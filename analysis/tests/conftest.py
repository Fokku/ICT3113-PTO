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
        # Schema version 2: null unless a test builds a cascade line.
        "escalated": None,
        "cascade_setting": None,
        "small_model_tag": None,
        "small_model_category": None,
        "small_model_latency_ms": None,
        "small_load_duration": None,
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


# ---------------------------------------------------------------------------
# Assignment 2 speed runs (results/runs/<stamp>_<config>_speed_a2_<rate>_run<k>)
# ---------------------------------------------------------------------------
# Added for analysis/summarise_load_a2.py and the Assignment 2 checks in
# analysis/reconcile.py. Nothing above is changed by these helpers.

from service.log_schema import CASCADE_LOG_FIELDS, LOG_FIELDS_V1  # noqa: E402

#: What JMeter writes in ``responseCode`` for a request that timed out.
UNFINISHED_CODE = "Non HTTP response code: java.net.SocketTimeoutException"
#: Service overhead (total - model latency) and HTTP residual (model latency -
#: Ollama total) on every fabricated Assignment 2 line, in ms.
A2_SERVICE_OVERHEAD_MS = 10.0
A2_QUEUE_RESIDUAL_MS = 5.0
#: Client-side overhead added to the server's total for a completed sample, in ms.
A2_CLIENT_OVERHEAD_MS = 5
A2_EVAL_MS = 100.0


@dataclass(frozen=True)
class A2Sample:
    """One measured request of a fabricated Assignment 2 speed run.

    ``elapsed_ms`` is what JMeter records. ``code`` is JMeter's responseCode:
    ``"200"``, another number, or :data:`UNFINISHED_CODE`. ``other_ms`` becomes the
    line's ``ollama_other_ms`` (total_duration minus load, prompt and eval) and
    ``load_ms`` its ``load_duration``, both exactly. For a cascade run,
    ``escalated`` picks the answering model, and ``skipped_small`` models a
    length-rule escalation that never called the small model.
    """

    offset_ms: int
    elapsed_ms: int
    code: str = "200"
    escalated: bool = False
    skipped_small: bool = False
    other_ms: float = 10.0
    load_ms: float = 1.0
    source_row: str | None = None
    server_status: int | None = None
    log: bool = True


def steady_samples(elapsed: list[int], *, interval_ms: int = 10_000,
                   escalated: list[bool] | None = None, **common_fields) -> list[A2Sample]:
    """One :class:`A2Sample` per ``elapsed`` value, ``interval_ms`` apart from offset 0."""
    flags = escalated or [False] * len(elapsed)
    return [
        A2Sample(offset_ms=index * interval_ms, elapsed_ms=value, escalated=flag,
                 **common_fields)
        for index, (value, flag) in enumerate(zip(elapsed, flags, strict=True))
    ]


def make_a2_metadata(run_id: str, *, config: str, cascade_setting: str | None,
                     small_model: str, large_model: str, rate_per_min: float,
                     run_index: int, warmup_ids: list[str], stats_before: int,
                     stats_after: int, n_samples: int, **overrides) -> dict:
    """Assignment 2 speed-run metadata: every Assignment 1 key plus the A2 contract keys."""
    cascade = cascade_setting is not None
    meta = make_metadata(
        run_id=run_id,
        plan="speed_a2",
        plan_file="jmeter/speed_a2.jmx",
        model_tag=large_model if cascade else config,
        model_digest="sha256:" + "b" * 12,
        rate_per_min=rate_per_min,
        run_index=run_index,
        freeze_commit=None,
        freeze_tag=None,
        input_csv="data/speed_test_tickets_a2.csv",
        warmup_request_id=warmup_ids[0] if warmup_ids else None,
    )
    meta.update({
        "assignment": "A2",
        "config": config,
        "service_mode": "cascade" if cascade else "single",
        "cascade_setting": cascade_setting,
        "cascade_small_model_tag": small_model if cascade else None,
        "cascade_small_model_digest": ("sha256:" + "c" * 12) if cascade else None,
        "cascade_large_model_tag": large_model if cascade else None,
        "cascade_rule": "category: escalate = predicted not in {...}" if cascade else None,
        "gate_commit": "2" * 40,
        "gate_tag": "a2-predictions-freeze",
        "s_seconds": 6.0,
        "response_timeout_ms": 300_000,
        "pause_s": 360,
        "ticket_list": "workload/speed_test_rows_a2.txt",
        "warmup_request_ids": list(warmup_ids),
        "large_model_direct_warmup": cascade,
        "stats_total_before": stats_before,
        "stats_total_after": stats_after,
        "expected_models": [small_model, large_model] if cascade else [config],
        "resident_models_before": [small_model, large_model] if cascade else [config],
        "resident_models_after": [small_model, large_model] if cascade else [config],
        "all_expected_resident_before": True,
        "all_expected_resident_after": True,
        "env_check_ok": True,
        "jtl_samples": n_samples,
        "mode": "real",
    })
    meta.update(overrides)
    return meta


