#!/usr/bin/env python3
"""Record the Assignment 2 test environment once, then check it before every configuration.

Owner: Part 1 -- Yeo Kai Yuan (technical core). TODO_A2.md §1.3, last bullet.

The brief, Step 4 (Set-up): *"Before the first run, record your software
versions, model digests and Ollama settings. Check they are unchanged before
each configuration."* A silent Ollama version bump, a re-pulled model or a
changed ``OLLAMA_NUM_PARALLEL`` between two configurations would make their
comparison meaningless without anyone noticing, so this is a diff, not a
one-off capture.

What a snapshot holds
---------------------
* ``ollama_version`` -- ``GET <ollama>/api/version``.
* ``model_digests`` -- ``GET <ollama>/api/tags``, for every tag pinned in
  ``models/models.yaml`` (all four, whichever configuration is about to run),
  plus whether each equals its Assignment 1 pin. A digest that differs from
  the pin also voids the reuse of Assignment 1 accuracy (brief, Step 4: "same
  digest, prompt, Ollama version and machine").
* ``ollama_env`` -- every ``OLLAMA_*`` variable set inside the Ollama container
  (``docker compose exec -T ollama printenv``, saved to a file and passed with
  ``--ollama-env-file``): ``OLLAMA_NUM_PARALLEL``, ``OLLAMA_MAX_LOADED_MODELS``
  and anything else that would change inference. The brief forbids changing
  these between configurations.
* ``service`` -- the parts of the triage service's ``GET /health`` that must not
  change between configurations: ``prompt_hash``, ``num_ctx``, ``seed``,
  ``ollama_timeout_s``, ``uvicorn_workers``, ``threadpool_size`` and the
  category list. The model tag and service mode are *expected* to change
  between configurations and are not compared.
* ``jmeter_version`` -- passed in by the load-test script.

Usage
-----
    # once, before the first Assignment 2 run of any kind
    python scripts/a2_env_snapshot.py record \\
        --ollama-url http://<service-host>:11434 --service-url http://<service-host>:8000 \\
        --ollama-env-file /tmp/ollama.env --jmeter-version 5.6.3

    # before every configuration (scripts/run_load_test_a2.sh does this itself)
    python scripts/a2_env_snapshot.py check --json \\
        --ollama-url ... --service-url ... --ollama-env-file ... --jmeter-version ...

Exit codes: 0 recorded / unchanged; 1 changed (``check``) or the pins disagree
(``record``, after writing); 2 could not check (unreachable, missing baseline,
misuse).

Standard library only, so it runs on the load generator without the analysis
dependencies (the same reason ``scripts/run_load_test.sh`` avoids them).
"""

from __future__ import annotations

import argparse
import json
import re
import socket
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASELINE = REPO_ROOT / "docs" / "a2" / "env_baseline.json"
MODELS_YAML = REPO_ROOT / "models" / "models.yaml"

#: /health keys that must be identical for every configuration.
SERVICE_KEYS = (
    "prompt_hash",
    "num_ctx",
    "seed",
    "ollama_timeout_s",
    "uvicorn_workers",
    "threadpool_size",
    "categories",
)

#: Snapshot keys that are compared by ``check``. ``captured_*`` and ``notes`` are not.
COMPARED_KEYS = ("ollama_version", "model_digests", "ollama_env", "service", "jmeter_version")

EXIT_OK, EXIT_CHANGED, EXIT_CANNOT = 0, 1, 2


class CannotCheck(RuntimeError):
    """Something needed for the snapshot could not be read. Never guessed around."""


# ---------------------------------------------------------------------------
# Inputs
# ---------------------------------------------------------------------------

