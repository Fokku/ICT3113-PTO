#!/usr/bin/env python3
"""The A2 gate: the one place that decides whether a real Assignment 2 benchmark may run.

Owner: Part 1 -- Yeo Kai Yuan (technical core).

Why this file exists
--------------------
This is the Assignment 2 counterpart of ``scripts/freeze_gate.py``, with the
same purpose and the same shape, retargeted at Assignment 2's evidence. The
Assignment 2 brief (Step 3): predictions are recorded and committed *before any
testing*, and cannot be revised afterwards. A benchmark run that happens before
that commit is worthless as evidence for the same reason Assignment 1's was:
there is nothing stopping the "prediction" from quietly becoming a description
of what was already observed.

Three files are gated here, not two, because Assignment 2 adds one more
piece of pre-registered evidence beyond the prediction record itself: the
escalation rule. The brief requires it "documented clearly enough that another
team could implement it from the description" and committed as a supporting
file; gating it alongside the predictions stops a team from tuning the rule
after seeing cascade results and then writing the document to match.

    from scripts.a2_gate import require_a2_gate      # (loaded by path; see below)
    gate_commit = require_a2_gate(repo_root)

and every shell/python driver calls the CLI:

    python3 scripts/a2_gate.py --json > "$run_dir/gate.json" || exit 3

This is the ONLY implementation of the Assignment 2 gate. If the rule changes,
it changes here -- do not re-implement these checks elsewhere.

What "gated" means (all of these must hold)
---------------------------------------------
1. ``predictions/prediction_record_a2.md`` exists on disk, is tracked by git,
   and has no uncommitted modifications relative to ``HEAD``.
2. ``cascade/escalation_rule.md`` likewise.
3. ``golden/split_a2.csv`` likewise -- the tuning/test split must also predate
   any test-set accuracy figure being looked at, per Step 1 of the brief.
4. The tag ``a2-predictions-freeze`` exists and resolves to a commit.
5. All three files exist **in the tagged commit's own tree**. Checking the
   working tree alone is not enough: someone could tag an early commit and add
   the files afterwards, and the tag would then "prove" a gate that never
   happened. Same reasoning as Assignment 1's freeze gate, condition 4.
6. The blob recorded at the tag and the blob at ``HEAD`` are identical for all
   three files -- none of them has been revised since the gate was cut. If a
   gate genuinely has to be re-cut, move the tag deliberately
   (``git tag -f a2-predictions-freeze <commit>``) and say so in the report.
7. **Neither** the prediction record **nor the escalation rule** -- each as
   recorded in the tagged commit, or on disk while there is no tag yet --
   contains a ``TODO(`` placeholder. Same reasoning as Assignment 1: without
   this check, an untouched template could be committed and tagged and every
   other condition above would pass. Both documents are checked, not just the
   prediction record, because both are pre-registered evidence under this
   gate; Assignment 1's own history (``predictions/prediction_record.md``
   section 0, item 1) is the reason this check exists at all.

Exit codes (CLI)
----------------
* ``0`` -- gated. Real Assignment 2 runs may proceed.
* ``3`` -- blocked. The reasons are on stdout as JSON (with ``--json``) and in
  English on stderr, each naming the exact command that fixes it.

No network access, no model, no third-party imports: this file must be
importable and printable (``--help``) on any machine in the team.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

#: Paths the gate is about. Relative to the repository root, forward slashes,
#: exactly as git spells them.
PREDICTION_RECORD_PATH = "predictions/prediction_record_a2.md"
ESCALATION_RULE_PATH = "cascade/escalation_rule.md"
SPLIT_PATH = "golden/split_a2.csv"
REQUIRED_PATHS: tuple[str, ...] = (
    PREDICTION_RECORD_PATH,
    ESCALATION_RULE_PATH,
    SPLIT_PATH,
)

#: The tag that marks the gate commit.
GATE_TAG = "a2-predictions-freeze"

#: The placeholders used for an undecided entry: the template's ``TODO(`` and
#: the ``<<<...>>>`` style used for a figure not yet filled in. A prediction
#: record still carrying either is unfinished, and an unfinished record does
#: not gate.
UNFINISHED_MARKERS: tuple[str, ...] = ("TODO(", "<<<")
UNFINISHED_MARKER = UNFINISHED_MARKERS[0]

#: Exit code used everywhere for "the gate blocked you". Distinct from 1 (an
#: internal error) and from 2 (a misuse of a script's arguments) so a caller
#: can tell the three apart.
GATE_BLOCKED_EXIT = 3


@dataclass(frozen=True)
class _Failure:
    """One blocking condition: what is wrong, and the command that fixes it."""

    reason: str
    fix: str


@dataclass
class GateStatus:
    """The gate's verdict.

    ``reasons`` is the machine-readable list that goes into ``gate.json``;
    ``fixes`` is the parallel list of remedies rendered on stderr. Everything
    else is evidence about the gate itself, so a run directory records
    *which* prediction record and escalation rule it was measured against,
    not merely that one existed.
    """

    ok: bool
    reasons: list[str] = field(default_factory=list)
    fixes: list[str] = field(default_factory=list)
    gate_commit: str | None = None
    gate_tag: str = GATE_TAG
    prediction_sha: str | None = None
    escalation_rule_sha: str | None = None
    split_sha: str | None = None

    def to_payload(self) -> dict:
        """The exact JSON object the contract specifies for each outcome.

        Success and failure deliberately have different shapes: a consumer
        that forgets to check ``ok`` will trip over the missing
        ``gate_commit`` rather than quietly treat a blocked gate as a pass.
        """
        if self.ok:
            return {
                "ok": True,
                "gate_commit": self.gate_commit,
                "gate_tag": self.gate_tag,
                "prediction_sha": self.prediction_sha,
                "escalation_rule_sha": self.escalation_rule_sha,
                "split_sha": self.split_sha,
            }
        return {"ok": False, "reasons": list(self.reasons)}


# ---------------------------------------------------------------------------
# git plumbing (identical approach to scripts/freeze_gate.py)
# ---------------------------------------------------------------------------

def _git(repo: Path, *args: str) -> subprocess.CompletedProcess:
    """Run one git command inside ``repo`` and return the completed process.

    ``shell=True`` is never used: every argument is a separate list element,
    so a path containing a space or a semicolon cannot turn into shell syntax.
    ``check=False`` because git's exit status is the answer we want, not an
    exception.
    """
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
        encoding="utf-8",
        errors="replace",
    )


def _git_ok(repo: Path, *args: str) -> bool:
    """True when the git command exits 0."""
    return _git(repo, *args).returncode == 0


def _git_out(repo: Path, *args: str) -> str | None:
    """Stripped stdout of a git command, or ``None`` if it failed."""
    proc = _git(repo, *args)
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


# ---------------------------------------------------------------------------
# The gate
# ---------------------------------------------------------------------------

def check_gate(repo: Path) -> GateStatus:
    """Inspect ``repo`` and report whether the A2 gate holds. Never raises."""
    repo = Path(repo).expanduser()
    failures: list[_Failure] = []

    if not repo.is_dir():
        return GateStatus(
            ok=False,
            reasons=[f"{repo} is not a directory, so there is no repository to check."],
            fixes=[f"Pass an existing repository root: --repo <path> (given: {repo})."],
        )
    repo = repo.resolve()

    if not _git_ok(repo, "rev-parse", "--git-dir"):
        return GateStatus(
            ok=False,
            reasons=[f"{repo} is not a git repository, so no gate can be proven."],
            fixes=[
                "The gate is evidence held in the commit history. Run the "
                "benchmarks from a clone of the team repository."
            ],
        )

    head = _git_out(repo, "rev-parse", "--verify", "-q", "HEAD")
    if head is None:
        failures.append(
            _Failure(
                reason="The repository has no commits, so nothing can be gated.",
                fix=(
                    "Commit the three required files, then tag:\n"
                    f"       git add {' '.join(REQUIRED_PATHS)}\n"
                    '       git commit -m "A2 gate: predictions, escalation rule, split"\n'
                    f'       git tag -a {GATE_TAG} -m "A2 predictions and escalation rule frozen"'
                ),
            )
        )

    # --- conditions 1-3: on disk, tracked, and unmodified ------------------
    for rel in REQUIRED_PATHS:
        failures.extend(_check_working_file(repo, rel, has_head=head is not None))

    # --- condition 4: the tag exists ----------------------------------------
    gate_commit = _git_out(
        repo, "rev-parse", "-q", "--verify", f"refs/tags/{GATE_TAG}^{{commit}}"
    )
    if not gate_commit:
        failures.append(
            _Failure(
                reason=f"The tag '{GATE_TAG}' does not exist.",
                fix=(
                    "After all three files are committed, tag that commit:\n"
                    f'       git tag -a {GATE_TAG} -m "A2 predictions and escalation rule frozen"\n'
                    f"       git push origin {GATE_TAG}"
                ),
            )
        )

    shas: dict[str, str | None] = {rel: None for rel in REQUIRED_PATHS}

    if gate_commit:
        # --- condition 5: all three files are in the TAGGED commit's tree --
        for rel in REQUIRED_PATHS:
            spec = f"{GATE_TAG}:{rel}"
            if not _git_ok(repo, "cat-file", "-e", spec):
                failures.append(
                    _Failure(
                        reason=(
                            f"{rel} is not present in the tree of the commit tagged "
                            f"'{GATE_TAG}' ({gate_commit[:12]}). The tag points at a "
                            f"commit made before the file existed, so it does not prove "
                            f"a gate."
                        ),
                        fix=(
                            f"Commit {rel}, then move the tag onto the commit that "
                            f"really contains it:\n"
                            f"       git add {rel} && git commit -m "
                            f'"A2 gate: predictions, escalation rule, split"\n'
                            f"       git tag -f -a {GATE_TAG} -m "
                            f'"A2 predictions and escalation rule frozen"'
                        ),
                    )
                )
            else:
                shas[rel] = _git_out(repo, "rev-parse", spec)

        # --- condition 6: nothing has been revised since the gate ----------
        if head is not None:
            for rel, tagged_sha in shas.items():
                if tagged_sha is None:
                    continue
                head_sha = _git_out(repo, "rev-parse", "-q", "--verify", f"HEAD:{rel}")
                if head_sha and head_sha != tagged_sha:
                    failures.append(
                        _Failure(
                            reason=(
                                f"{rel} has been changed since the '{GATE_TAG}' tag "
                                f"(tagged blob {tagged_sha[:12]}, HEAD blob "
                                f"{head_sha[:12]}). A gated file may not be revised."
                            ),
                            fix=(
                                f"Restore the gated content:\n"
                                f"       git checkout {GATE_TAG} -- {rel}\n"
                                f"   or, if the gate must genuinely be re-cut, move the "
                                f"tag and record why in the report:\n"
                                f"       git tag -f -a {GATE_TAG} -m "
                                f'"Re-cut A2 gate: <reason>"'
                            ),
                        )
                    )

    # --- condition 7: neither gated markdown document is still a template --
    # Checked on the tagged blob when there is a tag (that is the record of
    # evidence), otherwise on the working file, so the gate says so *before*
    # anyone tags an unfinished document. Both documents are checked, not just
    # the prediction record: Assignment 1's own history is the reason why
    # (predictions/prediction_record.md section 0, item 1) -- the first
    # golden-freeze tag once froze an empty template because the gate checked
    # that the file was committed, not that it said anything. The escalation
    # rule is exactly as pre-registered as the prediction record, and a
    # placeholder-only rule document would pass just as silently if it were
    # not checked here too.
    for doc_path, doc_label in (
        (PREDICTION_RECORD_PATH, "the prediction record"),
        (ESCALATION_RULE_PATH, "the escalation rule"),
    ):
        doc_text: str | None = None
        doc_where = ""
        if shas.get(doc_path):
            blob = _git(repo, "cat-file", "blob", shas[doc_path])
            if blob.returncode == 0:
                doc_text = blob.stdout
                doc_where = f"in the commit tagged '{GATE_TAG}'"
        elif not gate_commit and (repo / doc_path).is_file():
            doc_text = (repo / doc_path).read_text(encoding="utf-8", errors="replace")
            doc_where = "on disk"
        if doc_text is None:
            continue
        unfinished = _unfinished_lines(doc_text)
        if not unfinished:
            continue
        shown = ", ".join(str(n) for n in unfinished[:10])
        more = f" (and {len(unfinished) - 10} more)" if len(unfinished) > 10 else ""
        failures.append(
            _Failure(
                reason=(
                    f"{doc_path} {doc_where} still contains {len(unfinished)} "
                    f"unfinished {' or '.join(repr(m) for m in UNFINISHED_MARKERS)} "
                    f"placeholder line(s): lines {shown}{more}."
                ),
                fix=(
                    f"Replace every placeholder in {doc_label} with the team's "
                    f"decision, commit it, and only then tag:\n"
                    f"       grep -nE 'TODO\\(|<<<' {doc_path}"
                ),
            )
        )

    if failures:
        return GateStatus(
            ok=False,
            reasons=[f.reason for f in failures],
            fixes=[f.fix for f in failures],
            gate_commit=None,
            prediction_sha=shas.get(PREDICTION_RECORD_PATH),
            escalation_rule_sha=shas.get(ESCALATION_RULE_PATH),
            split_sha=shas.get(SPLIT_PATH),
        )

    return GateStatus(
        ok=True,
        gate_commit=gate_commit,
        prediction_sha=shas.get(PREDICTION_RECORD_PATH),
        escalation_rule_sha=shas.get(ESCALATION_RULE_PATH),
        split_sha=shas.get(SPLIT_PATH),
    )


def _unfinished_lines(text: str) -> list[int]:
    """1-based line numbers of ``text`` that still carry the unfinished marker."""
    return [
        number
        for number, line in enumerate(text.splitlines(), start=1)
        if any(marker in line for marker in UNFINISHED_MARKERS)
    ]


def _check_working_file(repo: Path, rel: str, *, has_head: bool) -> list[_Failure]:
    """Conditions 1-3 for a single path: exists, tracked, unmodified."""
    failures: list[_Failure] = []
    absolute = repo / rel

    if not absolute.is_file():
        hints = {
            SPLIT_PATH: (
                "Generate it from the frozen golden set by row-number parity "
                "(odd = tuning, even = test) -- see TODO_A2.md section 2.1."
            ),
            ESCALATION_RULE_PATH: (
                "Write the escalation rule document (TODO_A2.md section 2.5) before "
                "any benchmark run."
            ),
            PREDICTION_RECORD_PATH: (
                "Write the prediction record (brief Step 3: fastest qualifying "
                "configuration and why, expected escalation fraction/accuracy/latency "
                "per cascade setting, hardest categories for the small model's "
                "accepted answers) before any benchmark run -- see TODO_A2.md section 4.2."
            ),
        }
        failures.append(
            _Failure(
                reason=f"{rel} does not exist.",
                fix=f"{hints[rel]}\n       Then: git add {rel} && git commit",
            )
        )
        return failures

    if not _git_ok(repo, "ls-files", "--error-unmatch", "--", rel):
        failures.append(
            _Failure(
                reason=f"{rel} exists but is not tracked by git, so it is not evidence.",
                fix=(
                    f"git add {rel}\n"
                    '       git commit -m "A2 gate: predictions, escalation rule, split"'
                ),
            )
        )
        return failures

    if not has_head:
        # Tracked but there is no HEAD: the file is staged and never committed.
        # The missing-commits failure is already reported once; do not repeat
        # it per file.
        return failures

    diff = _git(repo, "diff", "--quiet", "HEAD", "--", rel)
    if diff.returncode == 1:
        failures.append(
            _Failure(
                reason=(
                    f"{rel} has uncommitted modifications, so the committed copy is "
                    f"not the copy that would be measured."
                ),
                fix=(
                    f"Inspect and then either commit or discard the change:\n"
                    f"       git diff HEAD -- {rel}\n"
                    f"       git add {rel} && git commit -m "
                    f'"<why the gated file changed>"\n'
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

def explain(status: GateStatus) -> str:
    """Render a blocked verdict as English, one numbered reason plus its fix."""
    if status.ok:
        return f"A2 GATE: PASS. Gated at {status.gate_commit} (tag '{status.gate_tag}')."
    lines = [
        f"A2 GATE: BLOCKED -- {len(status.reasons)} condition(s) not met.",
        "",
        "No real Assignment 2 benchmark run may proceed. The brief requires the",
        "prediction record and the escalation rule to be committed BEFORE the first",
        "A2 benchmark run; the commit history is the evidence that they predate the",
        "measurements.",
        "",
    ]
    for index, reason in enumerate(status.reasons, 1):
        fix = status.fixes[index - 1] if index - 1 < len(status.fixes) else ""
        lines.append(f"  {index}. {reason}")
        if fix:
            lines.append(f"     Fix: {fix}")
        lines.append("")
    lines.append(
        "To exercise the tooling before the gate, use --dev: it runs against "
        "data/dev/synthetic_tickets.csv,"
    )
    lines.append(
        "writes under results/dev/ only, and its output is explicitly not evidence."
    )
    return "\n".join(lines)


def require_a2_gate(repo: Path) -> str:
    """Return the gate commit, or exit 3 after explaining what is missing.

    This is the function every real-mode Assignment 2 script calls. It is
    deliberately unforgiving: there is no ``force`` argument, because the only
    legitimate way past the gate is to actually gate the files.
    """
    status = check_gate(repo)
    if not status.ok or status.gate_commit is None:
        print(explain(status), file=sys.stderr)
        raise SystemExit(GATE_BLOCKED_EXIT)
    return status.gate_commit


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="a2_gate.py",
        description=(
            "Check that the A2 prediction record, escalation rule and golden-set "
            "split are committed and tagged '%s'. Exit 0 if they are, %d if they "
            "are not." % (GATE_TAG, GATE_BLOCKED_EXIT)
        ),
        epilog=(
            "Callers: python3 scripts/a2_gate.py --json "
            '> "$run_dir/gate.json" || exit 3'
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help=(
            "Write the verdict to stdout as JSON. On success: ok, gate_commit, "
            "gate_tag, prediction_sha, escalation_rule_sha, split_sha. On "
            "failure: ok=false and reasons."
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
    status = check_gate(args.repo)

    if args.json:
        # stdout is the machine channel: exactly the contracted payload,
        # nothing else, so it can be redirected straight into gate.json.
        print(json.dumps(status.to_payload(), indent=2))

    if status.ok:
        if not args.json:
            print(explain(status))
            print(f"  prediction record : blob {status.prediction_sha}")
            print(f"  escalation rule    : blob {status.escalation_rule_sha}")
            print(f"  tuning/test split  : blob {status.split_sha}")
        return 0

    print(explain(status), file=sys.stderr)
    return GATE_BLOCKED_EXIT


if __name__ == "__main__":
    raise SystemExit(main())