def build_a2_run_dir(
    root: Path,
    samples: list[A2Sample],
    *,
    config: str = "qwen2.5:7b",
    cascade_setting: str | None = None,
    stamp: str = "20261120T090000Z",
    rate: str = "5pm",
    run_index: int = 1,
    small_model: str = "llama3.2:3b",
    large_model: str = "qwen2.5:7b",
    n_warmup: int = 3,
    stats_delta: int | None = None,
    gate_ok: bool | None = True,
    metadata_overrides: dict | None = None,
    line_overrides: dict[int, dict] | None = None,
) -> FakeRun:
    """Build one complete, self-consistent fabricated Assignment 2 speed run.

    The directory name follows the run-script contract
    (``<stamp>_<config>_speed_a2_<rate>_run<k>``). ``stats_delta`` defaults to the
    number of HTTP 200 service-log lines (what the service stores);
    ``line_overrides`` maps a sample index to service-log fields to replace, so a
    test can break one line on purpose. ``gate_ok=None`` writes no gate.json.
    """
    cascade = cascade_setting is not None
    config_dir = f"cascade-{cascade_setting}" if cascade else (
        config.replace(":", "-"))
    run_dir = root / f"{stamp}_{config_dir}_speed_a2_{rate}_run{run_index}"
    run_dir.mkdir(parents=True, exist_ok=True)
    tag = f"{config_dir}-r{run_index}-{stamp}"

    jtl_rows: list[dict] = []
    log_records: list[dict] = []
    for index, sample in enumerate(samples):
        request_id = f"{tag}-req-{index:04d}"
        source_row = sample.source_row or str(20000 + index)
        moment = BASE_TIME + timedelta(milliseconds=sample.offset_ms)
        numeric = sample.code.isdigit()
        jtl_rows.append(
            make_jtl_row(
                timeStamp=int(moment.timestamp() * 1000),
                elapsed=sample.elapsed_ms,
                Latency=sample.elapsed_ms - 1,
                responseCode=sample.code,
                responseMessage="OK" if sample.code == "200" else sample.code,
                success="true" if sample.code == "200" else "false",
                request_id=request_id,
                source_row=source_row,
            )
        )
        if not sample.log:
            continue
        status = sample.server_status or (int(sample.code) if numeric else 200)
        # An unfinished request: the client gave up, the service finished later.
        total = float(sample.elapsed_ms - A2_CLIENT_OVERHEAD_MS) if numeric else float(
            sample.elapsed_ms + 10_000)
        model_latency = total - A2_SERVICE_OVERHEAD_MS
        ollama_total = model_latency - A2_QUEUE_RESIDUAL_MS
        prompt = ollama_total - sample.load_ms - A2_EVAL_MS - sample.other_ms
        ok = status == 200
        if cascade:
            answered = large_model if sample.escalated else small_model
            category = CATEGORIES[index % len(CATEGORIES)]
            route = {
                "escalated": sample.escalated,
                "cascade_setting": cascade_setting,
                "small_model_tag": small_model,
                "small_model_category": None if sample.skipped_small else category,
                "small_model_latency_ms": None if sample.skipped_small else 400.0,
                "small_load_duration": None if sample.skipped_small else 1_000_000,
            }
        else:
            answered, category = config, CATEGORIES[index % len(CATEGORIES)]
            route = {name: None for name in CASCADE_LOG_FIELDS}
        record = make_log_line(
            ts=iso_ms(moment + timedelta(milliseconds=total)),
            request_id=request_id,
            source_row=source_row,
            status=status,
            model_tag=answered,
            predicted_category=category if ok else None,
            raw_model_output=category if ok else None,
            total_latency_ms=total,
            model_latency_ms=model_latency,
            total_duration=int(round(ollama_total * 1_000_000)) if ok else None,
            load_duration=int(round(sample.load_ms * 1_000_000)) if ok else None,
            prompt_eval_duration=int(round(prompt * 1_000_000)) if ok else None,
            eval_duration=int(round(A2_EVAL_MS * 1_000_000)) if ok else None,
            prompt_eval_count=300 if ok else None,
            eval_count=5 if ok else None,
            error=None if ok else "ollama_timeout",
            **route,
        )
        record.update((line_overrides or {}).get(index, {}))
        log_records.append(record)

    warm_ids = [f"{tag}-warmup-{k}" for k in range(n_warmup)]
    warm_records = [
        make_log_line(
            ts=iso_ms(BASE_TIME - timedelta(seconds=30 - 5 * k)),
            request_id=warm_id,
            source_row=str(30000 + k),
            warmup=True,
            model_tag=large_model if cascade else config,
            total_latency_ms=9000.0,
            model_latency_ms=8990.0,
            load_duration=8_000_000_000,
            **({"escalated": True, "cascade_setting": cascade_setting,
                "small_model_tag": small_model, "small_model_category": CATEGORIES[0],
                "small_model_latency_ms": 400.0, "small_load_duration": 1_000_000}
               if cascade else {}),
        )
        for k, warm_id in enumerate(warm_ids)
    ]

    write_jtl(run_dir / "results.jtl", jtl_rows)
    write_service_log(run_dir / "service.jsonl", log_records)
    if warm_records:
        write_service_log(run_dir / "warmup.jsonl", warm_records)

    stored = sum(1 for r in log_records if r["status"] == 200)
    before = 100
    after = before + (stored if stats_delta is None else stats_delta)
    meta = make_a2_metadata(
        run_dir.name, config=f"cascade-{cascade_setting}" if cascade else config,
        cascade_setting=cascade_setting, small_model=small_model, large_model=large_model,
        rate_per_min=float(rate.removesuffix("pm")), run_index=run_index,
        warmup_ids=warm_ids, stats_before=before, stats_after=after,
        n_samples=len(jtl_rows),
    )
    meta.update(metadata_overrides or {})
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    (run_dir / "stats_before.json").write_text(
        json.dumps({"total": before, "counts": {}}), encoding="utf-8")
    (run_dir / "stats_after.json").write_text(
        json.dumps({"total": after, "counts": {}}), encoding="utf-8")
    (run_dir / "env_check.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    if gate_ok is not None:
        (run_dir / "gate.json").write_text(
            json.dumps({"ok": gate_ok, "gate_commit": meta["gate_commit"],
                        "gate_tag": meta["gate_tag"]}), encoding="utf-8")
    return FakeRun(run_dir, run_dir / "results.jtl", run_dir / "service.jsonl", meta)


def to_v1_line(record: dict) -> dict:
    """An Assignment 1 (schema version 1, 24-field) copy of a log line."""
    return {name: record[name] for name in LOG_FIELDS_V1}


def build_a2_accuracy_dir(root: Path, *, setting: str, stamp: str, escalated: list[bool],
                          rows_set: str = "test", mode: str = "real") -> Path:
    """A fabricated ``results/accuracy_a2/cascade-<S>_<stamp>/`` with its service log."""
    run_dir = root / f"cascade-{setting}_{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    records = [
        make_log_line(
            ts=iso_ms(BASE_TIME + timedelta(seconds=index)),
            request_id=f"acc-{setting}-{stamp}-{index:03d}",
            source_row=str(10000 + 2 * index),
            escalated=flag,
            cascade_setting=setting,
            small_model_tag="llama3.2:3b",
            small_model_category=CATEGORIES[0],
            small_model_latency_ms=400.0,
            small_load_duration=1_000_000,
            model_tag="qwen2.5:7b" if flag else "llama3.2:3b",
        )
        for index, flag in enumerate(escalated)
    ]
    write_service_log(run_dir / "service.jsonl", records)
    meta = {
        "run_id": run_dir.name,
        "mode": mode,
        "plan": "accuracy_a2",
        "model_tag": f"cascade-{setting}",
        "assignment": "A2",
        "config": f"cascade-{setting}",
        "rows_set": rows_set,
        "service_mode": "cascade",
        "cascade_setting": setting,
        "warmup_request_id": None,
        "started_at_utc": iso_ms(BASE_TIME),
    }
    (run_dir / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return run_dir
