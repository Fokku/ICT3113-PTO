#!/usr/bin/env bash
#
# pull_and_pin_models.sh -- pull each candidate model and pin it by digest.
#
# Owner: Yeo Kai Yuan (technical core).
#
# WHAT IT DOES
#   Reads models/models.yaml, pulls each candidate into the Ollama instance that
#   will actually serve our benchmarks, reads the exact tag, digest and byte size
#   back from that instance, and writes them -- together with the pull timestamp
#   and the Ollama version -- into the `pinned:` block of each candidate.
#
# WHY IT EXISTS
#   An Ollama tag is mutable. `llama3.2:3b` can be re-published against different
#   weights, and `latest` tags move by design. A latency or accuracy number is
#   only attributable to a specific set of weights if we recorded the digest that
#   produced it, which is why the brief asks for tag AND digest and why Slide 5
#   reports both. This script is the only thing allowed to write those digests:
#   a digest typed in by hand is not evidence that anything was pulled.
#
# THE FAILURE IT IS DESIGNED TO CATCH
#   If a tag now resolves to a DIFFERENT digest than the one already pinned, the
#   script refuses to overwrite the pin and exits 4. That situation is exactly
#   the one that silently invalidates results: every run already recorded under
#   the old digest becomes incomparable with anything measured afterwards, and
#   the numbers would still look perfectly plausible in the results table.
#   Overriding the refusal needs --allow-repin and means re-running the affected
#   benchmarks.
#
# TRANSPORTS
#   Two, because the Ollama backend may be a container we manage or a host
#   somebody else manages:
#     docker -- `docker compose exec -T <service> ollama pull <tag>`, used when
#               --ollama-url names the compose service (e.g. http://ollama:11434),
#               a hostname that only resolves inside the compose network.
#     api    -- `POST <url>/api/pull`, used for anything reachable over HTTP,
#               including an external Ollama host.
#   The script says which one it chose and why, every run.
#
#   Digests and byte sizes are ALWAYS read back over HTTP from /api/tags, on both
#   transports. `ollama list` truncates the digest to twelve characters and prints
#   a rounded human size, and neither is good enough to pin: /api/tags is the only
#   source of the full digest and the exact byte count. For the docker transport
#   the script therefore also needs one HTTP-reachable address for the same
#   instance, which it finds from `docker compose port` or takes from
#   --readback-url.
#
# NOT PART OF THE SYSTEM UNDER TEST
#   This is a setup script. It is never running while we measure, so the
#   "A2 candidate" convention used in the service does not apply here. Models are
#   pulled one at a time on purpose: the progress output stays readable, and a
#   single large download is easier to diagnose than four interleaved ones.
#
# EXIT CODES
#   0  every requested candidate is pinned and consistent
#   1  usage error
#   2  environment problem (missing file, no Python, no PyYAML, no docker)
#   3  the Ollama instance could not be reached
#   4  a tag resolved to a digest that disagrees with the existing pin
#   5  a pull failed
#
# USAGE: see usage() below, or run with --help.

set -euo pipefail

# ---------------------------------------------------------------------------
# Locate the repository so the script works when invoked from any directory
# (the contract requires this: the run scripts and the playbooks call it by
# relative path from several places).
# ---------------------------------------------------------------------------
SCRIPT_PATH="${BASH_SOURCE[0]}"
SCRIPT_DIR="$(cd -- "$(dirname -- "$SCRIPT_PATH")" > /dev/null 2>&1 && pwd -P)"
REPO_ROOT="$(cd -- "$SCRIPT_DIR/.." > /dev/null 2>&1 && pwd -P)"

# ---------------------------------------------------------------------------
# Defaults. OLLAMA_BASE_URL is the same variable the service reads (see the
# configuration table in the README), so pointing the service at an external
# Ollama automatically points this script at the same place.
# ---------------------------------------------------------------------------
MODELS_FILE="$REPO_ROOT/models/models.yaml"
OLLAMA_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"
READBACK_URL=""                 # derived for the docker transport unless given
COMPOSE_SERVICE="ollama"        # the service name in docker-compose.yml
TRANSPORT="auto"                # auto | docker | api
DRY_RUN=0
MODEL_FILTER=""
ALLOW_REPIN=0
HTTP_TIMEOUT_S=60               # per-request timeout for /api/tags, /api/version
PULL_TIMEOUT_S=7200             # per-read timeout while streaming a pull

