"""ai assistant sessions + artifacts (AI Project Assistant)

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-21 12:00:00

Intent
------
Add the two tables backing the AI Project Assistant wizard:

* ``ai_sessions`` — one wizard run per (object, project). Holds the project-type
  classification and the gathered typed answers (JSONB) so steps can be re-run
  without re-asking.
* ``ai_artifacts`` — one row per produced step output (description / estimate /
  bkp_scope …) with the structured LLM output and validation report as JSONB and
  a draft → accepted/discarded lifecycle.

Both cascade-delete with their parent object/project so AI scratch state never
outlives the property it belongs to. All enums are non-native (stored as
strings) matching the rest of the schema.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ai_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("object_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("project_type", sa.String(length=64), nullable=True),
        sa.Column(
            "answers",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["object_id"], ["objects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_sessions_object_id", "ai_sessions", ["object_id"], unique=False
    )
    op.create_index(
        "ix_ai_sessions_project_id", "ai_sessions", ["project_id"], unique=False
    )

    op.create_table(
        "ai_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("step", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False),
        sa.Column("output", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "validation",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"], ["ai_sessions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_artifacts_session_id", "ai_artifacts", ["session_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_ai_artifacts_session_id", table_name="ai_artifacts")
    op.drop_table("ai_artifacts")
    op.drop_index("ix_ai_sessions_project_id", table_name="ai_sessions")
    op.drop_index("ix_ai_sessions_object_id", table_name="ai_sessions")
    op.drop_table("ai_sessions")
