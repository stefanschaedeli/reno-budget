"""projects, tags, multi-BKP allocations (Phase 11A)

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-07 10:00:00

Intent
------
Phase 11A introduces three new concepts:

* ``projects`` — planning groups of cost items inside one object (e.g.
  "Badsanierung 2027"). Soft-deletable via ``archived_at``.
* ``tags`` + ``tag_assignments`` — per-object key/value labels attachable
  polymorphically to projects, cost items (and in Phase B, lots).
* ``cost_item_bkp_allocations`` — multi-BKP splits for cost items that
  touch several Hauptgruppen (e.g. a refit spanning sanitary + electrical).
  Items using this table leave ``cost_items.bkp_code`` NULL; the column is
  thus made nullable.

Schema changes on ``cost_items``
--------------------------------
* ``bkp_code`` → NULLABLE (FK retained; semantics: NULL means "see
  ``cost_item_bkp_allocations`` or treat as uncategorised").
* New column ``project_id`` (UUID FK → ``projects.id``, ``ON DELETE SET
  NULL``, indexed).

Reversibility
-------------
``downgrade()`` reverses each step in dependency order. The
``bkp_code`` column is restored to NOT NULL — operators MUST migrate any
NULL values back to a valid code before downgrading, otherwise the ALTER
will fail. We intentionally do not auto-pick a code (a guess would corrupt
reports).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ---- projects -----------------------------------------------------------
    op.create_table(
        "projects",
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
        sa.Column("planned_year", sa.Integer(), nullable=True),
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
    op.create_index("ix_projects_object_id", "projects", ["object_id"])

    # ---- tags ---------------------------------------------------------------
    op.create_table(
        "tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(64), nullable=False),
        sa.Column("value", sa.String(64), nullable=False),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "object_id", "key", "value", name="uq_tags_object_key_value"
        ),
        sa.CheckConstraint(
            "color IS NULL OR char_length(color) = 7",
            name="ck_tags_color_hex_len",
        ),
    )
    op.create_index("ix_tags_object_id", "tags", ["object_id"])

    # ---- tag_assignments ----------------------------------------------------
    op.create_table(
        "tag_assignments",
        sa.Column(
            "tag_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tags.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("target_type", sa.String(16), primary_key=True),
        sa.Column(
            "target_id", postgresql.UUID(as_uuid=True), primary_key=True
        ),
    )
    op.create_index(
        "ix_tag_assignments_target",
        "tag_assignments",
        ["target_type", "target_id"],
    )

    # ---- cost_items: bkp_code -> nullable, add project_id -------------------
    op.alter_column("cost_items", "bkp_code", existing_type=sa.String(16), nullable=True)
    op.add_column(
        "cost_items",
        sa.Column(
            "project_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("projects.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("ix_cost_items_project_id", "cost_items", ["project_id"])

    # ---- cost_item_bkp_allocations ------------------------------------------
    op.create_table(
        "cost_item_bkp_allocations",
        sa.Column(
            "cost_item_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_items.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "bkp_code",
            sa.String(16),
            sa.ForeignKey("bkp_codes.code", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column("share_permille", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "share_permille BETWEEN 0 AND 1000",
            name="ck_cost_item_bkp_alloc_share_range",
        ),
    )
    op.create_index(
        "ix_cost_item_bkp_alloc_bkp_code",
        "cost_item_bkp_allocations",
        ["bkp_code"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_cost_item_bkp_alloc_bkp_code",
        table_name="cost_item_bkp_allocations",
    )
    op.drop_table("cost_item_bkp_allocations")

    op.drop_index("ix_cost_items_project_id", table_name="cost_items")
    op.drop_column("cost_items", "project_id")
    # NOTE: an ALTER … SET NOT NULL fails if rows have ``bkp_code IS NULL``.
    # The operator must clean those up beforehand; we don't guess on their
    # behalf — see header comment.
    op.alter_column("cost_items", "bkp_code", existing_type=sa.String(16), nullable=False)

    op.drop_index("ix_tag_assignments_target", table_name="tag_assignments")
    op.drop_table("tag_assignments")

    op.drop_index("ix_tags_object_id", table_name="tags")
    op.drop_table("tags")

    op.drop_index("ix_projects_object_id", table_name="projects")
    op.drop_table("projects")