usage() {
  cat <<'USAGE'
Usage: scripts/pull_and_pin_models.sh [options]

Pull every candidate model listed in models/models.yaml into the Ollama instance
that will serve our benchmarks, then pin each one by writing the exact digest,
byte size, pull timestamp and Ollama version back into that file.

Options:
  --models-file PATH     Pin file to read and update.
                         (default: <repo>/models/models.yaml)
  --ollama-url URL       Base URL of the Ollama instance to pull into.
                         (default: $OLLAMA_BASE_URL, else http://ollama:11434)
  --readback-url URL     HTTP address of the SAME instance, used to read digests
                         and sizes from /api/tags. Only needed with the docker
                         transport when the port is not discoverable; otherwise
                         it is derived from --ollama-url or `docker compose port`.
  --transport MODE       auto | docker | api.  auto picks docker when
                         --ollama-url names the compose service, api otherwise.
                         (default: auto)
  --compose-service NAME Compose service running Ollama. (default: ollama)
  --model TAG            Act on this one candidate only; must match a tag in the
                         pin file exactly (e.g. --model llama3.2:3b).
  --dry-run              Print what would be pulled and pinned, then stop.
                         Contacts nothing: no Ollama, no Docker, no registry, and
                         the pin file is not modified.
  --allow-repin          Permit overwriting an existing pin whose digest no longer
                         matches. USE ONLY DELIBERATELY: every benchmark run
                         recorded under the old digest must then be re-run, because
                         it is no longer comparable with anything measured after.
  --http-timeout S       Timeout for /api/tags and /api/version. (default: 60)
  --pull-timeout S       Per-read timeout while streaming a pull. (default: 7200)
  -h, --help             Show this help and exit.

Examples:
  # Check the plan first. Safe anywhere, contacts nothing.
  scripts/pull_and_pin_models.sh --dry-run

  # Dockerised Ollama managed by our compose file (the usual case).
  scripts/pull_and_pin_models.sh --ollama-url http://ollama:11434

  # An Ollama host somebody else runs, or one reached over the published port.
  scripts/pull_and_pin_models.sh --transport api --ollama-url http://10.0.0.21:11434

  # One model only, after adding it to models/models.yaml.
  scripts/pull_and_pin_models.sh --model qwen2.5:7b

Exit codes: 0 pinned, 1 usage, 2 environment, 3 Ollama unreachable,
            4 digest disagrees with the existing pin, 5 pull failed.
USAGE
}

# die <message> [exit-code]. Only $1 is printed: passing the code through "$*"
# would append it to the message, which is exactly the sort of small wrongness a
# marker notices.
die() { printf '%s\n' "$1" >&2; exit "${2:-1}"; }

# Long-option parsing. Every option takes its value as a separate argument so
# that a tag containing ':' or '=' cannot be misparsed.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --models-file)     [[ $# -ge 2 ]] || die "--models-file needs a value" 1; MODELS_FILE="$2"; shift 2 ;;
    --ollama-url)      [[ $# -ge 2 ]] || die "--ollama-url needs a value" 1; OLLAMA_URL="$2"; shift 2 ;;
    --readback-url)    [[ $# -ge 2 ]] || die "--readback-url needs a value" 1; READBACK_URL="$2"; shift 2 ;;
    --transport)       [[ $# -ge 2 ]] || die "--transport needs a value" 1; TRANSPORT="$2"; shift 2 ;;
    --compose-service) [[ $# -ge 2 ]] || die "--compose-service needs a value" 1; COMPOSE_SERVICE="$2"; shift 2 ;;
    --model)           [[ $# -ge 2 ]] || die "--model needs a value" 1; MODEL_FILTER="$2"; shift 2 ;;
    --http-timeout)    [[ $# -ge 2 ]] || die "--http-timeout needs a value" 1; HTTP_TIMEOUT_S="$2"; shift 2 ;;
    --pull-timeout)    [[ $# -ge 2 ]] || die "--pull-timeout needs a value" 1; PULL_TIMEOUT_S="$2"; shift 2 ;;
    --dry-run)         DRY_RUN=1; shift ;;
    --allow-repin)     ALLOW_REPIN=1; shift ;;
    -h|--help)         usage; exit 0 ;;
    *)                 usage >&2; die "unknown option: $1" 1 ;;
  esac
done

case "$TRANSPORT" in auto|docker|api) ;; *) die "--transport must be auto, docker or api (got '$TRANSPORT')" 1 ;; esac
[[ -f "$MODELS_FILE" ]] || die "pin file not found: $MODELS_FILE" 2

# ---------------------------------------------------------------------------
# Python. The contract requires the repository virtualenv, because the YAML is
# edited with PyYAML rather than sed: sed cannot tell a `digest:` inside a
# candidate from one inside a comment, and a half-edited pin file is worse than
# no pin file at all.
# ---------------------------------------------------------------------------
PY="$REPO_ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || true)"
  [[ -n "$PY" ]] || die "no Python found. Expected $REPO_ROOT/.venv/bin/python (see README, Tooling)." 2
  printf 'WARNING: %s/.venv/bin/python not found; falling back to %s\n' "$REPO_ROOT" "$PY" >&2
fi
"$PY" - <<'PYCHECK' || die "PyYAML is not importable by $PY. Create the virtualenv: python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt" 2
import sys
try:
    import yaml  # noqa: F401
except Exception as exc:  # pragma: no cover - environment problem, reported above
    print(f"import yaml failed: {exc}", file=sys.stderr)
    sys.exit(1)
PYCHECK

# ---------------------------------------------------------------------------
# The embedded Python toolbox. It is written to a temporary file once and then
# invoked with subcommands, rather than being repeated as several heredocs, so
# that there is exactly one copy of the YAML-patching logic to review.
# ---------------------------------------------------------------------------
TOOLBOX="$(mktemp -t pinmodels.XXXXXX.py)"
cleanup() { rm -f "$TOOLBOX"; }
trap cleanup EXIT

cat > "$TOOLBOX" <<'PYTOOL'
"""Helpers for scripts/pull_and_pin_models.sh. Not a general-purpose module.

Subcommands
    plan     <models_file>                       validate the pin file, emit TSV
    version  <base_url> <timeout>                print the Ollama version
    resolve  <base_url> <tag> <timeout>          print "<digest>\t<size_bytes>"
    pull     <base_url> <tag> <timeout>          stream POST /api/pull
    pin      <models_file> <tag> <digest> <pulled_at> <size_bytes> <version>

Only the standard library is used for HTTP so that the script needs nothing
beyond PyYAML, and so that a missing curl cannot stop a pull.

Exit codes mirror the shell script's: 2 environment/parse, 3 unreachable,
5 pull failed, 6 tag not present on the instance.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

#: Layout version of models/models.yaml that this script understands. A bump in
#: the file means its shape changed, and patching it blind could corrupt a pin.
SUPPORTED_SCHEMA_VERSION = 1

#: Human-written keys every candidate must carry. The script never writes these;
#: it validates them so that a candidate added in a hurry is caught here rather
#: than on Slide 5.
REQUIRED_CANDIDATE_KEYS = ("tag", "size_class", "licence", "url", "rationale")

#: The only keys the script is allowed to write, in the order they appear.
PINNED_KEYS = ("digest", "pulled_at", "size_bytes", "ollama_version")


def fail(message: str, code: int = 2) -> "NoReturn":  # type: ignore[valid-type]
    """Print to stderr and exit. Every failure in this file is loud."""
    print(f"pull_and_pin_models: {message}", file=sys.stderr)
    raise SystemExit(code)


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------
def _request(url: str, timeout: float, payload: bytes | None = None) -> Any:
    """Open ``url``, returning the response object. Caller closes it."""
    headers = {"Accept": "application/json"}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers,
                                 method="POST" if payload is not None else "GET")
    return urllib.request.urlopen(req, timeout=timeout)  # noqa: S310 - fixed http scheme


def get_json(base_url: str, path: str, timeout: float) -> dict:
    """GET ``path`` and decode the JSON body, or exit 3 if unreachable."""
    url = base_url.rstrip("/") + path
    try:
        with _request(url, timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        fail(f"GET {url} returned HTTP {exc.code}", 3)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"GET {url} failed: {exc}", 3)
    except json.JSONDecodeError as exc:
        fail(f"GET {url} did not return JSON: {exc}", 3)


def normalise_digest(raw: str) -> str:
    """Return the digest in the ``sha256:<hex>`` form we log and pin.

    ``/api/tags`` has reported the digest both bare and prefixed depending on
    the Ollama version, and ``MODEL_DIGEST`` in our configuration is documented
    as the prefixed form (it is copied verbatim into every log line), so the two
    must not be allowed to drift apart.
    """
    digest = raw.strip()
    if not digest:
        fail("the instance reported an empty digest", 3)
    if ":" not in digest:
        digest = f"sha256:{digest}"
    algorithm, _, hexdigest = digest.partition(":")
    if algorithm != "sha256" or not re.fullmatch(r"[0-9a-f]{64}", hexdigest):
        fail(f"unexpected digest form {raw!r}; expected sha256 and 64 hex characters", 3)
    return digest


# --------------------------------------------------------------------------
# Subcommand: plan
# --------------------------------------------------------------------------
def cmd_plan(models_file: str) -> int:
    """Validate the pin file and print one TSV row per candidate.

    Columns: tag, size_class, licence, pinned_digest, pulled_at, size_bytes,
    ollama_version, name. Empty values are printed as ``-`` so that the shell
    can read the row with a plain ``read``.
    """
    path = Path(models_file)
    try:
        document = yaml_safe_load(path)
    except Exception as exc:  # noqa: BLE001 - reported verbatim
        fail(f"{path} is not valid YAML: {exc}")

    if not isinstance(document, dict):
        fail(f"{path}: expected a mapping at the top level, found {type(document).__name__}")

    version = document.get("schema_version")
    if version != SUPPORTED_SCHEMA_VERSION:
        fail(f"{path}: schema_version is {version!r}, this script understands "
             f"{SUPPORTED_SCHEMA_VERSION}. Update the script before pinning.")

    candidates = document.get("candidates")
    if not isinstance(candidates, list) or not candidates:
        fail(f"{path}: 'candidates' must be a non-empty list")

    seen: set[str] = set()
    rows: list[str] = []
    for index, candidate in enumerate(candidates):
        where = f"{path}: candidates[{index}]"
        if not isinstance(candidate, dict):
            fail(f"{where}: expected a mapping")
        missing = [key for key in REQUIRED_CANDIDATE_KEYS if not candidate.get(key)]
        if missing:
            fail(f"{where}: missing or empty required field(s): {', '.join(missing)}")
        tag = str(candidate["tag"])
        if tag in seen:
            fail(f"{where}: duplicate tag {tag!r}. Tags must be unique; the pin "
                 f"patcher addresses candidates by tag.")
        seen.add(tag)

        pinned = candidate.get("pinned")
        if not isinstance(pinned, dict):
            fail(f"{where} ({tag}): a 'pinned:' mapping is required, pre-filled with nulls")
        unknown = sorted(set(pinned) - set(PINNED_KEYS))
        if unknown:
            fail(f"{where} ({tag}): unexpected key(s) in 'pinned': {', '.join(unknown)}")
        absent = [key for key in PINNED_KEYS if key not in pinned]
        if absent:
            fail(f"{where} ({tag}): 'pinned' is missing key(s): {', '.join(absent)}")

        def cell(value: Any) -> str:
            return "-" if value in (None, "") else str(value)

        rows.append("\t".join((
            tag,
            cell(candidate.get("size_class")),
            cell(candidate.get("licence")),
            cell(pinned.get("digest")),
            cell(pinned.get("pulled_at")),
            cell(pinned.get("size_bytes")),
            cell(pinned.get("ollama_version")),
            cell(candidate.get("name") or tag),
        )))

    print("\n".join(rows))
    return 0


def yaml_safe_load(path: Path) -> Any:
    """Load YAML from ``path``. Imported lazily so ``--help`` needs no PyYAML."""
    import yaml

    with path.open("r", encoding="utf-8") as handle:
        return yaml.safe_load(handle)


# --------------------------------------------------------------------------
# Subcommand: version / resolve / pull
# --------------------------------------------------------------------------
def cmd_version(base_url: str, timeout: float) -> int:
    """Print the Ollama version string reported by GET /api/version."""
    body = get_json(base_url, "/api/version", timeout)
    version = body.get("version")
    if not version:
        fail(f"{base_url}/api/version did not report a version: {body!r}", 3)
    print(str(version))
    return 0


def cmd_resolve(base_url: str, tag: str, timeout: float) -> int:
    """Print "<digest>\t<size_bytes>" for ``tag`` as the instance reports it.

    Exits 6 when the tag is not present locally, which the shell treats as
    "needs pulling" rather than as an error.
    """
    body = get_json(base_url, "/api/tags", timeout)
    models = body.get("models")
    if not isinstance(models, list):
        fail(f"{base_url}/api/tags did not return a 'models' list: {body!r}", 3)

    for entry in models:
        if not isinstance(entry, dict):
            continue
        # Ollama has reported the tag under both 'name' and 'model'; accept either
        # so the script is not tied to one server version.
        names = {str(entry.get(key)) for key in ("name", "model") if entry.get(key)}
        if tag in names:
            digest = normalise_digest(str(entry.get("digest", "")))
            size = entry.get("size")
            if not isinstance(size, int):
                fail(f"/api/tags reported a non-integer size for {tag}: {size!r}", 3)
            print(f"{digest}\t{size}")
            return 0
    return 6


def cmd_pull(base_url: str, tag: str, timeout: float) -> int:
    """Stream POST /api/pull, echoing each distinct status to stderr.

    The request is streamed rather than buffered because a multi-gigabyte pull
    with ``stream: false`` leaves the socket silent for its whole duration, which
    any sane read timeout would then kill. Streaming also gives the operator
    something to watch, which matters when a 4.7 GB download is normal.
    """
    url = base_url.rstrip("/") + "/api/pull"
    # 'model' is the documented field; 'name' was the field older servers read.
    # Sending both costs nothing and keeps the script working against an Ollama
    # host whose version we do not control.
    payload = json.dumps({"model": tag, "name": tag, "stream": True}).encode("utf-8")

    last_status = ""
    final_status = ""
    try:
        with _request(url, timeout, payload) as response:
            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    print(f"  (unparsed pull output) {line[:200]}", file=sys.stderr)
                    continue
                if "error" in event:
                    fail(f"Ollama refused to pull {tag}: {event['error']}", 5)
                status = str(event.get("status", ""))
                if status and status != last_status:
                    print(f"  {tag}: {status}", file=sys.stderr, flush=True)
                    last_status = status
                if status:
                    final_status = status
    except urllib.error.HTTPError as exc:
        fail(f"POST {url} returned HTTP {exc.code} for {tag}", 5)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        fail(f"POST {url} failed for {tag}: {exc}", 5)

    if final_status != "success":
        fail(f"pull of {tag} ended with status {final_status!r}, not 'success'", 5)
    return 0


# --------------------------------------------------------------------------
# Subcommand: pin
# --------------------------------------------------------------------------
def cmd_pin(models_file: str, tag: str, digest: str, pulled_at: str,
            size_bytes: str, ollama_version: str) -> int:
    """Rewrite one candidate's four ``pinned:`` scalars, in place, by line.

    PyYAML cannot round-trip comments, and this file is more than half comments:
    the header explains that a changed digest invalidates earlier runs, and each
    candidate carries a rationale that a marker reads. Dumping the parsed
    document back out would delete all of it. So the file is patched as text --
    only the four scalar lines inside the addressed candidate's ``pinned:`` block
    are rewritten, and every other byte is left exactly as the human wrote it.

    The result is re-parsed before it replaces the original, so a patch that
    produced invalid YAML, or that failed to land the values, aborts without
    touching the file on disk.
    """
    import yaml

    path = Path(models_file)
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines(keepends=True)

    try:
        size_value = int(size_bytes)
    except ValueError:
        fail(f"size_bytes must be an integer, got {size_bytes!r}")
    if size_value <= 0:
        fail(f"size_bytes must be positive, got {size_value}")

    # Locate the list items by their `- tag:` line. Candidate tags are unique
    # (cmd_plan enforces it), so the tag alone addresses a candidate.
    item_re = re.compile(r"^(\s*)-\s+tag:\s*(.+?)\s*$")
    starts: list[tuple[int, int, str]] = []
    for number, line in enumerate(lines):
        match = item_re.match(line)
        if match:
            raw_tag = match.group(2).strip().strip("'\"")
            starts.append((number, len(match.group(1)), raw_tag))

    target = next((entry for entry in starts if entry[2] == tag), None)
    if target is None:
        fail(f"{path}: no candidate with tag {tag!r} to pin")
    start_line, item_indent, _ = target

    # The candidate ends at the next list item of the same or lesser indent, or
    # at the first non-blank line indented no further than the item marker.
    end_line = len(lines)
    for number in range(start_line + 1, len(lines)):
        line = lines[number]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= item_indent and not line.lstrip().startswith("#"):
            end_line = number
            break

    # Find `pinned:` and then the four scalars beneath it.
    pinned_line = None
    pinned_indent = -1
    for number in range(start_line, end_line):
        match = re.match(r"^(\s+)pinned:\s*$", lines[number])
        if match and len(match.group(1)) > item_indent:
            pinned_line, pinned_indent = number, len(match.group(1))
            break
    if pinned_line is None:
        fail(f"{path}: candidate {tag!r} has no 'pinned:' block to write into")

    replacements = {
        "digest": json.dumps(digest),
        "pulled_at": json.dumps(pulled_at),
        "size_bytes": str(size_value),
        "ollama_version": json.dumps(ollama_version),
    }
    written: set[str] = set()
    for number in range(pinned_line + 1, end_line):
        line = lines[number]
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent <= pinned_indent:
            break
        match = re.match(r"^(\s+)(digest|pulled_at|size_bytes|ollama_version):\s*(.*?)\s*$", line)
        if not match:
            continue
        key = match.group(2)
        newline = "\n" if line.endswith("\n") else ""
        lines[number] = f"{match.group(1)}{key}: {replacements[key]}{newline}"
        written.add(key)

    missing = [key for key in PINNED_KEYS if key not in written]
    if missing:
        fail(f"{path}: candidate {tag!r} has no line for pinned key(s) "
             f"{', '.join(missing)}. Restore the four-key 'pinned:' block and retry.")

    patched = "".join(lines)

    # Belt and braces: the patched text must parse, and must contain exactly the
    # values we meant to write, before it is allowed to replace the file.
    try:
        document = yaml.safe_load(patched)
    except Exception as exc:  # noqa: BLE001
        fail(f"patching {tag!r} produced invalid YAML, file left unchanged: {exc}")
    candidate = next((entry for entry in document.get("candidates", [])
                      if isinstance(entry, dict) and entry.get("tag") == tag), None)
    if candidate is None:
        fail(f"patched {path} no longer contains candidate {tag!r}; file left unchanged")
    expected = {"digest": digest, "pulled_at": pulled_at,
                "size_bytes": size_value, "ollama_version": ollama_version}
    actual = {key: candidate.get("pinned", {}).get(key) for key in expected}
    if actual != expected:
        fail(f"verification failed for {tag!r}: wrote {expected!r} but re-read "
             f"{actual!r}; file left unchanged")

    # Atomic replace, so an interrupted write cannot leave a half-written pin file.
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(patched, encoding="utf-8")
    temporary.replace(path)
    return 0


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        fail("no subcommand given (plan|version|resolve|pull|pin)")
    command, args = argv[1], argv[2:]
    if command == "plan":
        return cmd_plan(*args)
    if command == "version":
        return cmd_version(args[0], float(args[1]))
    if command == "resolve":
        return cmd_resolve(args[0], args[1], float(args[2]))
    if command == "pull":
        return cmd_pull(args[0], args[1], float(args[2]))
    if command == "pin":
        return cmd_pin(*args)
    fail(f"unknown subcommand {command!r}")


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
PYTOOL

py_tool() { "$PY" "$TOOLBOX" "$@"; }

# ---------------------------------------------------------------------------
# Read and validate the pin file. This happens before any transport decision so
# that a malformed pin file is reported without any network access at all.
# ---------------------------------------------------------------------------
PLAN="$(py_tool plan "$MODELS_FILE")" || exit 2

# ---------------------------------------------------------------------------
# Decide the transport and say why. In --dry-run the decision is made purely
# from the URL, so that a dry run contacts nothing whatsoever -- not Ollama, and
# not the Docker daemon either.
# ---------------------------------------------------------------------------
url_host() {
  # Strip scheme, then userinfo, then path, then port. Good enough for the
  # http://host:port URLs this project uses; no general URL parsing intended.
  local url="$1"
  url="${url#*://}"
  url="${url#*@}"
  url="${url%%/*}"
  url="${url%%\?*}"
  printf '%s' "${url%%:*}"
}

OLLAMA_HOST="$(url_host "$OLLAMA_URL")"
TRANSPORT_REASON=""
CHOSEN_TRANSPORT="$TRANSPORT"

if [[ "$TRANSPORT" == "auto" ]]; then
  if [[ "$OLLAMA_HOST" == "$COMPOSE_SERVICE" ]]; then
    CHOSEN_TRANSPORT="docker"
    TRANSPORT_REASON="--ollama-url host '$OLLAMA_HOST' is the compose service name, which only resolves inside the compose network, so the pull must run inside the container"
  else
    CHOSEN_TRANSPORT="api"
    TRANSPORT_REASON="--ollama-url host '$OLLAMA_HOST' is an ordinary address reachable over HTTP from here"
  fi
else
  TRANSPORT_REASON="forced by --transport $TRANSPORT"
fi

printf '=== pull_and_pin_models ===\n'
printf 'repo root      : %s\n' "$REPO_ROOT"
printf 'pin file       : %s\n' "$MODELS_FILE"
printf 'ollama url     : %s\n' "$OLLAMA_URL"
printf 'transport      : %s (%s)\n' "$CHOSEN_TRANSPORT" "$TRANSPORT_REASON"
[[ -n "$MODEL_FILTER" ]] && printf 'model filter   : %s\n' "$MODEL_FILTER"
[[ "$ALLOW_REPIN" -eq 1 ]] && printf 'allow repin    : YES -- an existing pin may be overwritten\n'
printf 'mode           : %s\n' "$([[ "$DRY_RUN" -eq 1 ]] && echo 'DRY RUN (contacts nothing, writes nothing)' || echo 'live')"
printf '\n'

# ---------------------------------------------------------------------------
# Apply --model and report the plan.
# ---------------------------------------------------------------------------
SELECTED=""
while IFS=$'\t' read -r tag size_class licence pin_digest pin_pulled_at pin_size pin_version name; do
  [[ -n "$tag" ]] || continue
  if [[ -n "$MODEL_FILTER" && "$tag" != "$MODEL_FILTER" ]]; then
    continue
  fi
  SELECTED+="$tag"$'\t'"$size_class"$'\t'"$licence"$'\t'"$pin_digest"$'\t'"$name"$'\n'
done <<< "$PLAN"

if [[ -z "$SELECTED" ]]; then
  {
    printf 'No candidate matched.\n'
    if [[ -n "$MODEL_FILTER" ]]; then
      printf "  --model '%s' does not appear in %s. Tags present:\n" "$MODEL_FILTER" "$MODELS_FILE"
      printf '%s\n' "$PLAN" | cut -f1 | sed 's/^/    /'
    fi
  } >&2
  exit 1
fi

printf 'Candidates in scope:\n'
printf '%s' "$SELECTED" | while IFS=$'\t' read -r tag size_class licence pin_digest name; do
  if [[ "$pin_digest" == "-" ]]; then
    printf '  %-16s %-8s not yet pinned      %s\n' "$tag" "$size_class" "$name"
  else
    printf '  %-16s %-8s pinned %s  %s\n' "$tag" "$size_class" "${pin_digest:0:19}..." "$name"
  fi
  printf '  %-16s %-8s licence: %s\n' '' '' "$licence"
done
printf '\n'

if [[ "$DRY_RUN" -eq 1 ]]; then
  # The read-back address is only DERIVED on a live run (for the docker transport
  # it comes from `docker compose port`), so describe it rather than assert it --
  # a dry run must not consult Docker any more than it consults Ollama.
  if [[ -n "$READBACK_URL" ]]; then
    dry_readback="$READBACK_URL"
  elif [[ "$CHOSEN_TRANSPORT" == "api" ]]; then
    dry_readback="${OLLAMA_URL%/}"
  else
    dry_readback="<published port of compose service '$COMPOSE_SERVICE', resolved at run time, or --readback-url>"
  fi
  cat <<DRYRUN
DRY RUN -- nothing was pulled, nothing was contacted and $MODELS_FILE was not modified.

What a live run would do, for each candidate above, in order:
  1. GET $dry_readback/api/version  and record the version alongside the pin.
  2. GET $dry_readback/api/tags     to see whether the tag is already present
     locally, and with which digest. Digests and byte sizes always come from
     /api/tags, on both transports, because \`ollama list\` truncates the digest
     to twelve characters and rounds the size.
  3. If the candidate is ALREADY PINNED and the local digest matches the pin:
     skip the pull entirely and leave the file untouched. The pull is skipped
     deliberately -- if the tag has since been re-published upstream, pulling
     would replace the pinned weights on disk before we could compare, and every
     result already recorded under that digest would become unreproducible.
  4. If the candidate is ALREADY PINNED and the digest DISAGREES: stop with exit
     code 4 and change nothing. That is the failure this script exists to catch.
  5. If the candidate is NOT yet pinned: pull it --
DRYRUN
  if [[ "$CHOSEN_TRANSPORT" == "docker" ]]; then
    printf '       docker compose exec -T %s ollama pull <tag>\n' "$COMPOSE_SERVICE"
    printf '     (chosen transport: docker; %s)\n' "$TRANSPORT_REASON"
  else
    printf '       POST %s/api/pull  {"model": "<tag>", "stream": true}\n' "${OLLAMA_URL%/}"
    printf '     (chosen transport: api; %s)\n' "$TRANSPORT_REASON"
  fi
  cat <<'DRYRUN2'
     then read the exact digest and byte size back from /api/tags and write
     digest, pulled_at (UTC, seconds precision), size_bytes and ollama_version
     into that candidate's `pinned:` block. Human-written fields, comments and
     formatting are left exactly as they are.

Re-run without --dry-run on the machine that will serve the benchmarks.
DRYRUN2
  exit 0
fi

# ===========================================================================
# Live run from here. Everything above this line is free of network access.
# ===========================================================================

# ---------------------------------------------------------------------------
# Establish the address used to READ digests back. Both transports need one:
# /api/tags is the only source of a full digest and an exact byte count.
# ---------------------------------------------------------------------------
if [[ -z "$READBACK_URL" ]]; then
  if [[ "$CHOSEN_TRANSPORT" == "api" ]]; then
    READBACK_URL="$OLLAMA_URL"
  else
    command -v docker > /dev/null 2>&1 || die "the docker transport needs the docker CLI on PATH. Use --transport api --ollama-url http://<host>:11434 instead." 2
    # `docker compose port` prints the published address, e.g. 0.0.0.0:11434.
    # Bind-all addresses are rewritten to the loopback address, which is what we
    # can actually connect to from here.
    published="$(cd -- "$REPO_ROOT" && docker compose port "$COMPOSE_SERVICE" 11434 2>/dev/null || true)"
    if [[ -n "$published" ]]; then
      published="${published//0.0.0.0/127.0.0.1}"
      published="${published//\[::\]/127.0.0.1}"
      READBACK_URL="http://$published"
      printf 'readback url   : %s (from `docker compose port %s 11434`)\n\n' "$READBACK_URL" "$COMPOSE_SERVICE"
    else
      READBACK_URL="http://127.0.0.1:11434"
      printf 'readback url   : %s (guessed; `docker compose port %s 11434` said nothing)\n\n' "$READBACK_URL" "$COMPOSE_SERVICE"
    fi
  fi
fi

# A version call doubles as the reachability check, and its answer is recorded
# with every pin: the Ollama version is part of what makes a run reproducible.
OLLAMA_VERSION="$(py_tool version "$READBACK_URL" "$HTTP_TIMEOUT_S")" || {
  {
    printf '\nCannot reach Ollama at %s.\n' "$READBACK_URL"
    printf 'Digests and byte sizes are read from /api/tags, so an HTTP address for the\n'
    printf 'instance is required even when pulling through docker compose exec. Try:\n'
    printf '  * start it:            docker compose up -d %s\n' "$COMPOSE_SERVICE"
    printf '  * name the address:    --readback-url http://<host>:11434\n'
    printf '  * or pull over HTTP:   --transport api --ollama-url http://<host>:11434\n'
  } >&2
  exit 3
}
printf 'ollama version : %s\n\n' "$OLLAMA_VERSION"

if [[ "$CHOSEN_TRANSPORT" == "docker" ]]; then
  command -v docker > /dev/null 2>&1 || die "the docker transport needs the docker CLI on PATH." 2
  (cd -- "$REPO_ROOT" && docker compose ps --services --filter status=running 2>/dev/null | grep -qx "$COMPOSE_SERVICE") || \
    die "compose service '$COMPOSE_SERVICE' is not running. Start it with 'docker compose up -d $COMPOSE_SERVICE', or use --transport api." 2
fi

# ---------------------------------------------------------------------------
# resolve_tag <tag> -- ask the instance what it currently has for <tag>.
#
# On success it prints "<digest>\t<size_bytes>" and returns 0; it returns 1 when
# the tag is simply not installed yet (which is normal, not an error); and it
# returns the helper's own exit code for anything else, which callers treat as
# fatal. It must RETURN rather than exit, because every caller invokes it inside
# a command substitution -- that is a subshell, so an exit here would only kill
# the subshell and the caller would mistake a transport failure for "absent".
# ---------------------------------------------------------------------------
resolve_tag() {
  local tag="$1" out rc
  set +e
  out="$(py_tool resolve "$READBACK_URL" "$tag" "$HTTP_TIMEOUT_S")"
  rc=$?
  set -e
  if [[ "$rc" -eq 0 ]]; then
    printf '%s' "$out"
    return 0
  fi
  if [[ "$rc" -eq 6 ]]; then
    return 1
  fi
  return "$rc"
}

pull_tag() {
  local tag="$1"
  if [[ "$CHOSEN_TRANSPORT" == "docker" ]]; then
    printf '  pulling via: docker compose exec -T %s ollama pull %s\n' "$COMPOSE_SERVICE" "$tag"
    (cd -- "$REPO_ROOT" && docker compose exec -T "$COMPOSE_SERVICE" ollama pull "$tag") || {
      printf 'pull of %s failed inside container %s.\n' "$tag" "$COMPOSE_SERVICE" >&2
      exit 5
    }
  else
    printf '  pulling via: POST %s/api/pull  {"model": "%s"}\n' "${OLLAMA_URL%/}" "$tag"
    py_tool pull "$OLLAMA_URL" "$tag" "$PULL_TIMEOUT_S" || exit 5
  fi
}

PULLED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

n_pinned=0
n_unchanged=0
SUMMARY=""

while IFS=$'\t' read -r tag size_class licence pin_digest name; do
  [[ -n "$tag" ]] || continue
  printf -- '--- %s (%s) ---\n' "$tag" "$size_class"

  # Step 1: what does the instance have right now? Note the explicit rc capture:
  # `if x="$(f)"` would collapse "tag absent" and "instance unreachable" into the
  # same false branch, and silently pinning after a failed lookup is unthinkable.
  set +e
  local_line="$(resolve_tag "$tag")"
  resolve_rc=$?
  set -e
  case "$resolve_rc" in
    0)
      local_digest="${local_line%%$'\t'*}"
      local_size="${local_line##*$'\t'}"
      printf '  present locally: %s (%s bytes)\n' "$local_digest" "$local_size"
      ;;
    1)
      local_digest=""
      local_size=""
      printf '  not present on this instance yet\n'
      ;;
    *)
      printf 'could not query %s/api/tags for %s (exit %d). Nothing changed.\n' \
        "$READBACK_URL" "$tag" "$resolve_rc" >&2
      exit "$resolve_rc"
      ;;
  esac

  # Step 2: an existing pin constrains everything that follows.
  if [[ "$pin_digest" != "-" ]]; then
    if [[ -n "$local_digest" && "$local_digest" == "$pin_digest" ]]; then
      # Idempotent path: already pinned, already present, digests agree. The
      # pull is skipped on purpose -- see the message.
      printf '  already pinned and the local digest matches. Pull skipped, pin file untouched.\n'
      printf '    (Skipping the pull is deliberate: if the tag has been re-published\n'
      printf '     upstream, pulling would overwrite the pinned weights on disk and every\n'
      printf '     result recorded under this digest would stop being reproducible.)\n'
      n_unchanged=$((n_unchanged + 1))
      SUMMARY+="  $tag"$'\t'"unchanged"$'\t'"$pin_digest"$'\n'
      printf '\n'
      continue
    fi
    if [[ -n "$local_digest" && "$local_digest" != "$pin_digest" && "$ALLOW_REPIN" -eq 0 ]]; then
      {
        printf '\n'
        printf '*** DIGEST MISMATCH for %s -- STOPPING. Nothing was changed. ***\n' "$tag"
        printf '\n'
        printf '  pinned in %s : %s\n' "$MODELS_FILE" "$pin_digest"
        printf '  present on %s : %s\n' "$READBACK_URL" "$local_digest"
        if [[ "${pin_digest:0:19}" == "${local_digest:0:19}" ]]; then
          printf '  (the first 12 hex characters agree, so this may be a hand-edited short\n'
          printf '   digest rather than a real change. Check the pin file before overriding.)\n'
        fi
        printf '\n'
        printf '  WHY THIS IS FATAL: the tag %s no longer names the weights we pinned.\n' "$tag"
        printf '  Any benchmark or accuracy run already recorded under %s\n' "$pin_digest"
        printf '  cannot be compared with, or pooled with, anything measured against the\n'
        printf '  digest now installed -- and the numbers would still look entirely\n'
        printf '  plausible in the results table, which is exactly why this script refuses\n'
        printf '  to rewrite the pin quietly. Overwriting it would silently invalidate our\n'
        printf '  results.\n'
        printf '\n'
        printf '  Choose one, deliberately:\n'
        printf '    (a) Keep the pin. Restore the pinned weights on the Ollama host and\n'
        printf '        re-run this script; your existing results stay valid.\n'
        printf '    (b) Accept the new weights, re-pin, and RE-RUN every load, stress and\n'
        printf '        accuracy run for this model, then discard the old results:\n'
        printf '            scripts/pull_and_pin_models.sh --model %s --allow-repin\n' "$tag"
        printf '        Record the change and its date in models/candidates.md.\n'
      } >&2
      exit 4
    fi
    if [[ "$ALLOW_REPIN" -eq 1 ]]; then
      printf '  --allow-repin given: the existing pin %s will be overwritten.\n' "$pin_digest"
      printf '  Every earlier run for this model must be re-run and the old results discarded.\n'
    fi
  fi

  # Step 3: pull when we need to (absent locally, or re-pinning on purpose).
  if [[ -z "$local_digest" || "$ALLOW_REPIN" -eq 1 ]]; then
    pull_tag "$tag"
    set +e
    local_line="$(resolve_tag "$tag")"
    resolve_rc=$?
    set -e
    if [[ "$resolve_rc" -ne 0 ]]; then
      printf 'pull of %s reported success but %s/api/tags does not list it (exit %d).\n' \
        "$tag" "$READBACK_URL" "$resolve_rc" >&2
      printf 'Nothing was pinned. Check that the pull and the read-back address are the\n' >&2
      printf 'same Ollama instance -- --ollama-url and --readback-url can point at two.\n' >&2
      exit 5
    fi
    local_digest="${local_line%%$'\t'*}"
    local_size="${local_line##*$'\t'}"
    printf '  resolved after pull: %s (%s bytes)\n' "$local_digest" "$local_size"
  fi

  # Step 4: a pull that landed on a digest other than the pin is still fatal.
  if [[ "$pin_digest" != "-" && "$local_digest" != "$pin_digest" && "$ALLOW_REPIN" -eq 0 ]]; then
    {
      printf '\n*** %s pulled to %s but is pinned at %s. STOPPING; nothing changed. ***\n' \
        "$tag" "$local_digest" "$pin_digest"
      printf 'The upstream tag has moved. See the explanation above; re-pinning invalidates\n'
      printf 'every run already recorded against the pinned digest.\n'
    } >&2
    exit 4
  fi

  # Step 5: write the pin. Only the four scalars change; comments and every
  # human-written field survive untouched.
  py_tool pin "$MODELS_FILE" "$tag" "$local_digest" "$PULLED_AT" "$local_size" "$OLLAMA_VERSION" || exit 2
  printf '  pinned: digest=%s size_bytes=%s pulled_at=%s ollama_version=%s\n' \
    "$local_digest" "$local_size" "$PULLED_AT" "$OLLAMA_VERSION"
  n_pinned=$((n_pinned + 1))
  SUMMARY+="  $tag"$'\t'"pinned"$'\t'"$local_digest"$'\n'
  printf '\n'
done <<< "$SELECTED"

printf '=== summary ===\n'
printf '%s' "$SUMMARY"
printf 'newly pinned: %d   already pinned and unchanged: %d\n' "$n_pinned" "$n_unchanged"
if [[ "$n_pinned" -gt 0 ]]; then
  cat <<NEXT

Commit $MODELS_FILE now. Those digests are what Slide 5 reports, and they are the
only thing tying a measured number to a specific set of weights.
NEXT
fi
