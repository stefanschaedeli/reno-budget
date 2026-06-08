"""project rough_estimate_chf (Phase 11B)

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-08 11:00:00

Intent
------
Add a nullable ``rough_estimate_chf`` column to ``projects``. This is the
project's headline "Grobschätzung" — a single CHF figure captured at
creation time as the planning baseline before detailed eBKP-H–mapped cost
items exist (those will sum independently once Phase 5 lands). Stays
freely editable; not derived from cost_items.

Nullable so existing rows survive without backfill.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("rough_estimate_chf", sa.Numeric(12, 2), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("projects", "rough_estimate_chf")
