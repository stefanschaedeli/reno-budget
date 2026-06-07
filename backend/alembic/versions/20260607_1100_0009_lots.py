"""lots + lot_cost_items junction (Phase 11B)

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-07 11:00:00

Intent
------
Introduce the Lot concept — a cross-project bidding package scoped to one
Object. A Lot bundles any number of :class:`CostItem` rows from the same
object into a tender package; Phase C will hang Suppliers/Quotes off it.

Schema changes
--------------
* Create ``lots`` table.
    - ``status`` stored as ``String(16)`` (matches the project_status
      pattern — Enum is ``native_enum=False`` on the ORM side).
    - ``awarded_quote_id`` is added now as a plain nullable UUID column
      with NO foreign-key constraint. Phase C will add the FK once the
      ``quotes`` table exists; doing it now keeps the column shape stable
      across phases and means Phase C only adds a constraint (no
      backfill, no rewriting of existing rows).
* Create ``lot_cost_items`` junction table (composite PK, both FKs CASCADE).
* The ``tag_assignments.target_type`` column is ``String(16)`` already and
  the ORM ``TagTargetType`` enum is ``native_enum=False`` — adding the
  ``"lot"`` value requires NO ALTER and is covered by this revision only
  semantically (header comment).

Reversibility
-------------
``downgrade()`` drops both tables in dependency order. Any ``lot``
tag_assignment rows live in the existing ``tag_assignments`` table and
must be cleaned up by the operator before downgrading (they would be
orphaned, not corrupt).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- lots ---------------------------------------------------------------
    op.create_table(
        "lots",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("tender_deadline", sa.Date(), nullable=True),
        # No FK — Phase C will install ``ALTER TABLE lots ADD CONSTRAINT
        # fk_lots_awarded_quote_id FOREIGN KEY (awarded_quote_id) REFERENCES
        # quotes(id) ON DELETE SET NULL`` once the ``quotes`` table exists.
        sa.Column("awarded_quote_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_lots_object_id", "lots", ["object_id"])

    # ---- lot_cost_items -----------------------------------------------------
    op.create_table(
        "lot_cost_items",
        sa.Column(
            "lot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lots.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "cost_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )
    op.create_index(
        "ix_lot_cost_items_cost_item_id",
        "lot_cost_items",
        ["cost_item_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_lot_cost_items_cost_item_id", table_name="lot_cost_items"
    )
    op.drop_table("lot_cost_items")

    op.drop_index("ix_lots_object_id", table_name="lots")
    op.drop_table("lots")
