"""Tests for the freeze gate.

Owner: Part 1 -- Yeo Kai Yuan (technical core).

The gate is the only thing standing between "we measured after freezing" and an
academic integrity problem, so it is tested against *real* git repositories
rather than against mocks: each test builds a throwaway repository in
``tmp_path`` with ``subprocess`` git, puts it into exactly one broken state, and
asserts that the gate blocks for that reason and no other.

Every test isolates git from the developer's own configuration
(``GIT_CONFIG_GLOBAL=/dev/null`` and friends) so that a global ``commit.gpgsign``
or a template hook cannot make the suite fail on one machine and pass on
another.

No model, no service and no network are involved.
"""

from __future__ import annotations

import importlib.util
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
FREEZE_GATE_PATH = REPO_ROOT / "scripts" / "freeze_gate.py"

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _load_freeze_gate():
    """Import ``scripts/freeze_gate.py`` by path.

    ``scripts/`` is deliberately not a Python package (it is a directory of
    runnable tools, and adding ``__init__.py`` would invite importing shell-ish
    helpers from library code), so the module is loaded from its file.
    """
    spec = importlib.util.spec_from_file_location("freeze_gate_under_test", FREEZE_GATE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Registered before execution because @dataclass resolves annotations via
    # sys.modules[cls.__module__]; without this the import fails on 3.12+.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


freeze_gate = _load_freeze_gate()

GOLDEN = freeze_gate.GOLDEN_SET_PATH
PREDICTION = freeze_gate.PREDICTION_RECORD_PATH
TAG = freeze_gate.FREEZE_TAG

#: A golden set whose third column quotes a comma and a newline, so that the row
#: count cannot be produced by counting newline characters.
GOLDEN_CSV = (
    "row_number,label,note\n"
    "10000,Mortgage,plain\n"
    '10001,Debt collection,"two clauses, one row"\n'
    '10002,Credit card,"a note that spans\ntwo physical lines"\n'
    "10003,Credit reporting,plain\n"
)
GOLDEN_DATA_ROWS = 4

PREDICTION_MD = "# Prediction record\n\nFrozen before the first benchmark run.\n"


# ---------------------------------------------------------------------------
# git helpers
# ---------------------------------------------------------------------------

def _git_env() -> dict[str, str]:
    """An environment in which git is deterministic and ignores user config."""
    env = dict(os.environ)
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_AUTHOR_NAME": "ICT3113 Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "ICT3113 Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return env


def git(repo: Path, *args: str) -> str:
    """Run git in ``repo``, failing the test loudly if git itself fails."""
    proc = subprocess.run(
        ["git", "-C", str(repo), "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false", *args],
        capture_output=True,
        text=True,
        check=False,
        env=_git_env(),
    )
    if proc.returncode != 0:
        raise AssertionError(
            f"git {' '.join(args)} failed ({proc.returncode}):\n{proc.stderr}"
        )
    return proc.stdout.strip()


def new_repo(tmp_path: Path, name: str = "repo") -> Path:
    """An empty git repository with the golden/prediction directories present."""
    repo = tmp_path / name
    (repo / "golden").mkdir(parents=True)
    (repo / "predictions").mkdir(parents=True)
    git(repo, "init", "-q")
    return repo


def write_golden(repo: Path, content: str = GOLDEN_CSV) -> None:
    (repo / GOLDEN).write_text(content, encoding="utf-8")


def write_prediction(repo: Path, content: str = PREDICTION_MD) -> None:
    (repo / PREDICTION).write_text(content, encoding="utf-8")


def commit_all(repo: Path, message: str = "commit") -> str:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)
    return git(repo, "rev-parse", "HEAD")


def tag_freeze(repo: Path, commit: str = "HEAD", *, annotated: bool = True) -> None:
    if annotated:
        git(repo, "tag", "-a", TAG, "-m", "Golden set and predictions frozen", commit)
    else:
        git(repo, "tag", TAG, commit)


def frozen_repo(tmp_path: Path, *, annotated: bool = True) -> Path:
    """A repository in the state the brief requires: committed, then tagged."""
    repo = new_repo(tmp_path)
    write_golden(repo)
    write_prediction(repo)
    commit_all(repo, "Freeze golden set and prediction record")
    tag_freeze(repo, annotated=annotated)
    return repo


def run_cli(repo: Path, *extra: str) -> subprocess.CompletedProcess:
    """Invoke the gate exactly as the shell scripts do."""
    return subprocess.run(
        [sys.executable, str(FREEZE_GATE_PATH), "--repo", str(repo), *extra],
        capture_output=True,
        text=True,
        check=False,
    )


def reasons_text(status) -> str:
    return "\n".join(status.reasons)


# ---------------------------------------------------------------------------
# The passing case
# ---------------------------------------------------------------------------

