"""suppliers + quotes + lot.awarded_quote_id FK (Phase 11C — procurement)

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-08 10:00:00

Intent
------
Introduce the Supplier + Quote tables that complete the procurement
workflow. A :class:`Quote` is a supplier offer attached to a
:class:`Lot`. Awarding is exclusive per lot — enforced at the DB level
by a partial unique index on ``(lot_id) WHERE status = 'awarded'``.

Schema changes
--------------
* Create ``suppliers`` table (per-object address book).
* Create ``quotes`` table (lot ↔ supplier offers).
* Create partial unique index ``uq_quotes_one_awarded_per_lot`` to
  enforce at most one awarded quote per lot at the database level.
* Add the FK constraint ``lots.awarded_quote_id → quotes.id (SET NULL)``.
  Phase B added the column (no constraint) so this is just an
  ``ALTER TABLE ADD CONSTRAINT`` with no data backfill.

Reversibility
-------------
``downgrade()`` drops the FK BEFORE dropping the ``quotes`` table —
otherwise the constraint would block table removal. The ``suppliers``
table is dropped last as ``quotes.supplier_id`` references it.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- suppliers ----------------------------------------------------------
    op.create_table(
        "suppliers",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("contact_email", sa.String(254), nullable=True),
        sa.Column("contact_phone", sa.String(40), nullable=True),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
    op.create_index("ix_suppliers_object_id", "suppliers", ["object_id"])

    # ---- quotes -------------------------------------------------------------
    op.create_table(
        "quotes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "lot_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("lots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "supplier_id",
            postgresql.UUID(as_uuid=True),
            # RESTRICT: a supplier with any quote attached cannot be hard
            # deleted; soft-archive instead. This preserves historical
            # price evidence.
            sa.ForeignKey("suppliers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("amount_chf", sa.Numeric(12, 2), nullable=False),
        sa.Column("received_at", sa.Date(), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("amount_chf >= 0", name="ck_quotes_amount_chf_nonneg"),
    )
    op.create_index("ix_quotes_lot_id", "quotes", ["lot_id"])
    op.create_index("ix_quotes_supplier_id", "quotes", ["supplier_id"])
    # Partial unique index: at most one awarded quote per lot. Postgres
    # only enforces uniqueness on rows matching the WHERE clause, so we
    # can freely award/un-award without conflicting with non-awarded
    # quotes on the same lot.
    op.create_index(
        "uq_quotes_one_awarded_per_lot",
        "quotes",
        ["lot_id"],
        unique=True,
        postgresql_where=sa.text("status = 'awarded'"),
    )

    # ---- lots.awarded_quote_id FK ------------------------------------------
    op.create_foreign_key(
        "fk_lots_awarded_quote_id",
        "lots",
        "quotes",
        ["awarded_quote_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Drop the FK first so the quotes table can be removed without
    # the constraint blocking it.
    op.drop_constraint("fk_lots_awarded_quote_id", "lots", type_="foreignkey")

    op.drop_index("uq_quotes_one_awarded_per_lot", table_name="quotes")
    op.drop_index("ix_quotes_supplier_id", table_name="quotes")
    op.drop_index("ix_quotes_lot_id", table_name="quotes")
    op.drop_table("quotes")

    op.drop_index("ix_suppliers_object_id", table_name="suppliers")
    op.drop_table("suppliers")
