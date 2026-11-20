#!/usr/bin/env python3
"""Measure S and derive the Assignment 2 arrival rate, run length, timeout and pause.

Owner: Part 1 -- Yeo Kai Yuan (technical core). TODO_A2.md §1.3 ("Measure S").

The brief, Step 4, Set-up, followed literally:

* *"Restart Ollama and do the normal warm-up."* -- the Ollama container is
  restarted, then the same three fixed warm-up tickets every speed run uses
  (the first three hand-written rows of ``data/dev/synthetic_tickets.csv``,
  ``X-Warmup: 1``) are sent one at a time.
* *"Then send three different tickets of typical length to your top model, one
  at a time, and take the middle time. Do not send the same ticket three
  times"* -- three **different** team rows, chosen mechanically: not in the
  golden set (``golden/split_a2.csv`` row numbers -- no label is read), not in
  the speed-test workload (``workload/speed_test_rows_a2.txt``), and closest in
  length to the median of the 800 non-golden rows ("typical length"). They go
  through ``POST /tickets`` on the service serving ``qwen2.5:7b`` alone, and the
  time is the client-observed elapsed time, which is what JMeter measures.
* *"Call the middle time S ... Double it ... Send one ticket every 2S seconds"*
  -> ``rate_per_min = 60 / (2 S)``.
* *"Run for S minutes, with a minimum of 5"* -> ``duration_s = 60 * max(S, 5)``.
* *"the HTTP sampler's response timeout: set it to 10xS seconds, and at least 5
  minutes"* and *"set [the pause] longer than the timeout by at least one
  minute"* -> ``response_timeout_ms`` and ``pause_s = timeout + 60 s``.

It also does the 100-ticket check from ``docs/a2/arrival-rate.md`` §2: random
arrivals vary the count run to run, so the safe upper bound ``expected + 3 x
sqrt(expected)`` must not exceed the 100 tickets in the workload list, or a
ticket would repeat within a run and hit Ollama's prompt cache.

S is calibration, not a benchmark result: it touches no golden row and needs no
gate (TODO_A2.md, "What is NOT blocked").

Usage
-----
    # on the service host, with the triage service serving qwen2.5:7b alone
    python scripts/measure_s_a2.py
    # from the load generator, restarting Ollama on the service host over ssh
    SERVICE_SSH=user@service-host python scripts/measure_s_a2.py --restart ssh \\
        --service-url http://<service-host>:8000

Writes ``docs/a2/arrival_rate.json`` (read by ``scripts/run_load_test_a2.sh``);
refuses to overwrite it without ``--force``, because every speed run must use
the same S.

Exit codes: 0 done; 1 a request failed or the 100-ticket bound is exceeded;
2 misuse / cannot reach the service.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import shlex
import socket
import statistics
import subprocess
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAM_ROWS = REPO_ROOT / "data" / "team_rows.csv"
DEV_CSV = REPO_ROOT / "data" / "dev" / "synthetic_tickets.csv"
SPLIT = REPO_ROOT / "golden" / "split_a2.csv"
WORKLOAD = REPO_ROOT / "workload" / "speed_test_rows_a2.txt"
DEFAULT_OUT = REPO_ROOT / "docs" / "a2" / "arrival_rate.json"
TOP_MODEL = "qwen2.5:7b"
WORKLOAD_SIZE = 100

csv.field_size_limit(10 ** 9)


# ---------------------------------------------------------------------------
# Ticket selection (pure functions -- unit-tested)
# ---------------------------------------------------------------------------

def golden_rows(split: Path = SPLIT) -> set[int]:
    """Every golden-set row number, from the split. No label file is opened."""
    with split.open(newline="", encoding="utf-8") as handle:
        return {int(r["row_number"]) for r in csv.DictReader(handle)}


def workload_rows(path: Path = WORKLOAD) -> set[int]:
    rows = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            rows.add(int(line.split(",")[0]))
    return rows


def team_rows(path: Path = TEAM_ROWS) -> dict[int, str]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {int(r["row_number"]): r["narrative"] for r in csv.DictReader(handle)}


def dev_warmup_tickets(n: int = 3) -> list[tuple[str, str]]:
    """The same three fixed warm-up tickets the speed runs use (first three dev rows)."""
    with DEV_CSV.open(newline="", encoding="utf-8") as handle:
        return [(r["row_number"], r["narrative"]) for r in csv.DictReader(handle)][:n]


def choose_s_tickets(
    team: dict[int, str], golden: set[int], workload: set[int], n: int = 3
) -> tuple[list[int], float]:
    """The ``n`` non-golden, non-workload rows closest in length to the non-golden median.

    Ties are broken by the lower row number, so the choice is reproducible.
    Returns ``(rows, median_length)``.
    """
    non_golden = {row: len(text) for row, text in team.items() if row not in golden}
    median = statistics.median(non_golden.values())
    candidates = sorted(
        (abs(length - median), row) for row, length in non_golden.items() if row not in workload
    )
    return [row for _, row in candidates[:n]], float(median)


def derive(s_seconds: float, workload_size: int = WORKLOAD_SIZE) -> dict:
    """Everything the brief derives from S, plus the 100-ticket bound."""
    rate_per_min = round(60.0 / (2.0 * s_seconds), 2)
    duration_s = int(math.ceil(60.0 * max(s_seconds, 5.0)))
    timeout_s = max(10.0 * s_seconds, 300.0)
    response_timeout_ms = int(math.ceil(timeout_s * 1000))
    pause_s = int(math.ceil(timeout_s)) + 60
    expected = rate_per_min * duration_s / 60.0
    upper = expected + 3.0 * math.sqrt(expected)
    return {
        "rate_per_min": rate_per_min,
        "interval_s": round(2.0 * s_seconds, 3),
        "duration_s": duration_s,
        "response_timeout_ms": response_timeout_ms,
        "pause_s": pause_s,
        "expected_tickets_per_run": round(expected, 1),
        "safe_upper_bound_tickets": round(upper, 1),
        "workload_list_size": workload_size,
        "upper_bound_within_list": upper <= workload_size,
    }


# ---------------------------------------------------------------------------
# Service interaction
# ---------------------------------------------------------------------------

def get_json(url: str, timeout: float = 15) -> dict:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def post_ticket(base: str, narrative: str, row: str, request_id: str, warmup: bool, timeout: float) -> tuple[int, float]:
    """POST one ticket; return ``(http_status, client elapsed ms)``."""
    headers = {"Content-Type": "application/json", "X-Request-ID": request_id, "X-Source-Row": str(row)}
    if warmup:
        headers["X-Warmup"] = "1"
    request = urllib.request.Request(
        f"{base}/tickets", data=json.dumps({"narrative": narrative}).encode("utf-8"), headers=headers, method="POST"
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status = int(response.status)
    except urllib.error.HTTPError as exc:
        status = int(exc.code)
    return status, round((time.perf_counter() - started) * 1000.0, 1)


def restart_ollama(mode: str) -> str:
    if mode == "manual":
        return "manual (operator restarted the Ollama container before running this)"
    cmd = ["docker", "compose", "-f", str(REPO_ROOT / "docker-compose.yml"), "restart", "ollama"]
    if mode == "ssh":
        target = os.environ.get("SERVICE_SSH")
        repo = os.environ.get("SERVICE_REPO", "ICT3113-PTO")
        if not target:
            raise SystemExit("--restart ssh needs SERVICE_SSH=user@service-host")
        cmd = ["ssh", "-o", "BatchMode=yes", target,
               f"cd {shlex.quote(repo)} && docker compose -f docker-compose.yml restart ollama"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=300)
    if proc.returncode != 0:
        raise SystemExit(f"restarting Ollama failed: {proc.stderr.strip()[:400]}")
    return " ".join(cmd)


def wait_healthy(base: str, model: str, deadline_s: float = 240) -> dict:
    end = time.monotonic() + deadline_s
    last: object = None
    while time.monotonic() < end:
        try:
            health = get_json(f"{base}/health")
            if health.get("status") == "ok" and health.get("ollama_reachable"):
                return health
            last = health
        except (urllib.error.URLError, OSError, json.JSONDecodeError) as exc:
            last = exc
        time.sleep(2)
    raise SystemExit(f"/health never reported status ok with Ollama reachable: {last}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="measure_s_a2.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--service-url", default="http://127.0.0.1:8000")
    parser.add_argument("--model", default=TOP_MODEL, help="the top Assignment 1 model (default qwen2.5:7b)")
    parser.add_argument("--restart", choices=("docker", "ssh", "manual"), default="docker")
    parser.add_argument("--timeout-s", type=float, default=600.0, help="client timeout per request")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--force", action="store_true", help="overwrite an existing arrival_rate.json")
    parser.add_argument("--dry-run", action="store_true", help="print the chosen tickets and exit")
    args = parser.parse_args(argv)
    base = args.service_url.rstrip("/")

    team = team_rows()
    s_rows, median = choose_s_tickets(team, golden_rows(), workload_rows())
    warmups = dev_warmup_tickets()
    print(f"S tickets (closest to the {median:.0f}-char non-golden median, not golden, not in the workload):")
    for row in s_rows:
        print(f"  row {row}: {len(team[row])} chars")
    print(f"Warm-up tickets (dev rows): {', '.join(r for r, _ in warmups)}")
    if args.dry_run:
        return 0
    if args.out.exists() and not args.force:
        print(f"measure_s_a2: {args.out} exists; every speed run must use the same S. "
              f"Refusing to overwrite without --force.", file=sys.stderr)
        return 2

    restart_how = restart_ollama(args.restart)
    health = wait_healthy(base, args.model)
    if health.get("service_mode", "single") != "single" or health.get("model_tag") != args.model:
        print(f"measure_s_a2: the service is serving {health.get('service_mode')} / "
              f"{health.get('model_tag')!r}; S must be measured on {args.model!r} alone:\n"
              f"  MODEL_TAG={args.model} SERVICE_MODE=single docker compose up -d --force-recreate triage",
              file=sys.stderr)
        return 2

    print("Warm-up (timings discarded):")
    for row, narrative in warmups:
        status, ms = post_ticket(base, narrative, row, f"warmup-{uuid.uuid4()}", True, args.timeout_s)
        print(f"  dev row {row}: HTTP {status}")
        if status != 200:
            print("measure_s_a2: warm-up failed; nothing measured.", file=sys.stderr)
            return 1

    timings: list[dict] = []
    print("S measurement, one at a time:")
    for row in s_rows:
        request_id = f"s-measure-{uuid.uuid4()}"
        status, ms = post_ticket(base, team[row], str(row), request_id, False, args.timeout_s)
        timings.append({"row_number": row, "request_id": request_id, "http_status": status,
                        "elapsed_ms": ms, "narrative_chars": len(team[row])})
        print(f"  row {row}: HTTP {status}, {ms / 1000:.3f} s")
        if status != 200:
            print("measure_s_a2: a measurement request failed; S not recorded.", file=sys.stderr)
            return 1

    s_seconds = round(statistics.median(t["elapsed_ms"] for t in timings) / 1000.0, 3)
    derived = derive(s_seconds)
    payload = {
        "measured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "measured_from_host": socket.gethostname(),
        "service_url": base,
        "top_model_tag": args.model,
        "top_model_digest": health.get("model_digest"),
        "prompt_hash": health.get("prompt_hash"),
        "ollama_restart": restart_how,
        "warmup_rows": [r for r, _ in warmups],
        "s_selection": (f"the 3 team rows not in golden/split_a2.csv and not in "
                        f"workload/speed_test_rows_a2.txt whose narrative length is closest to "
                        f"the non-golden median ({median:.0f} chars); ties to the lower row number"),
        "s_rows": s_rows,
        "s_timings_s": [round(t["elapsed_ms"] / 1000.0, 3) for t in timings],
        "s_requests": timings,
        "s_seconds": s_seconds,
        **derived,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"\nS = {s_seconds} s (middle of {payload['s_timings_s']})")
    print(f"rate {derived['rate_per_min']}/min (one every {derived['interval_s']} s), "
          f"run {derived['duration_s']} s, timeout {derived['response_timeout_ms']} ms, pause {derived['pause_s']} s")
    print(f"~{derived['expected_tickets_per_run']} tickets per run; safe upper bound "
          f"{derived['safe_upper_bound_tickets']} vs {WORKLOAD_SIZE} in the list -> "
          f"{'OK' if derived['upper_bound_within_list'] else 'TOO MANY: regenerate a larger list first'}")
    print(f"Wrote {args.out.relative_to(REPO_ROOT) if args.out.is_relative_to(REPO_ROOT) else args.out}")
    return 0 if derived["upper_bound_within_list"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