def pinned_models(path: Path = MODELS_YAML) -> tuple[dict[str, str], str | None]:
    """``({tag: pinned digest}, pinned ollama_version)`` from ``models/models.yaml``.

    Parsed with a regular expression rather than PyYAML so the script needs no
    third-party package: the file is written by ``pull_and_pin_models.sh`` in a
    fixed shape (``- tag: "..."`` then, under ``pinned:``, ``digest: "..."`` and
    ``ollama_version: "..."``).
    """
    if not path.is_file():
        raise CannotCheck(f"{path} not found; it holds the Assignment 1 model pins")
    pins: dict[str, str] = {}
    versions: set[str] = set()
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        tag = re.match(r'^\s*-\s*tag:\s*"?([^"#]+?)"?\s*$', line)
        if tag:
            current = tag.group(1).strip()
            continue
        digest = re.match(r'^\s*digest:\s*"?([^"#]+?)"?\s*$', line)
        if digest and current:
            pins[current] = _norm_digest(digest.group(1).strip())
            continue
        version = re.match(r'^\s*ollama_version:\s*"?([^"#]+?)"?\s*$', line)
        if version:
            versions.add(version.group(1).strip())
    if not pins:
        raise CannotCheck(f"no pinned digests found in {path}")
    return pins, (versions.pop() if len(versions) == 1 else None)


def _norm_digest(value: str | None) -> str | None:
    if not value:
        return None
    return value if value.startswith("sha256:") else f"sha256:{value}"


def get_json(url: str, timeout: float = 10.0) -> Any:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, socket.timeout, OSError, json.JSONDecodeError) as exc:
        raise CannotCheck(f"GET {url} failed: {exc}") from exc


def read_env_file(path: Path | None) -> dict[str, str] | None:
    """``OLLAMA_*`` variables from a ``KEY=VALUE`` file, or ``None`` if not given."""
    if path is None:
        return None
    if not path.is_file():
        raise CannotCheck(f"--ollama-env-file {path} does not exist")
    found: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if key.startswith("OLLAMA_"):
            found[key] = value
    return dict(sorted(found.items()))


# ---------------------------------------------------------------------------
# Snapshot and diff
# ---------------------------------------------------------------------------

def take_snapshot(
    *,
    ollama_url: str,
    service_url: str,
    ollama_env_file: Path | None,
    jmeter_version: str | None,
) -> dict[str, Any]:
    ollama_url = ollama_url.rstrip("/")
    service_url = service_url.rstrip("/")
    pins, pinned_version = pinned_models()

    version = get_json(f"{ollama_url}/api/version").get("version")
    tags = get_json(f"{ollama_url}/api/tags")
    served: dict[str, str | None] = {}
    for entry in tags.get("models") or []:
        if not isinstance(entry, dict):
            continue
        for name in {entry.get("name"), entry.get("model")} - {None}:
            served[name] = _norm_digest(entry.get("digest"))
    digests = {tag: served.get(tag) for tag in sorted(pins)}

    health = get_json(f"{service_url}/health")
    service = {key: health.get(key) for key in SERVICE_KEYS}

    return {
        "captured_at_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "captured_from": socket.gethostname(),
        "ollama_url": ollama_url,
        "service_url": service_url,
        "ollama_version": version,
        "model_digests": digests,
        "ollama_env": read_env_file(ollama_env_file),
        "service": service,
        "jmeter_version": jmeter_version or None,
        # Against the Assignment 1 pins: informational here, but a False is
        # exactly the condition that voids reusing Assignment 1 accuracy.
        "matches_assignment_1_pins": {
            "ollama_version": (pinned_version is not None and version == pinned_version),
            "pinned_ollama_version": pinned_version,
            "digests": {tag: digests.get(tag) == pin for tag, pin in sorted(pins.items())},
        },
    }


