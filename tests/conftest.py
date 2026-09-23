"""Shared pytest fixtures.

Keeps the repository root on ``sys.path`` (belt and braces alongside the
``pythonpath`` setting in ``pyproject.toml``) so that ``service`` and
``analysis`` import cleanly no matter where pytest is invoked from.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture()
def repo_root() -> Path:
    """Absolute path to the repository root."""
    return REPO_ROOT


@pytest.fixture()
def synthetic_tickets_csv(repo_root: Path) -> Path:
    """The hand-written dev tickets. NEVER the team rows."""
    return repo_root / "data" / "dev" / "synthetic_tickets.csv"
