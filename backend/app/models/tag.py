"""Tag + polymorphic TagAssignment ORM models (Phase 11A).

A :class:`Tag` is a per-object label (``key``/``value`` pair, optional
``color``). Tags are attached to multiple kinds of entities via
:class:`TagAssignment` rows — currently :class:`~app.models.project.Project`
and :class:`~app.models.cost.CostItem` (Phase B will add ``lot``).

The polymorphic ``(target_type, target_id)`` pair mirrors the pattern in
:class:`~app.models.attachment.Attachment`. We deliberately do not encode an
FK on ``target_id`` — the router/service layer asserts referential integrity
before insert and on cascade-delete paths.
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
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class TagTargetType(enum.StrEnum):
    """What kind of entity a :class:`TagAssignment` points at.

    Phase B will extend this with ``LOT``. Adding a new value does NOT
    require a migration of the ``Enum`` column because we store it as a
    plain string (``native_enum=False``).
    """

    PROJECT = "project"
    COST_ITEM = "cost_item"
    LOT = "lot"


class Tag(Base):
    """A user-defined ``key=value`` label scoped to a single object."""

    __tablename__ = "tags"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    key: Mapped[str] = mapped_column(String(64), nullable=False)
    value: Mapped[str] = mapped_column(String(64), nullable=False)
    # Hex like '#aabbcc' — validated upstream; nullable for "default colour".
    color: Mapped[str | None] = mapped_column(String(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "object_id", "key", "value", name="uq_tags_object_key_value"
        ),
        CheckConstraint(
            "color IS NULL OR char_length(color) = 7",
            name="ck_tags_color_hex_len",
        ),
    )


class TagAssignment(Base):
    """Links one :class:`Tag` to one target (project / cost item)."""

    __tablename__ = "tag_assignments"

    tag_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("tags.id", ondelete="CASCADE"),
        primary_key=True,
    )
    target_type: Mapped[TagTargetType] = mapped_column(
        Enum(TagTargetType, name="tag_target_type", native_enum=False),
        primary_key=True,
    )
    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True
    )

    __table_args__ = (
        Index("ix_tag_assignments_target", "target_type", "target_id"),
    )
