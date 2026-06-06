"""eBKP-H catalogue, cost items, per-unit allocations (Phase 3)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-06 13:00:00

Intent
------
Add the cost-item domain:

* ``bkp_codes`` — seeded eBKP-H catalogue (top two CRB/SIA levels) plus a
  surface for superuser-added custom codes.
* ``cost_items`` — per-object renovation cost lines (planned + actual CHF).
* ``cost_item_unit_allocations`` — per-unit split of each cost item.

Schema lands first, then the data migration loads ``app/seeds/ebkp_h.json``
into ``bkp_codes`` with ``is_seed = True``. The seed JSON's first array
element is a metadata sentinel (``{"_meta": true, ...}``) and is skipped.

Reversibility
-------------
``downgrade()`` deletes seeded rows (``WHERE is_seed = TRUE``) and drops the
three tables in dependency order. Custom codes (``is_seed = FALSE``) would
prevent table drop via FK; we intentionally do not auto-delete them — the
operator must remove them first. This guards against an accidental
production downgrade obliterating user data.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# Path to the seed file inside the package; resolved relative to this script
# so the migration works both in-repo and from an installed wheel.
_SEED_PATH = Path(__file__).resolve().parents[2] / "app" / "seeds" / "ebkp_h.json"


def _load_seed_rows() -> list[dict[str, object]]:
    """Read the eBKP-H seed JSON, skipping the leading ``_meta`` sentinel."""
    with _SEED_PATH.open(encoding="utf-8") as fh:
        raw = json.load(fh)
    rows: list[dict[str, object]] = []
    for entry in raw:
        if entry.get("_meta"):
            continue
        rows.append(
            {
                "code": entry["code"],
                "parent_code": entry.get("parent_code"),
                "level": entry["level"],
                "label_de": entry["label_de"],
                "description": entry.get("description"),
                "is_seed": True,
            }
        )
    return rows


def upgrade() -> None:
    op.create_table(
        "bkp_codes",
        sa.Column("code", sa.String(16), primary_key=True),
        sa.Column(
            "parent_code",
            sa.String(16),
            sa.ForeignKey("bkp_codes.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("label_de", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_seed", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.CheckConstraint("level BETWEEN 1 AND 4", name="ck_bkp_codes_level_range"),
    )
    op.create_index("ix_bkp_codes_parent_code", "bkp_codes", ["parent_code"])

    op.create_table(
        "cost_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "bkp_code",
            sa.String(16),
            sa.ForeignKey("bkp_codes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("npk_code", sa.String(32), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("priority", sa.String(16), nullable=False),
        sa.Column("planned_year", sa.Integer(), nullable=True),
        sa.Column("planned_amount_chf", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_amount_chf", sa.Numeric(12, 2), nullable=True),
        sa.Column("actual_date", sa.Date(), nullable=True),
        sa.Column("lifespan_years", sa.Integer(), nullable=True),
        sa.Column("warranty_until", sa.Date(), nullable=True),
        sa.Column("scope", sa.String(16), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "planned_amount_chf IS NOT NULL OR actual_amount_chf IS NOT NULL",
            name="ck_cost_items_has_amount",
        ),
        sa.CheckConstraint(
            "planned_amount_chf IS NULL OR planned_amount_chf >= 0",
            name="ck_cost_items_planned_nonneg",
        ),
        sa.CheckConstraint(
            "actual_amount_chf IS NULL OR actual_amount_chf >= 0",
            name="ck_cost_items_actual_nonneg",
        ),
        sa.CheckConstraint(
            "planned_year IS NULL OR planned_year BETWEEN 1900 AND 2200",
            name="ck_cost_items_planned_year_range",
        ),
        sa.CheckConstraint(
            "lifespan_years IS NULL OR lifespan_years BETWEEN 0 AND 200",
            name="ck_cost_items_lifespan_range",
        ),
    )
    op.create_index("ix_cost_items_object_id", "cost_items", ["object_id"])
    op.create_index("ix_cost_items_bkp_code", "cost_items", ["bkp_code"])

    op.create_table(
        "cost_item_unit_allocations",
        sa.Column(
            "cost_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("share_permille", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "share_permille BETWEEN 0 AND 1000",
            name="ck_cost_item_alloc_share_range",
        ),
    )
    op.create_index(
        "ix_cost_item_alloc_unit_id",
        "cost_item_unit_allocations",
        ["unit_id"],
    )

    # ---- Data migration: seed the catalogue ---------------------------------
    seed_table = sa.table(
        "bkp_codes",
        sa.column("code", sa.String),
        sa.column("parent_code", sa.String),
        sa.column("level", sa.Integer),
        sa.column("label_de", sa.String),
        sa.column("description", sa.Text),
        sa.column("is_seed", sa.Boolean),
    )
    rows = _load_seed_rows()
    if rows:
        op.bulk_insert(seed_table, rows)


def downgrade() -> None:
    # Delete seeds first; custom codes (is_seed=false) survive and will block
    # the table drop via FK if any cost_items reference them. That is
    # intentional — see header comment.
    op.execute("DELETE FROM bkp_codes WHERE is_seed = TRUE")

    op.drop_index("ix_cost_item_alloc_unit_id", table_name="cost_item_unit_allocations")
    op.drop_table("cost_item_unit_allocations")

    op.drop_index("ix_cost_items_bkp_code", table_name="cost_items")
    op.drop_index("ix_cost_items_object_id", table_name="cost_items")
    op.drop_table("cost_items")

    op.drop_index("ix_bkp_codes_parent_code", table_name="bkp_codes")
    op.drop_table("bkp_codes")
