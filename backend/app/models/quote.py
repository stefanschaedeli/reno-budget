"""Quote ORM model (Phase 11C).

A :class:`Quote` is a supplier offer attached to a :class:`~app.models.lot.Lot`.
Quotes preserve historical pricing — the supplier FK uses RESTRICT so an
operator cannot accidentally delete a supplier referenced by a quote
(soft-archive instead).

The ``awarded`` status is mutually exclusive per lot: a partial unique
index on ``(lot_id) WHERE status = 'awarded'`` enforces this at the DB
level. The service-level :func:`~app.services.quotes.award_quote` runs
the lot/quote update transactionally so a partially-applied award is
impossible.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Numeric,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class QuoteStatus(enum.StrEnum):
    """Lifecycle of a quote within a tender."""

    RECEIVED = "received"
    SHORTLISTED = "shortlisted"
    REJECTED = "rejected"
    AWARDED = "awarded"


class Quote(Base):
    """A supplier price offer attached to a tender lot."""

    __tablename__ = "quotes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    lot_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("lots.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    supplier_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        # RESTRICT: preserve historical price evidence; suppliers must be
        # soft-archived (``archived_at``) rather than hard-deleted while
        # any quote still references them.
        ForeignKey("suppliers.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    amount_chf: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    received_at: Mapped[date] = mapped_column(Date, nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[QuoteStatus] = mapped_column(
        Enum(QuoteStatus, name="quote_status", native_enum=False),
        nullable=False,
        default=QuoteStatus.RECEIVED,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    lot: Mapped["Lot"] = relationship(  # noqa: F821
        "Lot",
        foreign_keys=[lot_id],
    )
    supplier: Mapped["Supplier"] = relationship(  # noqa: F821
        "Supplier",
        foreign_keys=[supplier_id],
    )

    __table_args__ = (
        CheckConstraint("amount_chf >= 0", name="ck_quotes_amount_chf_nonneg"),
        # Partial unique index: at most one ``awarded`` quote per lot. The
        # ``postgresql_where`` clause is used by Alembic's migration; the
        # ORM-side declaration here keeps Base.metadata.create_all (used by
        # the test fixtures) in sync.
        Index(
            "uq_quotes_one_awarded_per_lot",
            "lot_id",
            unique=True,
            postgresql_where=text("status = 'awarded'"),
        ),
    )


# Late imports — :class:`Lot` and :class:`Supplier` are loaded as siblings
# via :mod:`app.models.__init__`. The ``relationship`` strings above don't
# require the symbols at class-body time but importing them here ensures
# the mappers can resolve before configure_mappers() is called.
from app.models.lot import Lot  # noqa: E402, F401
from app.models.supplier import Supplier  # noqa: E402, F401
