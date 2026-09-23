"""Fixture builders for the analysis tests.

The analysis scripts must never be exercised against real model output during
development (that would be measuring a model before the freeze). So every test
in ``analysis/tests`` runs against **fabricated** evidence built here: fake
JMeter ``.jtl`` files and fake service logs whose shapes match the real ones
exactly -- ``service/log_schema.LOG_FIELDS`` for the logs, JMeter's CSV save
format plus the two ``sample_variables`` columns for the ``.jtl``.

The numbers these builders produce are arbitrary test data. They are never
reported, never committed as results, and live only under ``pytest``'s tmp_path.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from service.categories import CATEGORIES, UNPARSEABLE  # noqa: E402
from service.log_schema import LOG_FIELDS  # noqa: E402

#: Columns JMeter writes to a CSV .jtl with our save settings, in JMeter's own
#: order, followed by the two sample variables the run scripts request.
JTL_COLUMNS: tuple[str, ...] = (
    "timeStamp",
    "elapsed",
    "label",
    "responseCode",
    "responseMessage",
    "threadName",
    "dataType",
    "success",
    "failureMessage",
    "bytes",
    "sentBytes",
    "grpThreads",
    "allThreads",
    "URL",
    "Latency",
    "IdleTime",
    "Connect",
    "request_id",
    "source_row",
)

BASE_TIME = datetime(2026, 10, 1, 9, 0, 0, tzinfo=timezone.utc)


def iso_ms(moment: datetime) -> str:
    """Format as the service does: UTC, millisecond precision, ``Z`` suffix."""
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + (
        f"{moment.microsecond // 1000:03d}Z"
    )


def make_log_line(**overrides) -> dict:
    """One schema-complete service log line, with sensible defaults.

    Pass any field as a keyword to override it. Unknown keywords raise, so a
    typo in a test cannot silently produce an off-schema fixture.
    """
    bad = set(overrides) - set(LOG_FIELDS)
    if bad:
        raise KeyError(f"not service log fields: {sorted(bad)}")
    line = {
        "ts": iso_ms(BASE_TIME),
        "request_id": "00000000-0000-4000-8000-000000000000",
        "source_row": "10000",
        "warmup": False,
        "endpoint": "/tickets",
        "method": "POST",
        "status": 200,
        "ticket_chars": 800,
        "model_tag": "testmodel:1b",
        "model_digest": "sha256:" + "a" * 12,
        "predicted_category": CATEGORIES[0],
        "raw_model_output": CATEGORIES[0],
        "prompt_hash": "sha256:0123456789abcdef",
        "num_ctx": 4096,
        "seed": 42,
        "total_latency_ms": 1000.0,
        "model_latency_ms": 990.0,
        "total_duration": 990_000_000,
        "load_duration": 10_000_000,
        "prompt_eval_count": 300,
        "prompt_eval_duration": 400_000_000,
        "eval_count": 5,
        "eval_duration": 570_000_000,
        "error": None,
    }
    line.update(overrides)
    return {field: line[field] for field in LOG_FIELDS}


def write_service_log(path: Path, records) -> Path:
    """Write ``records`` as JSON lines, in :data:`LOG_FIELDS` order."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return path


def make_jtl_row(**overrides) -> dict:
    """One JMeter CSV sample row, with defaults matching :func:`make_log_line`."""
    bad = set(overrides) - set(JTL_COLUMNS)
    if bad:
        raise KeyError(f"not .jtl columns: {sorted(bad)}")
    row = {
        "timeStamp": int(BASE_TIME.timestamp() * 1000),
        "elapsed": 1005,
        "label": "POST /tickets",
        "responseCode": "200",
        "responseMessage": "OK",
        "threadName": "og-1-1",
        "dataType": "text",
        "success": "true",
        "failureMessage": "",
        "bytes": 120,
        "sentBytes": 900,
        "grpThreads": 1,
        "allThreads": 1,
        "URL": "http://10.0.0.11:8000/tickets",
        "Latency": 1004,
        "IdleTime": 0,
        "Connect": 1,
        "request_id": "00000000-0000-4000-8000-000000000000",
        "source_row": "10000",
    }
    row.update(overrides)
    return {column: row[column] for column in JTL_COLUMNS}


