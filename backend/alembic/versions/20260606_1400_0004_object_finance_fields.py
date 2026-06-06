"""object finance fields: contribution mode + inflation + initial reserve (Phase 4)

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-06 14:00:00

Intent
------
Phase 4 turns the cost-items list into a cashflow plan. The OWNER configures
three new per-object fields that drive the timeline and reserve aggregations:

* ``contribution_mode`` — how the OWNER plans to set aside the reserve
  (monthly / yearly / lump_sum). Display-only on the backend; the API simply
  echoes which mode is configured so the frontend can pick the matching
  presentation.
* ``inflation_rate_percent`` — annual inflation used to compound planned
  amounts forward (``Numeric(5,3)`` so 1.500 = 1.5 %/y). Default 0 keeps the
  legacy "nominal" view for objects that don't set a rate.
* ``initial_reserve_chf`` — money already on hand. Subtracted from the
  required-contribution total before we divide by the planning horizon.

Reversibility
-------------
``downgrade()`` drops the three columns. No data migration needed — defaults
match the legacy implicit behaviour (yearly mode, 0 % inflation, 0 reserve).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "objects",
        sa.Column(
            "contribution_mode",
            sa.String(16),
            nullable=False,
            server_default="yearly",
        ),
    )
    op.add_column(
        "objects",
        sa.Column(
            "inflation_rate_percent",
            sa.Numeric(5, 3),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "objects",
        sa.Column(
            "initial_reserve_chf",
            sa.Numeric(12, 2),
            nullable=False,
            server_default="0",
        ),
    )
    op.create_check_constraint(
        "ck_objects_inflation_rate_range",
        "objects",
        "inflation_rate_percent >= 0 AND inflation_rate_percent <= 20",
    )
    op.create_check_constraint(
        "ck_objects_initial_reserve_nonneg",
        "objects",
        "initial_reserve_chf >= 0",
    )


def downgrade() -> None:
    op.drop_constraint("ck_objects_initial_reserve_nonneg", "objects", type_="check")
    op.drop_constraint("ck_objects_inflation_rate_range", "objects", type_="check")
    op.drop_column("objects", "initial_reserve_chf")
    op.drop_column("objects", "inflation_rate_percent")
    op.drop_column("objects", "contribution_mode")
