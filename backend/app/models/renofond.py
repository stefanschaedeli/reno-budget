"""Renofond reserve-contribution model (Phase 5).

Captures **actual** deposits the owner has made into the renovation reserve
("Renofond"). The required-contribution math from Phase 4 told the owner
*how much* they should set aside; this table records *what they actually did*.

Important invariants:

* One row per (object, year, deposit). Multiple deposits per year are allowed
  — we sum them in the projection.
* ``amount_chf`` is non-negative (a withdrawal is just a missed year, not a
  negative row — the projection compares cumulative deposits against the
  cumulative plan).
* CASCADE on ``object_id`` deletion: dropping an object cleans up its
  contribution history.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class ReserveContribution(Base):
    """An actual deposit into the renovation reserve of an object."""

    __tablename__ = "reserve_contributions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    amount_chf: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    note: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    __table_args__ = (
        CheckConstraint("amount_chf >= 0", name="ck_reserve_contributions_amount_nonneg"),
        CheckConstraint(
            "year BETWEEN 1900 AND 2200", name="ck_reserve_contributions_year_range"
        ),
        Index("ix_reserve_contributions_object_year", "object_id", "year"),
    )