def differences(baseline: dict[str, Any], current: dict[str, Any]) -> list[dict[str, Any]]:
    """Every compared key whose value changed. ``None`` on either side of an
    optional input (env file, JMeter version) is reported, not skipped: a check
    that silently compared less than the baseline recorded would pass vacuously."""
    diffs: list[dict[str, Any]] = []
    for key in COMPARED_KEYS:
        before, after = baseline.get(key), current.get(key)
        if isinstance(before, dict) and isinstance(after, dict):
            for sub in sorted(set(before) | set(after)):
                if before.get(sub) != after.get(sub):
                    diffs.append({"key": f"{key}.{sub}", "baseline": before.get(sub), "current": after.get(sub)})
        elif before != after:
            diffs.append({"key": key, "baseline": before, "current": after})
    return diffs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="a2_env_snapshot.py",
        description="Record the A2 test environment once; check it is unchanged before each configuration.",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("record", "check"):
        p = sub.add_parser(name)
        p.add_argument("--ollama-url", default="http://127.0.0.1:11434")
        p.add_argument("--service-url", default="http://127.0.0.1:8000")
        p.add_argument("--ollama-env-file", type=Path, default=None,
                       help="KEY=VALUE lines from `docker compose exec -T ollama printenv`")
        p.add_argument("--jmeter-version", default=None)
        p.add_argument("--json", action="store_true", help="machine-readable result on stdout")
    sub.choices["record"].add_argument("--out", type=Path, default=DEFAULT_BASELINE)
    sub.choices["record"].add_argument(
        "--note", default="", help="free text stored in the baseline (not compared), e.g. where a value came from")
    sub.choices["record"].add_argument(
        "--force", action="store_true",
        help="overwrite an existing baseline (it is evidence: say why in docs/a2/run-log.md)")
    sub.choices["check"].add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        snapshot = take_snapshot(
            ollama_url=args.ollama_url,
            service_url=args.service_url,
            ollama_env_file=args.ollama_env_file,
            jmeter_version=args.jmeter_version,
        )
    except CannotCheck as exc:
        payload = {"ok": False, "error": str(exc)}
        print(json.dumps(payload, indent=2) if args.json else f"a2_env_snapshot: cannot check: {exc}",
              file=sys.stdout if args.json else sys.stderr)
        return EXIT_CANNOT

    if args.command == "record":
        if args.out.exists() and not args.force:
            print(f"a2_env_snapshot: {args.out} already exists and is evidence; refusing to "
                  f"overwrite it without --force.", file=sys.stderr)
            return EXIT_CANNOT
        snapshot["notes"] = args.note
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(snapshot, indent=2) + "\n", encoding="utf-8")
        pins = snapshot["matches_assignment_1_pins"]
        pins_ok = pins["ollama_version"] and all(pins["digests"].values())
        if args.json:
            print(json.dumps({"ok": pins_ok, "recorded": str(args.out), "snapshot": snapshot}, indent=2))
        else:
            print(f"Recorded {args.out}")
            print(f"  Ollama {snapshot['ollama_version']} (A1 pin {pins['pinned_ollama_version']})")
            for tag, same in pins["digests"].items():
                print(f"  {tag:<32} {snapshot['model_digests'][tag]}  {'= A1 pin' if same else 'DIFFERS FROM A1 PIN'}")
        if not pins_ok:
            print("a2_env_snapshot: WARNING: the environment differs from the Assignment 1 pins. "
                  "Reusing Assignment 1 accuracy is then not valid (brief, Step 4).", file=sys.stderr)
            return EXIT_CHANGED
        return EXIT_OK

    if not args.baseline.is_file():
        msg = (f"no baseline at {args.baseline}. Record one first, once, before the first "
               f"Assignment 2 run: python scripts/a2_env_snapshot.py record ...")
        print(json.dumps({"ok": False, "error": msg}, indent=2) if args.json else f"a2_env_snapshot: {msg}",
              file=sys.stdout if args.json else sys.stderr)
        return EXIT_CANNOT
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    diffs = differences(baseline, snapshot)
    result = {
        "ok": not diffs,
        "baseline_file": str(args.baseline),
        "baseline_captured_at_utc": baseline.get("captured_at_utc"),
        "checked_at_utc": snapshot["captured_at_utc"],
        "differences": diffs,
        "current": snapshot,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    elif diffs:
        print("a2_env_snapshot: CHANGED since the baseline -- do not measure until explained:", file=sys.stderr)
        for d in diffs:
            print(f"  {d['key']}: {d['baseline']!r} -> {d['current']!r}", file=sys.stderr)
    else:
        print(f"a2_env_snapshot: unchanged since {baseline.get('captured_at_utc')}")
    return EXIT_OK if not diffs else EXIT_CHANGED


if __name__ == "__main__":
    raise SystemExit(main())
