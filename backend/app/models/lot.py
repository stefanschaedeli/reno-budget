"""Lot + LotCostItem ORM models (Phase 11B).

A :class:`Lot` is a cross-project *bidding package*: any cost item from any
project in the same Object can be bundled into a lot for tendering. Cost
items remain on their original :class:`~app.models.project.Project`; lot
membership is an orthogonal many-to-many relation captured by
:class:`LotCostItem`.

Invariants
----------
* ``lot.object_id == cost_item.object_id`` for every (lot, cost_item) pair.
  Enforced at the service layer (see ``app.services.lots``); the DB has no
  cross-row check constraint for this because both rows live in different
  tables.
* :attr:`Lot.awarded_quote_id` is added now as a *nullable column without
  FK*. Phase C introduces the ``quotes`` table and the matching migration
  installs the FK constraint then. Adding it now keeps the schema stable
  across phases and avoids a backfill later.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime

from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class LotStatus(enum.StrEnum):
    """Lifecycle of a tender lot."""

    DRAFT = "draft"
    TENDERING = "tendering"
    AWARDED = "awarded"
    CANCELLED = "cancelled"
    COMPLETED = "completed"


class Lot(Base):
    """A cross-project bidding package scoped to one :class:`Object`."""

    __tablename__ = "lots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[LotStatus] = mapped_column(
        Enum(LotStatus, name="lot_status", native_enum=False),
        nullable=False,
        default=LotStatus.DRAFT,
    )
    tender_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    # NOTE: Phase C will add the FK constraint to ``quotes.id``. We keep the
    # column nullable without a constraint now so the schema stays stable
    # and Phase C only adds the ALTER TABLE … ADD CONSTRAINT (no backfill).
    awarded_quote_id = Column(UUID(as_uuid=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # SET NULL: preserve lot history if the author user is removed.
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    cost_items: Mapped[list["CostItem"]] = relationship(  # noqa: F821
        secondary="lot_cost_items",
        back_populates="lots",
    )


class LotCostItem(Base):
    """Junction row linking a :class:`Lot` to a :class:`CostItem`.

    The composite PK ``(lot_id, cost_item_id)`` enforces uniqueness; both
    sides cascade on delete. Whole-item assignment — no share/weight.
    """

    __tablename__ = "lot_cost_items"

    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lots.id", ondelete="CASCADE"),
        primary_key=True,
    )
    cost_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cost_items.id", ondelete="CASCADE"),
        primary_key=True,
    )

    __table_args__ = (
        Index("ix_lot_cost_items_cost_item_id", "cost_item_id"),
    )


# Late import to ensure CostItem's reverse relationship is wired after this
# module is imported by ``app.models``.
from app.models.cost import CostItem  # noqa: E402, F401
