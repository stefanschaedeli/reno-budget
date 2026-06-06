"""attachments table (Phase 6)

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-06 16:00:00

Intent
------
Phase 6 introduces file uploads attached to either a cost item or an object
(polymorphic ``target_type`` + ``target_id``). The actual file bytes live on
disk under ``RENO_UPLOADS_DIR`` keyed by SHA-256; this table only stores the
metadata (original filename, sniffed mime, size, hash, uploader, target).

Notes
-----
* The compound index ``(target_type, target_id)`` accelerates the dominant
  "list attachments for X" query.
* ``sha256`` is indexed separately so a future garbage-collection job can
  quickly answer "is any row still referencing this hash?".
* No FK exists on ``target_id`` — polymorphism prevents a single-column FK.
  Referential integrity is enforced at the application layer (the upload
  router resolves the parent row + RBAC before insert).

Reversibility
-------------
``downgrade()`` drops the table. The on-disk blobs under
``RENO_UPLOADS_DIR`` are **not** touched — operators retain the raw files
for forensic / recovery purposes after a schema rollback.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
# NOTE: Phase 5 (renofond) is being implemented in parallel and will add
# migration 0005. Before this commit lands we MUST bump ``down_revision`` to
# "0005" to keep the chain unbroken. Tests don't exercise migrations (they
# use ``Base.metadata.create_all``) so the value below keeps the tree usable
# while Phase 5 is in flight.
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("target_type", sa.String(16), nullable=False),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime", sa.String(127), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column(
            "uploaded_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name="ck_attachments_size_nonneg"),
        sa.CheckConstraint(
            "char_length(sha256) = 64",
            name="ck_attachments_sha256_len",
        ),
    )
    op.create_index(
        "ix_attachments_target",
        "attachments",
        ["target_type", "target_id"],
    )
    op.create_index("ix_attachments_sha256", "attachments", ["sha256"])


def downgrade() -> None:
    op.drop_index("ix_attachments_sha256", table_name="attachments")
    op.drop_index("ix_attachments_target", table_name="attachments")
    op.drop_table("attachments")
