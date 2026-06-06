"""Cost-domain ORM models (Phase 3).

Captures the eBKP-H code catalogue (CRB/SIA classification used in Swiss
construction estimating) together with user-tracked cost items and their
per-unit cost allocations.

Important invariants enforced at the ORM/service/DB layers:

* Every :class:`CostItem` MUST carry at least one monetary amount
  (``planned_amount_chf`` or ``actual_amount_chf``); a zero-amount item is
  meaningless. Monetary amounts are non-negative.
* :class:`CostItemUnitAllocation` rows for one cost item MUST sum to exactly
  ``1000‰`` (= 100 %). The sum invariant spans rows and is enforced in
  :mod:`app.services.allocations` (``validate_allocation_sum``).
* :class:`BkpCode` is a single-rooted forest: ``parent_code`` is nullable for
  root nodes (level 1 "Hauptgruppen") and FK-constrained for descendants.
  ``ON DELETE RESTRICT`` prevents accidental removal of seeded codes that
  have children or are referenced by cost items.
* ``is_seed = True`` marks system-shipped catalogue rows. Custom codes
  inserted by superusers carry ``is_seed = False`` and are the only rows
  removed when a tenant resets their custom catalogue.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class CostItemStatus(enum.StrEnum):
    """Lifecycle of a planned/observed cost item."""

    IDEA = "idea"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class CostItemPriority(enum.StrEnum):
    """User-assigned urgency (drives sorting / digest emails)."""

    LOW = "low"
    MED = "med"
    HIGH = "high"
    URGENT = "urgent"


class CostItemScope(enum.StrEnum):
    """Whether a cost item is borne jointly or by a single unit.

    * ``SHARED`` — split across multiple units by allocation rows. Defaults
      from the object's Wertquoten when none provided.
    * ``UNIT``   — borne by one or more specific units (e.g. private bathroom
      refit). Allocation rows still must sum to 1000‰.
    """

    SHARED = "shared"
    UNIT = "unit"


class BkpCode(Base):
    """An eBKP-H classification code (Hauptgruppe / Elementgruppe / Element).

    The catalogue is seeded with the public CRB/SIA top-two-levels (``is_seed
    = True``). Superusers may extend it with site-specific entries (``is_seed
    = False``). ``parent_code`` is a self-FK that builds the tree; root nodes
    have ``parent_code = None``.
    """

    __tablename__ = "bkp_codes"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    parent_code: Mapped[str | None] = mapped_column(
        String(16),
        # RESTRICT: never let a parent be deleted while children dangle. The
        # seed-removal path in the migration downgrade explicitly orders the
        # deletes from leaves upward.
        ForeignKey("bkp_codes.code", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    label_de: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_seed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    parent: Mapped[BkpCode | None] = relationship(
        back_populates="children",
        remote_side="BkpCode.code",
    )
    children: Mapped[list[BkpCode]] = relationship(
        back_populates="parent",
        order_by="BkpCode.code",
    )

    __table_args__ = (CheckConstraint("level BETWEEN 1 AND 4", name="ck_bkp_codes_level_range"),)


class CostItem(Base):
    """A single planned or actual renovation cost line on an :class:`Object`.

    Money is stored as ``Numeric(12, 2)`` (CHF, two decimals) to avoid float
    drift. The split between *planned* and *actual* lets us compute deltas
    without an extra status table; ``status`` captures lifecycle separately.
    """

    __tablename__ = "cost_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    bkp_code: Mapped[str] = mapped_column(
        String(16),
        ForeignKey("bkp_codes.code", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # NPK (Normpositionen-Katalog) is the SIA item-level catalogue. Stubbed
    # here for Phase 8; we accept and persist the string but don't validate
    # it yet against a master list.
    npk_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[CostItemStatus] = mapped_column(
        Enum(CostItemStatus, name="cost_item_status", native_enum=False),
        nullable=False,
        default=CostItemStatus.IDEA,
    )
    priority: Mapped[CostItemPriority] = mapped_column(
        Enum(CostItemPriority, name="cost_item_priority", native_enum=False),
        nullable=False,
        default=CostItemPriority.MED,
    )
    planned_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    planned_amount_chf: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    actual_amount_chf: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    actual_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    lifespan_years: Mapped[int | None] = mapped_column(Integer, nullable=True)
    warranty_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    scope: Mapped[CostItemScope] = mapped_column(
        Enum(CostItemScope, name="cost_item_scope", native_enum=False),
        nullable=False,
        default=CostItemScope.SHARED,
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # SET NULL: we want history to survive user deletions, but flag the
        # original author as unknown. Keeps audit trail honest.
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    allocations: Mapped[list[CostItemUnitAllocation]] = relationship(
        back_populates="cost_item",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "planned_amount_chf IS NOT NULL OR actual_amount_chf IS NOT NULL",
            name="ck_cost_items_has_amount",
        ),
        CheckConstraint(
            "planned_amount_chf IS NULL OR planned_amount_chf >= 0",
            name="ck_cost_items_planned_nonneg",
        ),
        CheckConstraint(
            "actual_amount_chf IS NULL OR actual_amount_chf >= 0",
            name="ck_cost_items_actual_nonneg",
        ),
        CheckConstraint(
            "planned_year IS NULL OR planned_year BETWEEN 1900 AND 2200",
            name="ck_cost_items_planned_year_range",
        ),
        CheckConstraint(
            "lifespan_years IS NULL OR lifespan_years BETWEEN 0 AND 200",
            name="ck_cost_items_lifespan_range",
        ),
    )


class CostItemUnitAllocation(Base):
    """Splits a :class:`CostItem` across :class:`~app.models.object.Unit` rows.

    The composite PK ``(cost_item_id, unit_id)`` enforces uniqueness; both
    sides cascade on delete (removing the cost item or the unit cleans up
    allocations). The aggregate-equals-1000 invariant is enforced in the
    service layer because it spans rows.
    """

    __tablename__ = "cost_item_unit_allocations"

    cost_item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cost_items.id", ondelete="CASCADE"),
        primary_key=True,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        primary_key=True,
    )
    share_permille: Mapped[int] = mapped_column(Integer, nullable=False)

    cost_item: Mapped[CostItem] = relationship(back_populates="allocations")

    __table_args__ = (
        CheckConstraint(
            "share_permille BETWEEN 0 AND 1000",
            name="ck_cost_item_alloc_share_range",
        ),
        Index("ix_cost_item_alloc_unit_id", "unit_id"),
    )
