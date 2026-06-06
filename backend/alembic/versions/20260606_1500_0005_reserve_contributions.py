"""reserve_contributions table (Phase 5 — Renofond projections)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-06 15:00:00

Intent
------
Phase 5 records the **actual** deposits the owner has made into the
renovation reserve ("Renofond"). Phase 4 already computes how much *should*
be set aside per year; this table lets the projection compare that target
against reality and surface underfunding years.

One row per deposit (multiple per year are allowed and summed in the
service). ``year`` is an integer (calendar year) rather than a date because
contributions are conceptually per-period; we don't care about the day.

Reversibility
-------------
``downgrade()`` drops the table. Data is lost — operators should export
any history before downgrading.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reserve_contributions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("year", sa.Integer(), nullable=False),
        sa.Column("amount_chf", sa.Numeric(12, 2), nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "amount_chf >= 0", name="ck_reserve_contributions_amount_nonneg"
        ),
        sa.CheckConstraint(
            "year BETWEEN 1900 AND 2200", name="ck_reserve_contributions_year_range"
        ),
    )
    op.create_index(
        "ix_reserve_contributions_object_id",
        "reserve_contributions",
        ["object_id"],
    )
    op.create_index(
        "ix_reserve_contributions_object_year",
        "reserve_contributions",
        ["object_id", "year"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_reserve_contributions_object_year", table_name="reserve_contributions"
    )
    op.drop_index(
        "ix_reserve_contributions_object_id", table_name="reserve_contributions"
    )
    op.drop_table("reserve_contributions")
