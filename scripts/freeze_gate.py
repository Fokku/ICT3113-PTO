#!/usr/bin/env python3
"""The freeze gate: the one place that decides whether a real benchmark may run.

Owner: Part 1 -- Yeo Kai Yuan (technical core).

Why this file exists
--------------------
The brief makes one rule non-negotiable: the golden test set and the prediction
record must be committed to the repository *before* the first benchmark run, and
the commit history is our evidence that the labels and predictions predate the
measurements. A benchmark run that happens before that freeze is worthless as
evidence, and a golden set edited after seeing model output is an academic
integrity problem rather than a marking deduction.

Prose in a playbook cannot enforce that. This module can, so every script that
is capable of driving a model through real team rows calls it first:

    from scripts.freeze_gate import require_freeze      # (loaded by path; see below)
    freeze_commit = require_freeze(repo_root)

and every shell script calls the CLI:

    python3 scripts/freeze_gate.py --json > "$run_dir/freeze.json" || exit 3

This is the ONLY implementation of the gate. Nothing else in the repository may
re-implement these checks; if the rule changes, it changes here.

What "frozen" means (all of these must hold)
--------------------------------------------
1. ``golden/golden_set.csv`` exists on disk, is tracked by git, and has no
   uncommitted modifications relative to ``HEAD``.
2. ``predictions/prediction_record.md`` likewise.
3. The tag ``golden-freeze`` exists and resolves to a commit.
4. Both files exist **in the tagged commit's own tree**. Checking the working
   tree alone is not enough: someone could tag an early commit and add the
   golden set afterwards, and the tag would then "prove" a freeze that never
   happened.
5. (Our own addition, in the same spirit.) The blob recorded at the tag and the
   blob at ``HEAD`` are identical for both files -- that is, neither file has
   been revised since the freeze was cut. The brief says the prediction record
   cannot be revised after the freeze, so a divergence is a blocking condition
   and not a warning. If a freeze genuinely has to be re-cut, move the tag
   deliberately (``git tag -f golden-freeze <commit>``) and say so in the
   report; that action stays visible in the history, which is the point.

Exit codes (CLI)
----------------
* ``0`` -- frozen. Real runs may proceed.
* ``3`` -- blocked. The reasons are on stdout as JSON (with ``--json``) and in
  English on stderr, each naming the exact command that fixes it.

No network access, no model, no third-party imports: this file must be
importable and printable (``--help``) on any machine in the team.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Paths the freeze is about. Relative to the repository root, forward slashes,
#: exactly as git spells them.
GOLDEN_SET_PATH = "golden/golden_set.csv"
PREDICTION_RECORD_PATH = "predictions/prediction_record.md"
REQUIRED_PATHS: tuple[str, ...] = (GOLDEN_SET_PATH, PREDICTION_RECORD_PATH)

#: The tag that marks the freeze commit.
FREEZE_TAG = "golden-freeze"

#: Exit code used everywhere for "the gate blocked you". Distinct from 1 (an
#: internal error) and from 2 (a misuse of a script's arguments) so a caller can
#: tell the three apart.
GATE_BLOCKED_EXIT = 3

#: The command that builds the golden set, quoted in the stderr advice so that a
#: teammate who hits the gate does not have to go looking for it.
_BUILD_GOLDEN_CMD = (
    "python labelling/scripts/build_golden_set.py "
    "--a labelling/labeller_A.csv --b labelling/labeller_B.csv "
    "--resolutions labelling/resolutions.csv --out golden/golden_set.csv"
)


@dataclass(frozen=True)
class _Failure:
    """One blocking condition: what is wrong, and the command that fixes it."""

    reason: str
    fix: str


@dataclass
class FreezeStatus:
    """The gate's verdict.

    ``reasons`` is the machine-readable list that goes into ``freeze.json``;
    ``fixes`` is the parallel list of remedies rendered on stderr. Everything
    else is evidence about the freeze itself, so that a run directory records
    *which* golden set it was measured against and not merely that one existed.
    """

    ok: bool
    reasons: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    freeze_commit: str | None = None
    freeze_tag: str = FREEZE_TAG
    golden_sha: str | None = None
    prediction_sha: str | None = None
    golden_rows: int | None = None

    def to_payload(self) -> dict:
        """The exact JSON object the contract specifies for each outcome.

        Success and failure deliberately have different shapes: a consumer that
        forgets to check ``ok`` will trip over the missing ``freeze_commit``
        rather than quietly treat a blocked gate as a pass.
        """
        if self.ok:
            return {
                "ok": True,
                "freeze_commit": self.freeze_commit,
                "freeze_tag": self.freeze_tag,
                "golden_sha": self.golden_sha,
                "prediction_sha": self.prediction_sha,
                "golden_rows": self.golden_rows,
            }
        return {"ok": False, "reasons": list(self.reasons)}


# ---------------------------------------------------------------------------
# git plumbing
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str, text: bool = True) -> subprocess.CompletedProcess:
    """Run one git command inside ``repo`` and return the completed process.

    ``shell=True`` is never used anywhere in this file: every argument is passed
    as a separate list element, so a path containing a space or a semicolon
    cannot turn into shell syntax. ``check=False`` because git's exit status is
    the answer we want, not an exception.
    """
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=text,
        check=False,
        encoding="utf-8" if text else None,
        errors="replace" if text else None,
    )


def _git_ok(repo: Path, *args: str) -> bool:
    """True when the git command exits 0. Used for the ``-e``-style probes."""
    return _git(repo, *args).returncode == 0


def _git_out(repo: Path, *args: str) -> str | None:
    """Stripped stdout of a git command, or ``None`` if it failed."""
    proc = _git(repo, *args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _count_csv_data_rows(blob: bytes) -> int:
    """Count the data rows of a CSV blob, tolerating quoted newlines.

    Counting ``\\n`` characters would over-count, because a golden-set row may
    quote a narrative containing newlines. The header row is dropped when the
    first cell does not look like a row number, which is the only assumption
    made about the golden set's column layout -- Part 2 owns that layout.
    """
    text = blob.decode("utf-8", errors="replace")
    if text.startswith("﻿"):          # a spreadsheet export may add a BOM
        text = text[1:]
    reader = csv.reader(io.StringIO(text, newline=""))
    rows = [row for row in reader if any(cell.strip() for cell in row)]
    if not rows:
        return 0
    first_cell = rows[0][0].strip() if rows[0] else ""
    if not first_cell.isdigit():
        rows = rows[1:]
    return len(rows)


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def check_freeze(repo: Path) -> FreezeStatus:
    """Inspect ``repo`` and report whether the freeze holds. Never raises.

    Returning a value rather than raising keeps this usable from a test, from a
    dry-run report and from the CLI without three code paths.
    """
    repo = Path(repo).expanduser()
    failures: list[_Failure] = []

    if not repo.is_dir():
        return FreezeStatus(
            ok=False,
            reasons=[f"{repo} is not a directory, so there is no repository to check."],
            fixes=[f"Pass an existing repository root: --repo <path> (given: {repo})."],
        )
    repo = repo.resolve()

    if not _git_ok(repo, "rev-parse", "--git-dir"):
        return FreezeStatus(
            ok=False,
            reasons=[f"{repo} is not a git repository, so no freeze can be proven."],
            fixes=[
                "The freeze is evidence held in the commit history. Run the "
                "benchmarks from a clone of the team repository."
            ],
        )

    head = _git_out(repo, "rev-parse", "--verify", "-q", "HEAD")
    if head is None:
        failures.append(
            _Failure(
                reason="The repository has no commits, so nothing can be frozen.",
                fix=(
                    "Commit the golden set and the prediction record, then tag:\n"
                    f"       git add {GOLDEN_SET_PATH} {PREDICTION_RECORD_PATH}\n"
                    '       git commit -m "Freeze golden set and prediction record"\n'
                    f'       git tag -a {FREEZE_TAG} -m "Golden set and predictions frozen"'
                ),
            )
        )

    # --- conditions 1 and 2: on disk, tracked, and unmodified ---------------
    for rel in REQUIRED_PATHS:
        failures.extend(_check_working_file(repo, rel, has_head=head is not None))

    # --- condition 3: the tag exists ---------------------------------------
    freeze_commit = _git_out(
        repo, "rev-parse", "-q", "--verify", f"refs/tags/{FREEZE_TAG}^{{commit}}"
    )
    if not freeze_commit:
        failures.append(
            _Failure(
                reason=f"The tag '{FREEZE_TAG}' does not exist.",
                fix=(
                    "After both files are committed, tag that commit:\n"
                    f'       git tag -a {FREEZE_TAG} -m "Golden set and predictions frozen"\n'
                    f"       git push origin {FREEZE_TAG}"
                ),
            )
        )

    golden_sha: str | None = None
    prediction_sha: str | None = None
    golden_rows: int | None = None

    if freeze_commit:
        # --- condition 4: both files are in the TAGGED commit's tree --------
        # This is the check that stops a back-dated freeze: tagging an earlier
        # commit and adding the golden set afterwards would satisfy every other
        # condition while proving nothing at all.
        tagged: dict[str, str | None] = {}
        for rel in REQUIRED_PATHS:
            spec = f"{FREEZE_TAG}:{rel}"
            if not _git_ok(repo, "cat-file", "-e", spec):
                failures.append(
                    _Failure(
                        reason=(
                            f"{rel} is not present in the tree of the commit tagged "
                            f"'{FREEZE_TAG}' ({freeze_commit[:12]}). The tag points at a "
                            f"commit made before the file existed, so it does not prove a "
                            f"freeze."
                        ),
                        fix=(
                            f"Commit {rel}, then move the tag onto the commit that really "
                            f"contains it:\n"
                            f"       git add {rel} && git commit -m "
                            f'"Freeze golden set and prediction record"\n'
                            f"       git tag -f -a {FREEZE_TAG} -m "
                            f'"Golden set and predictions frozen"'
                        ),
                    )
                )
                tagged[rel] = None
            else:
                tagged[rel] = _git_out(repo, "rev-parse", f"{spec}")

        golden_sha = tagged.get(GOLDEN_SET_PATH)
        prediction_sha = tagged.get(PREDICTION_RECORD_PATH)

        # --- condition 5: nothing has been revised since the freeze ---------
        if head is not None:
            for rel, tagged_sha in tagged.items():
                if tagged_sha is None:
                    continue
                head_sha = _git_out(repo, "rev-parse", "-q", "--verify", f"HEAD:{rel}")
                if head_sha and head_sha != tagged_sha:
                    failures.append(
                        _Failure(
                            reason=(
                                f"{rel} has been changed since the '{FREEZE_TAG}' tag "
                                f"(tagged blob {tagged_sha[:12]}, HEAD blob "
                                f"{head_sha[:12]}). A frozen file may not be revised."
                            ),
                            fix=(
                                f"Restore the frozen content:\n"
                                f"       git checkout {FREEZE_TAG} -- {rel}\n"
                                f"   or, if the freeze must genuinely be re-cut, move the "
                                f"tag and record why in the report:\n"
                                f"       git tag -f -a {FREEZE_TAG} -m "
                                f'"Re-cut freeze: <reason>"'
                            ),
                        )
                    )

        if golden_sha:
            blob = _git(repo, "cat-file", "blob", golden_sha, text=False)
            if blob.returncode == 0:
                golden_rows = _count_csv_data_rows(blob.stdout)

    if failures:
        return FreezeStatus(
            ok=False,
            reasons=[f.reason for f in failures],
            fixes=[f.fix for f in failures],
            freeze_commit=None,
            golden_sha=golden_sha,
            prediction_sha=prediction_sha,
            golden_rows=golden_rows,
        )

    return FreezeStatus(
        ok=True,
        freeze_commit=freeze_commit,
        golden_sha=golden_sha,
        prediction_sha=prediction_sha,
        golden_rows=golden_rows,
    )


def _check_working_file(repo: Path, rel: str, *, has_head: bool) -> list[_Failure]:
    """Conditions 1 and 2 for a single path: exists, tracked, unmodified."""
    failures: list[_Failure] = []
    absolute = repo / rel

    if not absolute.is_file():
        hint = _BUILD_GOLDEN_CMD if rel == GOLDEN_SET_PATH else (
            "Write the prediction record (Step 4 of the brief: expected bottleneck, "
            "per-model expected accuracy and single-request latency, hardest "
            "categories) before any benchmark run."
        )
        failures.append(
            _Failure(
                reason=f"{rel} does not exist.",
                fix=f"{hint}\n       Then: git add {rel} && git commit",
            )
        )
        return failures

    if not _git_ok(repo, "ls-files", "--error-unmatch", "--", rel):
        failures.append(
            _Failure(
                reason=f"{rel} exists but is not tracked by git, so it is not evidence.",
                fix=(
                    f"git add {rel}\n"
                    '       git commit -m "Freeze golden set and prediction record"'
                ),
            )
        )
        return failures

    if not has_head:
        # Tracked but there is no HEAD: the file is staged and never committed.
        # The missing-commits failure is already reported once; do not repeat it
        # per file.
        return failures

    diff = _git(repo, "diff", "--quiet", "HEAD", "--", rel)
    if diff.returncode == 1:
        failures.append(
            _Failure(
                reason=(
                    f"{rel} has uncommitted modifications, so the committed copy is not "
                    f"the copy that would be measured."
                ),
                fix=(
                    f"Inspect and then either commit or discard the change:\n"
                    f"       git diff HEAD -- {rel}\n"
                    f"       git add {rel} && git commit -m "
                    f'"<why the frozen file changed>"\n'
                    f"   or: git checkout -- {rel}"
                ),
            )
        )
    elif diff.returncode != 0:
        failures.append(
            _Failure(
                reason=(
                    f"git could not compare {rel} with HEAD "
                    f"(exit {diff.returncode}): {diff.stderr.strip()}"
                ),
                fix="Resolve the git error above, then re-run the gate.",
            )
        )
    return failures


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def explain(status: FreezeStatus) -> str:
    """Render a blocked verdict as English, one numbered reason plus its fix."""
    if status.ok:
        return (
            f"FREEZE GATE: PASS. Frozen at {status.freeze_commit} "
            f"(tag '{status.freeze_tag}')."
        )
    lines = [
        f"FREEZE GATE: BLOCKED -- {len(status.reasons)} condition(s) not met.",
        "",
        "No real benchmark run may proceed. The brief requires the golden test set",
        "and the prediction record to be committed BEFORE the first benchmark run;",
        "the commit history is the evidence that they predate the measurements.",
        "",
    ]
    for index, reason in enumerate(status.reasons, 1):
        fix = status.fixes[index - 1] if index - 1 < len(status.fixes) else ""
        lines.append(f"  {index}. {reason}")
        if fix:
            lines.append(f"     Fix: {fix}")
        lines.append("")
    lines.append(
        "To exercise the tooling before the freeze, use --dev: it runs against "
        "data/dev/synthetic_tickets.csv,"
    )
    lines.append(
        "writes under results/dev/ only, and its output is explicitly not evidence."
    )
    return "\n".join(lines)


def require_freeze(repo: Path) -> str:
    """Return the freeze commit, or exit 3 after explaining what is missing.

    This is the function every real-mode script calls. It is deliberately
    unforgiving: there is no ``force`` argument, because the only legitimate way
    past the gate is to actually freeze the files.
    """
    status = check_freeze(repo)
    if not status.ok or status.freeze_commit is None:
        print(explain(status), file=sys.stderr)
        raise SystemExit(GATE_BLOCKED_EXIT)
    return status.freeze_commit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="freeze_gate.py",
        description=(
            "Check that the golden test set and the prediction record are "
            "committed and tagged '%s'. Exit 0 if they are, %d if they are not."
            % (FREEZE_TAG, GATE_BLOCKED_EXIT)
        ),
        epilog=(
            "Bash callers: python3 scripts/freeze_gate.py --json "
            '> "$run_dir/freeze.json" || exit 3'
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Write the verdict to stdout as JSON. On success: ok, freeze_commit, "
            "freeze_tag, golden_sha, prediction_sha, golden_rows. On failure: "
            "ok=false and reasons."
        ),
    )
    parser.add_argument(
        "--repo",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="Repository root to check (default: the repository this script lives in).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    status = check_freeze(args.repo)

    if args.json:
        # stdout is the machine channel: exactly the contracted payload, nothing
        # else, so it can be redirected straight into freeze.json.
        print(json.dumps(status.to_payload(), indent=2))

    if status.ok:
        if not args.json:
            print(explain(status))
            print(f"  golden set   : {status.golden_rows} rows, blob {status.golden_sha}")
            print(f"  prediction   : blob {status.prediction_sha}")
        return 0

    print(explain(status), file=sys.stderr)
    return GATE_BLOCKED_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
