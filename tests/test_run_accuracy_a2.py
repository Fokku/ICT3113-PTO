"""Tests for ``scripts/run_accuracy_a2.py``, the Assignment 2 accuracy driver.

Owner: Yeo Kai Yuan (Part 1 -- technical core). TODO_A2.md §1.3 / §1.5.

**No model, no Docker, no network.** The "service" is :class:`FakeService`, a
tiny ``http.server`` on 127.0.0.1 that answers ``GET /health`` and
``POST /tickets`` and writes schema-v2 log lines into a temporary
``SERVICE_LOG_DIR``. The A2 gate is replaced with ``monkeypatch``; the split
file and the team rows are temporary files, so the real golden-set files are
never touched by this suite -- and one test proves the driver never opens a
file under ``golden/`` other than the split, using an audit hook.
"""

from __future__ import annotations

import contextlib
import csv
import importlib.util
import json
import os
import shutil
import sys
import threading
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Callable, Iterator

import pytest

from service.categories import CATEGORIES
from service.log_schema import LOG_FIELDS

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "run_accuracy_a2.py"

# scripts/ is not a package: load the driver by path. It puts scripts/ on
# sys.path itself, so its own `import run_accuracy` / `import a2_gate` resolve.
_spec = importlib.util.spec_from_file_location("run_accuracy_a2_under_test", SCRIPT_PATH)
assert _spec is not None and _spec.loader is not None
drv = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = drv          # dataclasses look their module up here
_spec.loader.exec_module(drv)
a1 = drv.a1            # scripts/run_accuracy.py, as the driver imported it
a2_gate = drv.a2_gate

SMALL = "llama3.2:3b"
LARGE = "qwen2.5:7b"
SINGLE = "granite4:3b"


# ---------------------------------------------------------------------------
# File-open recorder (audit hook): which paths did the code under test open?
# ---------------------------------------------------------------------------

_OPENED: list[str] | None = None


def _audit(event: str, args: tuple) -> None:
    if event == "open" and _OPENED is not None and args:
        target = args[0]
        if isinstance(target, (str, bytes, os.PathLike)):
            try:
                _OPENED.append(os.path.abspath(os.fsdecode(target)))
            except (TypeError, ValueError):
                pass


sys.addaudithook(_audit)


@contextlib.contextmanager
def record_opens() -> Iterator[list[str]]:
    global _OPENED
    _OPENED = []
    try:
        yield _OPENED
    finally:
        _OPENED = None


# ---------------------------------------------------------------------------
# The fake service
# ---------------------------------------------------------------------------

def health_single(model_tag: str = SINGLE, **overrides) -> dict:
    body = {
        "status": "ok", "ollama_reachable": True,
        "model_tag": model_tag, "model_digest": "sha256:" + "a" * 64,
        "num_ctx": 4096, "seed": 42, "prompt_hash": "sha256:0123456789abcdef",
        "ollama_base_url": "http://ollama:11434", "db_path": "/data/triage.db",
        "uvicorn_workers": 1, "threadpool_size": 40,
        "service_mode": "single", "cascade_setting": None,
        "cascade_small_model_tag": None, "cascade_small_model_digest": None,
        "cascade_large_model_tag": None, "cascade_rule": None,
    }
    body.update(overrides)
    return body


def health_cascade(setting: str = "A", **overrides) -> dict:
    body = health_single(
        LARGE,
        service_mode="cascade", cascade_setting=setting,
        cascade_small_model_tag=SMALL, cascade_small_model_digest="sha256:" + "b" * 64,
        cascade_large_model_tag=LARGE,
        cascade_rule=f"escalate if predicted_category in {{...}} (Setting {setting}, test fixture)",
    )
    body.update(overrides)
    return body