def write_jtl(path: Path, rows) -> Path:
    """Write ``rows`` as a JMeter CSV ``.jtl``."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(JTL_COLUMNS))
        writer.writeheader()
        writer.writerows(rows)
    return path


def make_metadata(**overrides) -> dict:
    """A complete ``metadata.json`` payload for a fabricated run directory."""
    meta = {
        "run_id": "20261001T090000Z_testmodel-1b_load_post_tickets_60pm_run1",
        "mode": "real",
        "plan": "load_post_tickets",
        "plan_file": "jmeter/load_post_tickets.jmx",
        "model_tag": "testmodel:1b",
        "model_digest": "sha256:" + "a" * 12,
        "rate_per_min": 60,
        "duration_s": 300,
        "run_index": 1,
        "runs_total": 3,
        "started_at_utc": iso_ms(BASE_TIME),
        "ended_at_utc": iso_ms(BASE_TIME + timedelta(seconds=300)),
        "git_commit": "0" * 40,
        "git_dirty": False,
        "freeze_commit": "1" * 40,
        "freeze_tag": "golden-freeze",
        "prompt_hash": "sha256:0123456789abcdef",
        "num_ctx": 4096,
        "seed": 42,
        "input_csv": "data/team_rows.csv",
        "service_url": "http://10.0.0.11:8000",
        "service_host_info": {"hostname": "svc-host"},
        "load_generator_host_info": {"hostname": "loadgen-host"},
        "jmeter_version": "5.6.3",
        "ollama_num_parallel": "default",
        "ollama_max_loaded_models": "default",
        "warmup_request_id": "warmup-00000000",
        "notes": "",
    }
    meta.update(overrides)
    return meta


@dataclass(frozen=True)
class FakeRun:
    """A fabricated run directory on disk."""

    path: Path
    jtl: Path
    service_log: Path
    metadata: dict


def build_run_dir(
    root: Path,
    *,
    stamp: str = "20261001T090000Z",
    model: str = "testmodel-1b",
    plan: str = "load_post_tickets",
    rate: str = "60pm",
    run_index: int = 1,
    n_samples: int = 20,
    base_latency_ms: int = 1000,
    latency_step_ms: int = 10,
    n_errors: int = 0,
    include_warmup: bool = True,
    interval_ms: int = 1000,
    metadata_overrides: dict | None = None,
    drop_log_for_last: int = 0,
    drop_jtl_for_first: int = 0,
) -> FakeRun:
    """Build one complete, self-consistent fabricated run directory.

    ``drop_log_for_last`` / ``drop_jtl_for_first`` deliberately break the
    one-to-one correspondence so ``reconcile.py`` can be tested against a run
    that does *not* reconcile.
    """
    run_dir = root / f"{stamp}_{model}_{plan}_{rate}_run{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)

    log_records: list[dict] = []
    jtl_rows: list[dict] = []

    if include_warmup:
        warm_id = "warmup-00000000"
        log_records.append(
            make_log_line(
                ts=iso_ms(BASE_TIME - timedelta(seconds=5)),
                request_id=warm_id,
                source_row="900000",
                warmup=True,
                total_latency_ms=9000.0,
                model_latency_ms=8990.0,
                load_duration=8_000_000_000,
            )
        )

    for index in range(n_samples):
        request_id = f"req-{index:04d}"
        source_row = str(10000 + index)
        moment = BASE_TIME + timedelta(milliseconds=index * interval_ms)
        is_error = index >= n_samples - n_errors
        latency = base_latency_ms + index * latency_step_ms
        log_records.append(
            make_log_line(
                ts=iso_ms(moment),
                request_id=request_id,
                source_row=source_row,
                status=502 if is_error else 200,
                total_latency_ms=float(latency),
                model_latency_ms=float(latency - 10),
                predicted_category=None if is_error else CATEGORIES[index % len(CATEGORIES)],
                raw_model_output=None if is_error else CATEGORIES[index % len(CATEGORIES)],
                error="ollama_timeout" if is_error else None,
                total_duration=None if is_error else (latency - 10) * 1_000_000,
                eval_count=None if is_error else 5,
            )
        )
        jtl_rows.append(
            make_jtl_row(
                timeStamp=int(moment.timestamp() * 1000),
                elapsed=latency + 5,
                Latency=latency + 4,
                responseCode="502" if is_error else "200",
                success="false" if is_error else "true",
                request_id=request_id,
                source_row=source_row,
            )
        )

    if drop_log_for_last:
        log_records = log_records[:-drop_log_for_last]
    if drop_jtl_for_first:
        jtl_rows = jtl_rows[drop_jtl_for_first:]

    warm = [r for r in log_records if r["warmup"]]
    body = [r for r in log_records if not r["warmup"]]
    write_service_log(run_dir / "service.jsonl", body)
    if warm:
        write_service_log(run_dir / "warmup.jsonl", warm)
    write_jtl(run_dir / "results.jtl", jtl_rows)

    meta = make_metadata(
        run_id=run_dir.name,
        plan=plan,
        model_tag=model.replace("-", ":", 1),
        rate_per_min=int(rate.removesuffix("pm")) if rate.endswith("pm") else 0,
        run_index=run_index,
        **(metadata_overrides or {}),
    )
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (run_dir / "freeze.json").write_text(
        json.dumps({"ok": True, "freeze_commit": meta["freeze_commit"],
                    "freeze_tag": "golden-freeze"}, indent=2),
        encoding="utf-8",
    )
    return FakeRun(run_dir, run_dir / "results.jtl", run_dir / "service.jsonl", meta)


@pytest.fixture()
def build_run(tmp_path: Path):
    """Factory fixture: ``build_run(**kwargs)`` -> :class:`FakeRun`."""

    def _build(**kwargs) -> FakeRun:
        kwargs.setdefault("root", tmp_path / "runs")
        return build_run_dir(**kwargs)

    return _build


@pytest.fixture()
def golden_csv(tmp_path: Path):
    """Factory fixture writing a ``golden/golden_set.csv``-shaped file."""

    def _write(pairs, name: str = "golden_set.csv") -> Path:
        path = tmp_path / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["row_number", "label"])
            writer.writerows(pairs)
        return path

    return _write
