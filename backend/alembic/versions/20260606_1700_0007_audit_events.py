"""audit_events table (Phase 7)

Revision ID: 0007
Revises: 0006
Create Date: 2026-06-06 17:00:00

Intent
------
Phase 7 introduces an append-only audit log of mutating actions. Owners
read their own object's history via ``GET /objects/{id}/audit``;
superusers see the global feed via ``GET /audit``.

The table is intentionally simple: one row per event, denormalised actor
email so deletions of the user row keep the historical actor identifiable,
optional ``object_id`` scope, and a JSONB ``payload`` for small structured
diffs.

Indexes
-------
* ``ix_audit_events_object_id_created_at`` — composite, drives the per-
  object owner viewer's keyset pagination.
* ``ix_audit_events_created_at_desc`` — drives the global superuser feed.
* ``ix_audit_events_actor_user_id`` — supports ad-hoc per-actor lookups
  by an operator from a DB shell.

Reversibility
-------------
``downgrade()`` drops the table. There is intentionally no soft-delete or
archive table — operational purge of old events (a future worker phase)
will hard-delete rows.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "audit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "actor_user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actor_email", sa.String(254), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column(
            "object_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("objects.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("target_type", sa.String(32), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("payload", postgresql.JSONB, nullable=True),
        sa.Column("ip_address", sa.String(64), nullable=True),
        sa.Column("user_agent", sa.String(255), nullable=True),
    )
    op.create_index(
        "ix_audit_events_object_id_created_at",
        "audit_events",
        ["object_id", "created_at"],
    )
    op.create_index(
        "ix_audit_events_created_at_desc",
        "audit_events",
        ["created_at"],
    )
    op.create_index(
        "ix_audit_events_actor_user_id",
        "audit_events",
        ["actor_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_audit_events_actor_user_id", table_name="audit_events")
    op.drop_index("ix_audit_events_created_at_desc", table_name="audit_events")
    op.drop_index("ix_audit_events_object_id_created_at", table_name="audit_events")
    op.drop_table("audit_events")