class FakeService:
    """``GET /health`` + ``POST /tickets`` on 127.0.0.1, logging like the real service.

    ``fail_rows`` answer 502 (and are logged as errors); ``unlogged_rows`` are
    answered but never logged; in cascade mode ``escalate(row)`` decides which
    model "answered". Every POST's source row is recorded in arrival order.
    """

    def __init__(
        self,
        log_dir: Path,
        health: dict,
        *,
        fail_rows: tuple[int, ...] = (),
        unlogged_rows: tuple[int, ...] = (),
        escalate: Callable[[int], bool] = lambda row: row % 3 == 0,
    ) -> None:
        self.log_dir = log_dir
        self.health = health
        self.fail_rows = set(fail_rows)
        self.unlogged_rows = set(unlogged_rows)
        self.escalate = escalate
        self.posts: list[int] = []
        self.health_calls = 0
        self.in_flight = 0
        self.max_in_flight = 0
        self._lock = threading.Lock()
        self._server: ThreadingHTTPServer | None = None

    # -- what a request "does" ------------------------------------------
    def log_line(self, request_id: str, row: int, status: int, category: str | None) -> dict:
        cascade = self.health["service_mode"] == "cascade"
        escalated = self.escalate(row) if cascade else None
        line = {name: None for name in LOG_FIELDS}
        line.update(
            ts=a1.iso_ms(datetime.now(timezone.utc)),
            request_id=request_id, source_row=str(row), warmup=False,
            endpoint="/tickets", method="POST", status=status, ticket_chars=100,
            model_tag=(LARGE if escalated else SMALL) if cascade else self.health["model_tag"],
            predicted_category=category, prompt_hash=self.health["prompt_hash"],
            num_ctx=4096, seed=42, total_latency_ms=1.0, model_latency_ms=1.0,
            error=None if status == 200 else "ollama_timeout",
        )
        if cascade:
            line.update(
                escalated=escalated,
                cascade_setting=self.health["cascade_setting"],
                small_model_tag=SMALL,
                small_model_category=CATEGORIES[(row + 1) % len(CATEGORIES)],
            )
        return line

    def handle_post(self, request_id: str, row: int) -> tuple[int, dict]:
        with self._lock:
            self.posts.append(row)
        status = 502 if row in self.fail_rows else 200
        category = CATEGORIES[row % len(CATEGORIES)] if status == 200 else None
        if row not in self.unlogged_rows:
            line = self.log_line(request_id, row, status, category)
            path = self.log_dir / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
            with self._lock, path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(line) + "\n")
        if status != 200:
            return status, {"detail": "model backend did not classify the ticket",
                            "error": "ollama_timeout", "request_id": request_id}
        return 200, {"id": len(self.posts), "category": category, "request_id": request_id}

    # -- plumbing ---------------------------------------------------------
    def __enter__(self) -> "FakeService":
        fake = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args) -> None:   # keep pytest output clean
                pass

            def _send(self, status: int, body: dict) -> None:
                data = json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self) -> None:
                if self.path == "/health":
                    with fake._lock:
                        fake.health_calls += 1
                    self._send(200, fake.health)
                else:
                    self._send(404, {"detail": "not found"})

            def do_POST(self) -> None:
                if self.path != "/tickets":
                    self._send(404, {"detail": "not found"})
                    return
                with fake._lock:
                    fake.in_flight += 1
                    fake.max_in_flight = max(fake.max_in_flight, fake.in_flight)
                try:
                    length = int(self.headers.get("Content-Length") or 0)
                    json.loads(self.rfile.read(length) or b"{}")
                    status, body = fake.handle_post(
                        self.headers["X-Request-ID"], int(self.headers["X-Source-Row"])
                    )
                    self._send(status, body)
                finally:
                    with fake._lock:
                        fake.in_flight -= 1

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc) -> None:
        assert self._server is not None
        self._server.shutdown()
        self._server.server_close()

    @property
    def cli(self) -> list[str]:
        assert self._server is not None
        return ["--host", "127.0.0.1", "--port", str(self._server.server_address[1])]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

#: The temp split: rows 10001-10012 by parity, written out of order on purpose.
SPLIT_ROWS = [10007, 10002, 10001, 10012, 10004, 10003, 10010, 10005, 10006, 10009, 10008, 10011]
TEST_ROWS = sorted(row for row in SPLIT_ROWS if row % 2 == 0)
TUNING_ROWS = sorted(row for row in SPLIT_ROWS if row % 2 == 1)


def write_split(path: Path, rows: list[int] = SPLIT_ROWS, header: str = "row_number,set") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [header] + [f"{row},{'test' if row % 2 == 0 else 'tuning'}" for row in rows]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_team_rows(path: Path, rows: list[int], *, blank: tuple[int, ...] = ()) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["row_number", "narrative", "raw_label"])
        for row in rows:
            writer.writerow([row, "" if row in blank else f"Synthetic test narrative {row}.", "x"])
    return path


