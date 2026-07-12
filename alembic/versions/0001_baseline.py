"""Baseline schema migration — foundation sprint.

Creates no domain tables. Establishes the Alembic versioning chain so
subsequent sprints can generate incremental revisions cleanly.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op baseline. Domain tables arrive in later sprints."""


def downgrade() -> None:
    """No-op baseline downgrade."""
