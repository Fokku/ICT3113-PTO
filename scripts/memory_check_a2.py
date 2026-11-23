#!/usr/bin/env python3
"""Assignment 2 memory check: can a small model and the large model stay resident together?

Owner: Part 1 -- Yeo Kai Yuan (technical core). TODO_A2.md §1.1.

The brief, Step 2 ("Memory: both models must fit at the same time"): *"A cascade
only works if the small model and the large model are both loaded in memory
together ... Check this before you build anything: load both models, run a few
tickets through each, and confirm that ``ollama ps`` lists both. If they do not
both stay loaded, try a smaller pair. If no pair fits, report that a cascade is
not feasible on this machine, show the ``ollama ps`` evidence, and recommend a
single model."*

What it does, per pair (small model, large model)
-------------------------------------------------
1. ``docker compose restart ollama`` -- nothing resident, prompt cache empty.
2. Sends the same few hand-written dev tickets (``data/dev/synthetic_tickets.csv``,
   never a team row) to the small and the large model **alternately**, straight
   to Ollama's ``/api/generate`` with the service's own request shape (the
   unchanged classification prompt, temperature 0, the fixed seed, ``num_ctx``).
   Alternating is the point: if the two do not fit together, Ollama evicts one
   to load the other and every call after the first pays a reload, which shows
   up in Ollama's own ``load_duration``.
3. Captures ``ollama ps`` inside the container (the brief's evidence) and
   ``GET /api/ps`` (sizes and expiry, machine-readable), the host's memory, the
   Ollama container's memory use and limit (``docker stats`` / ``docker
   inspect``).
4. Verdict: **fits** when ``/api/ps`` lists both tags after the last call AND no
   call after each model's first one paid a reload (``load_duration`` above
   ``--reload-threshold-ms``).

Nothing here is a benchmark: no latency is reported as a result, and the
inference settings (``OLLAMA_NUM_PARALLEL``, ``OLLAMA_MAX_LOADED_MODELS``, ...)
are recorded, never changed. Run it on the service host (it needs ``docker``).

Usage
-----
    python scripts/memory_check_a2.py                      # all three small models vs qwen2.5:7b
    python scripts/memory_check_a2.py --small llama3.2:3b  # one pair

Output: ``docs/environment/a2-memory-check/<UTC stamp>/`` with, per pair,
``<pair>/ollama_ps.txt``, ``api_ps.json``, ``calls.csv``, ``docker_stats.txt``,
plus ``host_memory.txt``, ``ollama_env.txt``, ``summary.json`` and
``summary.md`` for the whole check.

Exit codes: 0 at least one pair fits; 1 no pair fits; 2 could not check.
"""

from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from service.prompt import build_prompt  # noqa: E402  (the unchanged classification prompt)

DEFAULT_LARGE = "qwen2.5:7b"
DEFAULT_SMALLS = ("llama3.2:1b-instruct-q4_K_M", "llama3.2:3b", "granite4:3b")
DEV_CSV = REPO_ROOT / "data" / "dev" / "synthetic_tickets.csv"
OUT_ROOT = REPO_ROOT / "docs" / "environment" / "a2-memory-check"

csv.field_size_limit(10 ** 9)


class CannotCheck(RuntimeError):
    pass


def stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def safe(tag: str) -> str:
    return "".join(c if c.isalnum() or c in "._-" else "-" for c in tag).strip("-")


def run(cmd: list[str], *, check: bool = False, timeout: float = 300) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
    if check and proc.returncode != 0:
        raise CannotCheck(f"{' '.join(cmd)} failed ({proc.returncode}): {proc.stderr.strip()[:400]}")
    return proc


def compose(args: argparse.Namespace, *rest: str, check: bool = True, timeout: float = 300):
    return run(["docker", "compose", "-f", str(args.compose_file), *rest], check=check, timeout=timeout)


def http_json(url: str, payload: dict | None = None, timeout: float = 600) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, headers={"Content-Type": "application/json"}, method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise CannotCheck(f"{'POST' if data else 'GET'} {url} failed: {exc}") from exc


def wait_for_ollama(url: str, deadline_s: float = 120) -> str:
    end = time.monotonic() + deadline_s
    last = ""
    while time.monotonic() < end:
        try:
            return http_json(f"{url}/api/version", timeout=5).get("version", "?")
        except CannotCheck as exc:
            last = str(exc)
            time.sleep(2)
    raise CannotCheck(f"Ollama did not come back within {deadline_s:.0f}s: {last}")


def dev_tickets(n: int) -> list[tuple[str, str]]:
    with DEV_CSV.open(newline="", encoding="utf-8") as handle:
        rows = [(r["row_number"], r["narrative"]) for r in csv.DictReader(handle)]
    if len(rows) < n:
        raise CannotCheck(f"{DEV_CSV} has only {len(rows)} tickets")
    return rows[:n]