@pytest.fixture()
def env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict:
    """Temp log dir, temp split/team rows, temp dev-output root, clean env vars."""
    log_dir = tmp_path / "logs" / "service"
    log_dir.mkdir(parents=True)
    monkeypatch.setenv("SERVICE_LOG_DIR", str(log_dir))
    for name in ("SERVICE_SSH", "SERVICE_REPO", "RUN_NOTES", "ACCURACY_TIMEOUT_S", "SLICE_MARGIN_S"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1,localhost")
    monkeypatch.setenv("no_proxy", "127.0.0.1,localhost")

    split = write_split(tmp_path / "inputs" / "split_a2.csv")
    team_rows = write_team_rows(tmp_path / "inputs" / "team_rows.csv", sorted(SPLIT_ROWS))
    monkeypatch.setattr(drv, "SPLIT_PATH", split)
    monkeypatch.setattr(drv, "TEAM_ROWS_PATH", team_rows)
    monkeypatch.setattr(drv, "DEV_OUT_ROOT", tmp_path / "results" / "dev" / "accuracy_a2")
    return {"tmp": tmp_path, "log_dir": log_dir, "split": split, "team_rows": team_rows}


@pytest.fixture()
def gate_ok(monkeypatch: pytest.MonkeyPatch) -> a2_gate.GateStatus:
    status = a2_gate.GateStatus(
        ok=True, gate_commit="c" * 40, prediction_sha="1" * 40,
        escalation_rule_sha="2" * 40, split_sha="3" * 40,
    )
    monkeypatch.setattr(a2_gate, "check_gate", lambda repo: status)
    return status


@pytest.fixture()
def gate_must_not_run(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(repo):
        raise AssertionError("dev mode must bypass the A2 gate")
    monkeypatch.setattr(a2_gate, "check_gate", boom)


def only_run_dir(root: Path) -> Path:
    dirs = [p for p in root.iterdir() if p.is_dir()]
    assert len(dirs) == 1, dirs
    return dirs[0]


def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return list(reader.fieldnames or []), list(reader)


# ---------------------------------------------------------------------------
# Golden labels are never read
# ---------------------------------------------------------------------------

def test_source_never_names_the_golden_labels_file() -> None:
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    assert "golden_set.csv" not in source
    assert "GOLDEN_REL" not in source          # Assignment 1's path constant for it
    assert "golden_label" not in source


def test_split_reader_reads_only_row_number_and_set(tmp_path: Path) -> None:
    good = write_split(tmp_path / "good.csv")
    split = drv.read_split(good)
    assert set(split.values()) == {"test", "tuning"}
    assert all(isinstance(row, int) for row in split)

    # A split carrying any further column (a label, say) is refused, not read around.
    labelled = tmp_path / "labelled.csv"
    labelled.write_text("row_number,set,golden_label\n10002,test,Mortgage\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="expected exactly"):
        drv.read_split(labelled)
    swapped = write_split(tmp_path / "swapped.csv", header="set,row_number")
    with pytest.raises(SystemExit, match="expected exactly"):
        drv.read_split(swapped)


@pytest.mark.parametrize(
    "body, message",
    [
        ("row_number,set\n10002,test\n10002,test\n", "more than once"),
        ("row_number,set\n10002,holdout\n", "not one of"),
        ("row_number,set\nabc,test\n", "not a row number"),
        ("row_number,set\n", "no rows"),
    ],
)
def test_split_reader_fails_loudly_on_a_bad_split(tmp_path: Path, body: str, message: str) -> None:
    path = tmp_path / "split.csv"
    path.write_text(body, encoding="utf-8")
    with pytest.raises(SystemExit, match=message):
        drv.read_split(path)


def test_real_run_never_opens_the_golden_labels(env, gate_ok) -> None:
    with FakeService(env["log_dir"], health_single()) as svc, record_opens() as opened:
        code = drv.main(["--config", SINGLE, "--out-root", str(env["tmp"] / "out"), *svc.cli])
    assert code == 0
    golden_dir = str(REPO_ROOT / "golden")
    assert not [p for p in opened if "golden_set" in p or p.startswith(golden_dir)]
    assert not [p for p in opened if p == str(REPO_ROOT / "data" / "team_rows.csv")]
    assert str(env["split"]) in opened and str(env["team_rows"]) in opened


# ---------------------------------------------------------------------------
# --rows selection
# ---------------------------------------------------------------------------

def test_rows_selection_from_a_temp_split(env) -> None:
    for rows_set, expected in (("test", TEST_ROWS), ("tuning", TUNING_ROWS)):
        worklist, source, total = drv.build_worklist(
            rows_set, dev=False, split_path=env["split"],
            team_rows_path=env["team_rows"], dev_csv_path=Path("/nonexistent"),
        )
        assert [row for row, _ in worklist] == expected      # row-number order
        assert all(text == f"Synthetic test narrative {row}." for row, text in worklist)
        assert source == env["team_rows"] and total == len(SPLIT_ROWS)


def test_missing_or_empty_narrative_fails_loudly(env) -> None:
    short = write_team_rows(env["tmp"] / "short.csv", [r for r in SPLIT_ROWS if r != 10004])
    with pytest.raises(SystemExit, match="not present"):
        drv.build_worklist("test", dev=False, split_path=env["split"],
                           team_rows_path=short, dev_csv_path=Path("/nonexistent"))
    blank = write_team_rows(env["tmp"] / "blank.csv", SPLIT_ROWS, blank=(10006,))
    with pytest.raises(SystemExit, match="empty narrative"):
        drv.build_worklist("test", dev=False, split_path=env["split"],
                           team_rows_path=blank, dev_csv_path=Path("/nonexistent"))


def test_tuning_rows_are_posted_with_a_never_decides_note(env, gate_ok, capsys) -> None:
    with FakeService(env["log_dir"], health_single()) as svc:
        code = drv.main(["--config", SINGLE, "--rows", "tuning",
                         "--out-root", str(env["tmp"] / "out"), *svc.cli])
    assert code == 0
    assert svc.posts == TUNING_ROWS
    assert "NEVER used to decide pass/fail" in capsys.readouterr().out
    meta = json.loads((only_run_dir(env["tmp"] / "out") / "metadata.json").read_text())
    assert meta["rows_set"] == "tuning" and meta["n_rows"] == len(TUNING_ROWS)


# ---------------------------------------------------------------------------
# Dev mode
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "extra",
    [
        ["--out-root", "golden/"],
        ["--out-root", "data/team_rows.csv"],
        ["--out-root=results/dev/accuracy_a2/golden_set"],
    ],
)
def test_dev_mode_refuses_real_data_arguments(env, gate_must_not_run, extra, capsys) -> None:
    with FakeService(env["log_dir"], health_single()) as svc:
        code = drv.main(["--config", SINGLE, "--dev", *extra, *svc.cli])
    assert code == 2
    assert svc.health_calls == 0 and svc.posts == []
    assert "refusing" in capsys.readouterr().err


def test_dev_mode_refuses_to_write_outside_its_tree(env, gate_must_not_run) -> None:
    with FakeService(env["log_dir"], health_single()) as svc:
        code = drv.main(["--config", SINGLE, "--dev", "--out-root", str(env["tmp"] / "elsewhere"), *svc.cli])
    assert code == 2 and svc.posts == []


def test_dev_run_reads_only_synthetic_tickets_and_bypasses_the_gate(env, gate_must_not_run) -> None:
    dev_csv = REPO_ROOT / "data" / "dev" / "synthetic_tickets.csv"
    dev_rows = sorted(a1.read_narratives(dev_csv))
    with FakeService(env["log_dir"], health_cascade("B")) as svc, record_opens() as opened:
        code = drv.main(["--config", "cascade-B", "--dev", *svc.cli])
    assert code == 0
    assert svc.posts == [row for row in dev_rows if row % 2 == 0]     # --rows test, by parity
    assert not [p for p in opened if "team_rows" in p or "golden" in p or "split_a2" in p]

    run_dir = only_run_dir(drv.DEV_OUT_ROOT)
    assert run_dir.name.startswith("cascade-B_")
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["mode"] == "dev" and meta["gate_commit"] is None and meta["split_file"] is None
    assert meta["input_csv"] == "data/dev/synthetic_tickets.csv"
    gate = json.loads((run_dir / "gate.json").read_text())
    assert set(gate) == {"ok", "mode", "enforced", "reasons"}
    assert (gate["ok"], gate["mode"], gate["enforced"]) == (False, "dev", False)
    assert gate["reasons"] and "not evidence" in gate["reasons"][0]


# ---------------------------------------------------------------------------
# The A2 gate and the configuration check
# ---------------------------------------------------------------------------

def test_gate_blocked_exits_3_before_any_post(env, monkeypatch, capsys) -> None:
    blocked = a2_gate.GateStatus(ok=False, reasons=["The tag 'a2-predictions-freeze' does not exist."],
                                 fixes=["git tag -a a2-predictions-freeze"])
    monkeypatch.setattr(a2_gate, "check_gate", lambda repo: blocked)
    out_root = env["tmp"] / "out"
    with FakeService(env["log_dir"], health_cascade("A")) as svc, record_opens() as opened:
        code = drv.main(["--config", "cascade-A", "--out-root", str(out_root), *svc.cli])
    assert code == 3 == a2_gate.GATE_BLOCKED_EXIT
    assert svc.posts == [] and svc.health_calls == 0
    assert not out_root.exists()
    assert str(env["split"]) not in opened and str(env["team_rows"]) not in opened
    assert "A2 GATE: BLOCKED" in capsys.readouterr().err


@pytest.mark.parametrize(
    "config, health, expect",
    [
        ("cascade-A", health_single(), ["SERVICE_MODE=cascade", "CASCADE_SETTING=A",
                                        "CASCADE_SMALL_MODEL_TAG=", "MODEL_TAG="]),
        ("cascade-A", health_cascade("B"), ["SERVICE_MODE=cascade", "CASCADE_SETTING=A",
                                            f"CASCADE_SMALL_MODEL_TAG={SMALL}", f"MODEL_TAG={LARGE}"]),
        (SINGLE, health_single("llama3.2:3b"), ["SERVICE_MODE=single", f"MODEL_TAG={SINGLE}"]),
        # In cascade mode /health's model_tag is the large model: still not "qwen2.5:7b alone".
        (LARGE, health_cascade("A"), ["SERVICE_MODE=single", f"MODEL_TAG={LARGE}"]),
    ],
)
def test_config_health_mismatch_is_refused(env, gate_ok, capsys, config, health, expect) -> None:
    with FakeService(env["log_dir"], health) as svc:
        code = drv.main(["--config", config, "--out-root", str(env["tmp"] / "out"), *svc.cli])
    err = capsys.readouterr().err
    assert code == 1 and svc.posts == []
    assert "docker compose up -d --force-recreate triage" in err
    for fragment in expect:
        assert fragment in err


def test_unreachable_ollama_is_refused(env, gate_ok, capsys) -> None:
    with FakeService(env["log_dir"], health_single(ollama_reachable=False, status="degraded")) as svc:
        code = drv.main(["--config", SINGLE, "--out-root", str(env["tmp"] / "out"), *svc.cli])
    assert code == 1 and svc.posts == []
    assert "not reachable" in capsys.readouterr().err


def test_parse_config() -> None:
    assert drv.parse_config("cascade-A") == drv.Config("cascade-A", "A")
    assert drv.parse_config("cascade-b") == drv.Config("cascade-B", "B")
    assert drv.parse_config(" granite4:3b ") == drv.Config("granite4:3b", None)
    assert drv.parse_config("granite4:3b").dir_name == "granite4-3b"
    assert drv.parse_config("cascade-B").dir_name == "cascade-B"
    for bad in ("cascade-C", "cascade", ""):
        with pytest.raises(ValueError):
            drv.parse_config(bad)


def test_bad_cascade_config_is_misuse(env, gate_ok) -> None:
    assert drv.main(["--config", "cascade-C"]) == 2


# ---------------------------------------------------------------------------
# A full real-mode run, and the routing join
# ---------------------------------------------------------------------------

def test_cascade_run_end_to_end(env, gate_ok) -> None:
    out_root = env["tmp"] / "out"
    with FakeService(env["log_dir"], health_cascade("A"), fail_rows=(10004,),
                     unlogged_rows=(10008,)) as svc:
        code = drv.main(["--config", "cascade-A", "--out-root", str(out_root), *svc.cli])

    assert code == 1                              # one 502 and one missing log line
    assert svc.posts == TEST_ROWS                 # each once, in order: no retry of 10004
    assert svc.max_in_flight == 1                 # strictly sequential

    run_dir = only_run_dir(out_root)
    assert run_dir.name.startswith("cascade-A_")
    header, responses = read_csv(run_dir / "responses.csv")
    assert tuple(header) == drv.RESPONSES_COLUMNS
    assert [int(r["row_number"]) for r in responses] == TEST_ROWS
    failed = next(r for r in responses if r["row_number"] == "10004")
    assert failed["http_status"] == "502" and failed["predicted_category"] == ""
    assert failed["error"].startswith("http_502")

    service_lines = (run_dir / "service.jsonl").read_text().splitlines()
    assert len(service_lines) == len(TEST_ROWS) - 1

    header, routing = read_csv(run_dir / "routing.csv")
    assert tuple(header) == drv.ROUTING_COLUMNS
    by_row = {int(r["row_number"]): r for r in routing}
    assert list(by_row) == TEST_ROWS
    for resp in responses:
        assert by_row[int(resp["row_number"])]["request_id"] == resp["request_id"]
    for row in TEST_ROWS:
        r = by_row[row]
        if row == 10008:
            assert all(r[c] == "" for c in drv.ROUTING_COLUMNS[4:])   # missing log line
            continue
        esc = row % 3 == 0
        assert r["escalated"] == ("true" if esc else "false")
        assert r["model_tag"] == (LARGE if esc else SMALL)
        assert r["cascade_setting"] == "A" and r["small_model_tag"] == SMALL
        assert r["small_model_category"] == CATEGORIES[(row + 1) % len(CATEGORIES)]
        if row != 10004:
            assert r["predicted_category"] == CATEGORIES[row % len(CATEGORIES)]

    logged = [row for row in TEST_ROWS if row != 10008]
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["assignment"] == "A2" and meta["plan"] == "accuracy_a2" and meta["mode"] == "real"
    assert meta["config"] == meta["model_tag"] == "cascade-A"
    assert meta["rows_set"] == "test" and meta["n_rows"] == len(TEST_ROWS)
    assert meta["gate_commit"] == "c" * 40 and meta["gate_tag"] == "a2-predictions-freeze"
    assert meta["freeze_commit"] is None and meta["freeze_tag"] is None
    assert meta["service_mode"] == "cascade" and meta["cascade_setting"] == "A"
    assert meta["cascade_small_model_tag"] == SMALL and meta["cascade_large_model_tag"] == LARGE
    assert meta["cascade_rule"] and meta["split_file"] == "golden/split_a2.csv"
    assert meta["routing_missing_log_lines"] == 1
    assert meta["escalated_count"] == sum(row % 3 == 0 for row in logged)
    assert meta["escalation_denominator"] == len(logged)
    assert meta["escalation_fraction"] == pytest.approx(meta["escalated_count"] / len(logged))
    assert json.loads((run_dir / "gate.json").read_text()) == gate_ok.to_payload()


def test_single_model_run_leaves_cascade_columns_blank(env, gate_ok) -> None:
    out_root = env["tmp"] / "out"
    with FakeService(env["log_dir"], health_single()) as svc:
        code = drv.main(["--config", SINGLE, "--out-root", str(out_root), *svc.cli])
    assert code == 0 and svc.posts == TEST_ROWS
    run_dir = only_run_dir(out_root)
    assert run_dir.name.startswith("granite4-3b_")
    _, routing = read_csv(run_dir / "routing.csv")
    assert [r["model_tag"] for r in routing] == [SINGLE] * len(TEST_ROWS)
    assert all(r[c] == "" for r in routing for c in drv.ROUTING_CASCADE_COLUMNS)
    meta = json.loads((run_dir / "metadata.json").read_text())
    assert meta["escalated_count"] is None and meta["escalation_fraction"] is None
    assert meta["routing_missing_log_lines"] == 0 and meta["model_tag"] == SINGLE


def test_build_routing_join() -> None:
    def post(row, rid, status=200, cat="Mortgage"):
        return {"row_number": row, "request_id": rid, "http_status": status, "predicted_category": cat}

    def line(rid, **fields):
        base = {"ts": "2026-11-19T10:00:00.000Z", "request_id": rid, "endpoint": "/tickets",
                "method": "POST", "model_tag": SMALL, "predicted_category": "Mortgage",
                "escalated": False, "cascade_setting": "A", "small_model_tag": SMALL,
                "small_model_category": "Mortgage"}
        base.update(fields)
        return base

    posted = [post(1, "r1"), post(2, "r2"), post(3, "r3"), post(4, "r4", 502, None)]
    logs = [
        line("r3", model_tag=LARGE, escalated=True, small_model_category="Debt collection"),
        line("zz"),                                                    # not ours: ignored
        {"request_id": "r2", "endpoint": "/stats", "method": "GET"},  # not a ticket line
        line("r1"),
        line("r4", model_tag=LARGE, escalated=True, predicted_category=None),
    ]
    rows, summary = drv.build_routing(posted, logs, drv.Config("cascade-A", "A"))
    assert [r["request_id"] for r in rows] == ["r1", "r2", "r3", "r4"]   # posted order
    assert rows[0]["model_tag"] == SMALL and rows[0]["escalated"] == "false"
    assert rows[1]["model_tag"] == "" and rows[1]["escalated"] == ""     # no ticket line for r2
    assert rows[2]["model_tag"] == LARGE and rows[2]["escalated"] == "true"
    assert rows[2]["small_model_category"] == "Debt collection"
    assert rows[3]["http_status"] == 502 and rows[3]["predicted_category"] == ""
    assert summary.missing_log_lines == 1
    assert (summary.escalated_count, summary.escalation_denominator) == (2, 3)
    assert summary.escalation_fraction == pytest.approx(2 / 3)
    assert summary.config_mismatch_lines == 0 and summary.category_mismatches == 0

    # The same log read as a single-model run: cascade columns blank, lines flagged.
    rows, summary = drv.build_routing(posted[:1], [line("r1", escalated=None)], drv.Config(SMALL))
    assert rows[0]["model_tag"] == SMALL
    assert all(rows[0][c] == "" for c in drv.ROUTING_CASCADE_COLUMNS)
    assert summary.escalated_count is None and summary.escalation_fraction is None
    assert summary.config_mismatch_lines == 0
    _, summary = drv.build_routing(posted[:1], [line("r1")], drv.Config(SINGLE))
    assert summary.config_mismatch_lines == 1        # logged by another model


# ---------------------------------------------------------------------------
# Compatibility with Assignment 1's driver
# ---------------------------------------------------------------------------

def test_responses_header_and_metadata_keys_match_assignment_1(env, gate_must_not_run, monkeypatch) -> None:
    """Run the real A1 driver (dev mode) and this one against the same fake service."""
    a1_root = env["tmp"] / "a1_repo"
    (a1_root / "data" / "dev").mkdir(parents=True)
    shutil.copy(REPO_ROOT / "data" / "dev" / "synthetic_tickets.csv", a1_root / "data" / "dev")
    monkeypatch.setattr(a1, "REPO_ROOT", a1_root)

    with FakeService(env["log_dir"], health_single()) as svc:
        assert a1.main(["--model", SINGLE, "--dev", *svc.cli]) == 0
        assert drv.main(["--config", SINGLE, "--dev", *svc.cli]) == 0

    a1_dir = only_run_dir(a1_root / "results" / "dev" / "accuracy")
    a2_dir = only_run_dir(drv.DEV_OUT_ROOT)
    a1_header = (a1_dir / "responses.csv").read_text().splitlines()[0]
    a2_header = (a2_dir / "responses.csv").read_text().splitlines()[0]
    assert a2_header == a1_header == ",".join(drv.RESPONSES_COLUMNS)

    a1_meta = json.loads((a1_dir / "metadata.json").read_text())
    a2_meta = json.loads((a2_dir / "metadata.json").read_text())
    assert set(a1_meta) <= set(a2_meta)
    required_a2 = {
        "assignment", "config", "rows_set", "n_rows", "gate_commit", "gate_tag", "service_mode",
        "cascade_setting", "cascade_small_model_tag", "cascade_small_model_digest",
        "cascade_large_model_tag", "cascade_rule", "split_file", "escalated_count",
        "escalation_fraction", "routing_missing_log_lines",
    }
    assert required_a2 <= set(a2_meta)
    assert a2_meta["plan"] == "accuracy_a2"