def test_passes_when_committed_and_tagged(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    status = freeze_gate.check_freeze(repo)

    assert status.ok, reasons_text(status)
    assert status.reasons == []
    assert SHA40.match(status.freeze_commit or "")
    assert status.freeze_commit == git(repo, "rev-parse", "HEAD")
    assert status.freeze_tag == TAG
    assert SHA40.match(status.golden_sha or "")
    assert SHA40.match(status.prediction_sha or "")
    # The blob SHAs must be the ones recorded at the tag, not merely any blob.
    assert status.golden_sha == git(repo, "rev-parse", f"{TAG}:{GOLDEN}")
    assert status.prediction_sha == git(repo, "rev-parse", f"{TAG}:{PREDICTION}")


def test_passes_with_a_lightweight_tag(tmp_path: Path) -> None:
    """A lightweight tag is still a freeze; the gate must not insist on -a."""
    repo = frozen_repo(tmp_path, annotated=False)
    status = freeze_gate.check_freeze(repo)
    assert status.ok, reasons_text(status)
    assert status.freeze_commit == git(repo, "rev-parse", "HEAD")


def test_golden_rows_counts_data_rows_not_newlines(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    status = freeze_gate.check_freeze(repo)
    assert status.ok, reasons_text(status)
    # GOLDEN_CSV has a header, four data rows, and a quoted embedded newline.
    assert status.golden_rows == GOLDEN_DATA_ROWS


def test_require_freeze_returns_the_commit(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    assert freeze_gate.require_freeze(repo) == git(repo, "rev-parse", "HEAD")


# ---------------------------------------------------------------------------
# One test per blocking reason
# ---------------------------------------------------------------------------

def test_blocks_when_golden_set_is_missing(tmp_path: Path) -> None:
    repo = new_repo(tmp_path)
    write_prediction(repo)
    commit_all(repo)
    tag_freeze(repo)

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    # Every complaint is about the golden set -- the prediction record and the
    # tag are in order. (A missing file also fails the tagged-tree condition,
    # so two reasons are expected, both naming the same path.)
    assert all(GOLDEN in reason for reason in status.reasons), reasons_text(status)
    assert PREDICTION not in reasons_text(status)
    assert "does not exist" in status.reasons[0]
    assert status.freeze_commit is None
    # The advice must name the command that produces the file.
    assert "build_golden_set.py" in status.fixes[0]


def test_blocks_when_golden_set_is_untracked(tmp_path: Path) -> None:
    repo = new_repo(tmp_path)
    write_prediction(repo)
    commit_all(repo)
    tag_freeze(repo)
    # Written to disk but never added: a file only git knows about is evidence.
    write_golden(repo)

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert all(GOLDEN in reason for reason in status.reasons), reasons_text(status)
    assert PREDICTION not in reasons_text(status)
    assert "not tracked by git" in status.reasons[0]
    assert f"git add {GOLDEN}" in status.fixes[0]


def test_blocks_when_golden_set_is_modified_after_commit(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    # Edited on disk after the freeze: the committed copy is no longer the copy
    # that would be measured.
    write_golden(repo, GOLDEN_CSV + "10004,Consumer loan,added after the freeze\n")

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert len(status.reasons) == 1, reasons_text(status)
    assert "uncommitted modifications" in status.reasons[0]
    assert GOLDEN in status.reasons[0]


def test_blocks_when_staged_but_never_committed(tmp_path: Path) -> None:
    """``git add`` alone is not a freeze: there must be a commit."""
    repo = new_repo(tmp_path)
    write_golden(repo)
    write_prediction(repo)
    git(repo, "add", "-A")

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert any("no commits" in reason for reason in status.reasons), reasons_text(status)


def test_blocks_when_prediction_record_is_missing(tmp_path: Path) -> None:
    repo = new_repo(tmp_path)
    write_golden(repo)
    commit_all(repo)
    tag_freeze(repo)

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert all(PREDICTION in reason for reason in status.reasons), reasons_text(status)
    assert GOLDEN not in reasons_text(status)
    assert "does not exist" in status.reasons[0]


def test_blocks_when_prediction_record_is_modified_after_commit(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    write_prediction(repo, PREDICTION_MD + "\nRevised after seeing the results.\n")

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert len(status.reasons) == 1, reasons_text(status)
    assert PREDICTION in status.reasons[0]
    assert "uncommitted modifications" in status.reasons[0]


def test_blocks_when_the_tag_is_missing(tmp_path: Path) -> None:
    repo = new_repo(tmp_path)
    write_golden(repo)
    write_prediction(repo)
    commit_all(repo)

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert len(status.reasons) == 1, reasons_text(status)
    assert TAG in status.reasons[0]
    assert "does not exist" in status.reasons[0]
    assert f"git tag -a {TAG}" in status.fixes[0]


def test_blocks_when_the_tag_predates_the_frozen_files(tmp_path: Path) -> None:
    """The back-dated freeze: tag an early commit, add the files afterwards.

    Every other condition holds -- the files exist, are tracked, are unmodified,
    and the tag resolves -- so this is precisely the case a working-tree-only
    check would wave through.
    """
    repo = new_repo(tmp_path)
    (repo / "README.md").write_text("Team 10 repository.\n", encoding="utf-8")
    early = commit_all(repo, "Initial commit")
    write_golden(repo)
    write_prediction(repo)
    commit_all(repo, "Add golden set and prediction record after tagging")
    tag_freeze(repo, early)

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert len(status.reasons) == 2, reasons_text(status)
    joined = reasons_text(status)
    assert GOLDEN in joined and PREDICTION in joined
    assert "not present in the tree of the commit tagged" in joined
    assert status.freeze_commit is None


def test_blocks_when_a_frozen_file_is_revised_after_the_tag(tmp_path: Path) -> None:
    """Committed changes after the tag are still a revision of a frozen file."""
    repo = frozen_repo(tmp_path)
    write_golden(repo, GOLDEN_CSV + "10004,Consumer loan,added and committed after the tag\n")
    commit_all(repo, "Revise the golden set after the freeze")

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert len(status.reasons) == 1, reasons_text(status)
    assert "has been changed since" in status.reasons[0]
    assert GOLDEN in status.reasons[0]


def test_blocks_when_there_is_no_repository(tmp_path: Path) -> None:
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    status = freeze_gate.check_freeze(plain)
    assert not status.ok
    assert "not a git repository" in reasons_text(status)


def test_blocks_when_the_repo_path_does_not_exist(tmp_path: Path) -> None:
    status = freeze_gate.check_freeze(tmp_path / "absent")
    assert not status.ok
    assert "not a directory" in reasons_text(status)


def test_reports_every_reason_at_once(tmp_path: Path) -> None:
    """A blocked gate lists all of its reasons, so one fix does not reveal another."""
    repo = new_repo(tmp_path)
    (repo / "README.md").write_text("Team 10 repository.\n", encoding="utf-8")
    commit_all(repo, "Initial commit")

    status = freeze_gate.check_freeze(repo)
    assert not status.ok
    assert len(status.reasons) == 3, reasons_text(status)
    assert len(status.fixes) == len(status.reasons)


# ---------------------------------------------------------------------------
# CLI behaviour and the JSON contract
# ---------------------------------------------------------------------------

def test_cli_exits_3_and_prints_the_failure_payload(tmp_path: Path) -> None:
    repo = new_repo(tmp_path)            # empty: nothing committed, nothing tagged
    proc = run_cli(repo, "--json")

    assert proc.returncode == freeze_gate.GATE_BLOCKED_EXIT == 3
    payload = json.loads(proc.stdout)
    # Exactly the shape the contract specifies for a blocked gate.
    assert set(payload) == {"ok", "reasons"}
    assert payload["ok"] is False
    assert isinstance(payload["reasons"], list) and payload["reasons"]
    assert all(isinstance(reason, str) for reason in payload["reasons"])
    # The human channel is stderr and must name a command to run.
    assert "FREEZE GATE: BLOCKED" in proc.stderr
    assert "git " in proc.stderr


def test_cli_exits_0_and_prints_the_success_payload(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    proc = run_cli(repo, "--json")

    assert proc.returncode == 0, proc.stderr
    payload = json.loads(proc.stdout)
    assert set(payload) == {
        "ok",
        "freeze_commit",
        "freeze_tag",
        "golden_sha",
        "prediction_sha",
        "golden_rows",
    }
    assert payload["ok"] is True
    assert SHA40.match(payload["freeze_commit"])
    assert payload["freeze_tag"] == TAG
    assert SHA40.match(payload["golden_sha"])
    assert SHA40.match(payload["prediction_sha"])
    assert payload["golden_rows"] == GOLDEN_DATA_ROWS


def test_cli_without_json_is_still_usable(tmp_path: Path) -> None:
    repo = frozen_repo(tmp_path)
    proc = run_cli(repo)
    assert proc.returncode == 0, proc.stderr
    assert "FREEZE GATE: PASS" in proc.stdout


def test_cli_help_needs_no_repository() -> None:
    """--help must work anywhere, including off a git checkout."""
    proc = subprocess.run(
        [sys.executable, str(FREEZE_GATE_PATH), "--help"],
        capture_output=True,
        text=True,
        check=False,
        cwd="/",                     # deliberately outside any git checkout
    )
    assert proc.returncode == 0
    assert "--json" in proc.stdout and "--repo" in proc.stdout


def test_require_freeze_exits_3_when_blocked(tmp_path: Path) -> None:
    repo = new_repo(tmp_path)
    with pytest.raises(SystemExit) as excinfo:
        freeze_gate.require_freeze(repo)
    assert excinfo.value.code == 3
