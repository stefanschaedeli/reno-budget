"""objects, units, memberships, unit scopes + extend invitations (Phase 2)

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-06 12:00:00

Intent
------
Introduce the object/unit domain and per-object RBAC. Also augment
``invitations`` with ``object_id``, ``role`` and ``scope_unit_ids`` so that
accepting an invitation can atomically create the corresponding membership.

Reversibility
-------------
``downgrade()`` drops the new tables and the three added invitation columns.
Safe to run on dev databases; do NOT downgrade in production once cost items
referencing units exist (they will be added in Phase 3 and pin the schema).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "objects",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.String(255), nullable=True),
        sa.Column("year_built", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(8), nullable=False),
        sa.Column(
            "planning_horizon_years",
            sa.Integer(),
            nullable=False,
            server_default="30",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "planning_horizon_years BETWEEN 1 AND 100",
            name="ck_objects_planning_horizon_range",
        ),
    )

    op.create_table(
        "units",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", sa.String(64), nullable=False),
        sa.Column("wertquote_permille", sa.Integer(), nullable=False),
        sa.Column("area_m2", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "wertquote_permille BETWEEN 0 AND 1000",
            name="ck_units_wertquote_range",
        ),
        sa.CheckConstraint("area_m2 IS NULL OR area_m2 >= 0", name="ck_units_area_nonneg"),
        sa.UniqueConstraint("object_id", "label", name="uq_units_object_label"),
    )
    op.create_index("ix_units_object_id", "units", ["object_id"])

    op.create_table(
        "object_memberships",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "object_id", name="uq_memberships_user_object"),
    )
    op.create_index("ix_memberships_user_id", "object_memberships", ["user_id"])
    op.create_index("ix_memberships_object_id", "object_memberships", ["object_id"])
    op.create_index(
        "ix_memberships_object_role", "object_memberships", ["object_id", "role"]
    )

    op.create_table(
        "unit_scopes",
        sa.Column(
            "membership_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("object_memberships.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "unit_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("units.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Extend invitations with object/role binding (all nullable for back-compat).
    op.add_column(
        "invitations",
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.add_column("invitations", sa.Column("role", sa.String(16), nullable=True))
    op.add_column(
        "invitations", sa.Column("scope_unit_ids", sa.String(2048), nullable=True)
    )
    op.create_index("ix_invitations_object_id", "invitations", ["object_id"])


def downgrade() -> None:
    op.drop_index("ix_invitations_object_id", table_name="invitations")
    op.drop_column("invitations", "scope_unit_ids")
    op.drop_column("invitations", "role")
    op.drop_column("invitations", "object_id")

    op.drop_table("unit_scopes")

    op.drop_index("ix_memberships_object_role", table_name="object_memberships")
    op.drop_index("ix_memberships_object_id", table_name="object_memberships")
    op.drop_index("ix_memberships_user_id", table_name="object_memberships")
    op.drop_table("object_memberships")

    op.drop_index("ix_units_object_id", table_name="units")
    op.drop_table("units")

    op.drop_table("objects")
