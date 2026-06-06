"""Attachment ORM model (Phase 6).

Files (PDFs, photos, contracts, invoices) attached to either a
:class:`~app.models.cost.CostItem` or an :class:`~app.models.object.Object`.

Storage layout
--------------
The bytes themselves live on disk at
``<settings.uploads_dir>/<sha256[:2]>/<sha256>`` (managed by
:mod:`app.services.storage`). The DB row stores only metadata: the original
filename (for ``Content-Disposition``), the sniffed mime type, byte size, the
content hash, the polymorphic target (cost item or object) and the uploader.

Polymorphic target
------------------
We model attachments as a single table with ``(target_type, target_id)`` rather
than two parallel tables because the operational semantics are identical: list
by target, stream by id, RBAC-check via the parent object. The compound index
``(target_type, target_id)`` makes "list attachments for X" cheap.

Cascade behaviour
-----------------
* For ``target_type='cost_item'`` we rely on application-level cascade: when a
  cost item is deleted the attachment rows are deleted explicitly in the
  delete-cost-item service path. (We cannot express a polymorphic FK at the
  schema level.)
* For ``target_type='object'`` likewise.

We deliberately do **not** delete the file on disk when a row is removed —
multiple rows may point at the same content-addressed file (dedup). A future
garbage-collection job (TODO: tracked in docs/architecture/) scans the
storage tree and unlinks blobs whose hash is no longer referenced by any
attachment row.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class AttachmentTargetType(enum.StrEnum):
    """What kind of entity an :class:`Attachment` belongs to."""

    COST_ITEM = "cost_item"
    OBJECT = "object"


class Attachment(Base):
    """A single uploaded file attached to a cost item or an object.

    Security-relevant invariants (enforced upstream in
    :mod:`app.services.storage` and the upload routes):

    * ``mime`` is the **sniffed** type (via ``python-magic``) — never the
      client's ``Content-Type`` header.
    * ``sha256`` is computed server-side while writing the file; this is also
      the content-address used on disk.
    * ``filename`` is the original client filename, sanitised (no path
      separators, null bytes, or ``..`` traversal sequences).
    """

    __tablename__ = "attachments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Polymorphic target. We do not (and cannot) express an FK here — the
    # router layer guarantees referential integrity by checking that the
    # parent row exists *and* that the caller has access before inserting.
    target_type: Mapped[AttachmentTargetType] = mapped_column(
        Enum(AttachmentTargetType, name="attachment_target_type", native_enum=False),
        nullable=False,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False)

    # Content-address: 64-char lowercase hex SHA-256.
    sha256: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    # Original filename for Content-Disposition. Sanitised (see storage svc).
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    # Sniffed mime type; verified against the allowlist before insert.
    mime: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)

    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # SET NULL: preserve attachment history if the uploader is removed.
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        # "List attachments for this target" is the dominant query.
        Index("ix_attachments_target", "target_type", "target_id"),
        CheckConstraint("size_bytes >= 0", name="ck_attachments_size_nonneg"),
        CheckConstraint(
            "char_length(sha256) = 64",
            name="ck_attachments_sha256_len",
        ),
    )