def resident(api_ps: dict) -> list[str]:
    names: set[str] = set()
    for entry in api_ps.get("models") or []:
        names.update(v for v in (entry.get("name"), entry.get("model")) if v)
    return sorted(names)


def check_pair(args: argparse.Namespace, small: str, large: str, out_dir: Path) -> dict:
    pair_dir = out_dir / f"{safe(small)}__{safe(large)}"
    pair_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n== {small} + {large}")

    print("   restarting the Ollama container (nothing resident, prompt cache cleared)")
    compose(args, "restart", args.ollama_service)
    version = wait_for_ollama(args.ollama_url)

    tickets = dev_tickets(args.tickets)
    calls: list[dict] = []
    order = [(i, model) for i in range(len(tickets)) for model in (small, large)]
    for index, (ticket_i, model) in enumerate(order, 1):
        row, narrative = tickets[ticket_i]
        body = http_json(
            f"{args.ollama_url}/api/generate",
            {
                "model": model,
                "prompt": build_prompt(narrative),
                "stream": False,
                "options": {"temperature": 0, "seed": args.seed, "num_ctx": args.num_ctx},
            },
            timeout=args.call_timeout_s,
        )
        load_ms = (body.get("load_duration") or 0) / 1e6
        calls.append(
            {
                "call": index,
                "model": model,
                "dev_row": row,
                "load_duration_ms": round(load_ms, 1),
                "total_duration_ms": round((body.get("total_duration") or 0) / 1e6, 1),
                "first_call_for_model": sum(1 for c in calls if c["model"] == model) == 0,
                "reply": (body.get("response") or "").strip()[:60],
            }
        )
        print(f"   call {index}: {model:<30} load_duration {load_ms:9.1f} ms")

    ps_text = compose(args, "exec", "-T", args.ollama_service, "ollama", "ps").stdout
    api_ps = http_json(f"{args.ollama_url}/api/ps", timeout=15)
    stats = run(["docker", "stats", "--no-stream", "--format",
                 "{{.Name}}\t{{.MemUsage}}\t{{.MemPerc}}\t{{.CPUPerc}}", args.ollama_container]).stdout
    (pair_dir / "ollama_ps.txt").write_text(ps_text, encoding="utf-8")
    (pair_dir / "api_ps.json").write_text(json.dumps(api_ps, indent=2) + "\n", encoding="utf-8")
    (pair_dir / "docker_stats.txt").write_text(stats, encoding="utf-8")
    with (pair_dir / "calls.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(calls[0]))
        writer.writeheader()
        writer.writerows(calls)

    listed = resident(api_ps)
    both_listed = small in listed and large in listed
    reloads = [c for c in calls if not c["first_call_for_model"] and c["load_duration_ms"] > args.reload_threshold_ms]
    sizes = {
        (e.get("name") or e.get("model")): e.get("size")
        for e in api_ps.get("models") or []
    }
    fits = both_listed and not reloads
    print(f"   ollama ps lists: {', '.join(listed) or '(nothing)'}")
    print(f"   reloads after first load: {len(reloads)}  ->  {'FITS' if fits else 'DOES NOT FIT'}")
    return {
        "small": small,
        "large": large,
        "ollama_version": version,
        "resident_after_last_call": listed,
        "both_listed": both_listed,
        "reloads_after_first_load": len(reloads),
        "reload_threshold_ms": args.reload_threshold_ms,
        "resident_sizes_bytes": sizes,
        "resident_total_bytes": sum(v for v in sizes.values() if isinstance(v, int)),
        "calls": len(calls),
        "fits": fits,
        "evidence_dir": str(pair_dir.relative_to(REPO_ROOT)),
        "docker_stats": stats.strip(),
    }


def host_memory() -> str:
    parts = []
    proc = run(["free", "-b"])
    parts.append("$ free -b\n" + proc.stdout)
    try:
        meminfo = Path("/proc/meminfo").read_text(encoding="utf-8").splitlines()[:3]
        parts.append("$ head -3 /proc/meminfo\n" + "\n".join(meminfo) + "\n")
    except OSError:
        pass
    return "\n".join(parts)


def container_memory_limit(args: argparse.Namespace) -> str:
    proc = run(["docker", "inspect", "--format", "{{.HostConfig.Memory}} {{.HostConfig.NanoCpus}}",
                args.ollama_container])
    return proc.stdout.strip()


def _limits(raw: str) -> str:
    """``"0 0"`` from docker inspect, said in words."""
    parts = (raw or "").split()
    if len(parts) != 2:
        return f"`{raw}`"
    memory, cpus = parts
    mem = "none (the host's RAM)" if memory == "0" else f"{int(memory) / 1024 ** 3:.1f} GiB"
    cpu = "none (all host CPUs)" if cpus == "0" else f"{int(cpus) / 1e9:g} CPUs"
    return f"memory {mem}, CPU {cpu}"


def write_summary(out_dir: Path, results: list[dict], meta: dict) -> None:
    (out_dir / "summary.json").write_text(json.dumps({**meta, "pairs": results}, indent=2) + "\n", encoding="utf-8")
    gib = 1024 ** 3
    lines = [
        "# Assignment 2 memory check",
        "",
        f"Run {meta['checked_at_utc']} on `{meta['host']}` by `scripts/memory_check_a2.py`. "
        f"Ollama {meta['ollama_version']}. Host RAM {meta['host_ram_gib']:.1f} GiB. Ollama container "
        f"limits (`docker inspect` HostConfig.Memory, NanoCpus): {_limits(meta['container_memory_limit'])}. "
        f"Inference settings recorded, not changed: see `ollama_env.txt`.",
        "",
        "Procedure per pair (brief, Step 2): restart the Ollama container, send "
        f"{meta['tickets_per_model']} hand-written dev tickets to each model alternately "
        "(small, large, small, large, ...) with the unchanged classification prompt, then "
        "`ollama ps` inside the container. A pair **fits** when `ollama ps` lists both models "
        "after the last call and no call after each model's first paid a reload "
        f"(`load_duration` > {meta['reload_threshold_ms']} ms).",
        "",
        "| Small model | Large model | `ollama ps` lists both | Reloads after first load | Resident size (GiB) | Verdict | Evidence |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| `{r['small']}` | `{r['large']}` | {'yes' if r['both_listed'] else 'no'} | "
            f"{r['reloads_after_first_load']} | {r['resident_total_bytes'] / gib:.2f} | "
            f"{'**fits**' if r['fits'] else '**does not fit**'} | `{r['evidence_dir']}/ollama_ps.txt` |"
        )
    lines += ["", "## `ollama ps` output, per pair", ""]
    for r in results:
        ps = (REPO_ROOT / r["evidence_dir"] / "ollama_ps.txt").read_text(encoding="utf-8").rstrip()
        lines += [f"**{r['small']} + {r['large']}**", "", "```", ps, "```", ""]
    (out_dir / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="memory_check_a2.py", description=__doc__.split("\n\n")[0])
    parser.add_argument("--small", action="append", help="small model tag (repeatable); default all three")
    parser.add_argument("--large", default=DEFAULT_LARGE)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--compose-file", type=Path, default=REPO_ROOT / "docker-compose.yml")
    parser.add_argument("--ollama-service", default="ollama")
    parser.add_argument("--ollama-container", default="ict3113-ollama")
    parser.add_argument("--tickets", type=int, default=3, help="tickets per model (default 3)")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--num-ctx", type=int, default=4096)
    parser.add_argument("--call-timeout-s", type=float, default=600)
    parser.add_argument("--reload-threshold-ms", type=float, default=1000.0)
    parser.add_argument("--out-root", type=Path, default=OUT_ROOT)
    args = parser.parse_args(argv)
    args.ollama_url = args.ollama_url.rstrip("/")
    smalls = args.small or list(DEFAULT_SMALLS)

    try:
        run(["docker", "version", "--format", "{{.Server.Version}}"], check=True, timeout=30)
        out_dir = args.out_root / stamp()
        out_dir.mkdir(parents=True, exist_ok=False)
        (out_dir / "ollama_env.txt").write_text(
            compose(args, "exec", "-T", args.ollama_service, "printenv").stdout, encoding="utf-8"
        )
        memory = host_memory()
        (out_dir / "host_memory.txt").write_text(memory, encoding="utf-8")
        limit = container_memory_limit(args)
        results = [check_pair(args, small, args.large, out_dir) for small in smalls]
    except (CannotCheck, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(f"memory_check_a2: cannot check: {exc}", file=sys.stderr)
        return 2

    total_kb = next((int(l.split()[1]) for l in memory.splitlines() if l.startswith("MemTotal:")), 0)
    meta = {
        "checked_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "host": run(["hostname"]).stdout.strip(),
        "ollama_version": results[0]["ollama_version"] if results else None,
        "host_ram_gib": total_kb / 1024 ** 2,
        "container_memory_limit": limit,
        "tickets_per_model": args.tickets,
        "reload_threshold_ms": args.reload_threshold_ms,
    }
    write_summary(out_dir, results, meta)
    print(f"\nWrote {out_dir.relative_to(REPO_ROOT)}/summary.md")
    fitting = [r for r in results if r["fits"]]
    if not fitting:
        print("memory_check_a2: NO pair fits. Tell the whole team now: the cascade is not feasible "
              "on this machine (TODO_A2.md §1.1).", file=sys.stderr)
        return 1
    print("Pairs that fit: " + ", ".join(f"{r['small']} + {r['large']}" for r in fitting))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
