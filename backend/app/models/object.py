"""Object-domain ORM models (Phase 2).

Defines the buildings ("Objekte") tracked by Reno-Budget, their condominium
units ("Stockwerkeinheiten") with Wertquoten in permille, and the per-object
RBAC tables (memberships with optional per-unit scoping).

Important invariants enforced at the ORM/service layer (and re-checked by
Pydantic validators and DB constraints where possible):

* The Wertquoten of all units of an :class:`Object` MUST sum to exactly
  1000 (= 100 %). Validation lives in
  :mod:`app.services.allocations` because it spans multiple rows.
* A single-family house (``ObjectType.SFH``) has exactly one implicit unit
  with ``wertquote_permille = 1000``.
* An :class:`ObjectMembership` MUST be unique per (user, object).
* :class:`UnitScope` rows are only meaningful for non-OWNER roles; an empty
  scope set means "all units" (effectively unscoped).
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.cost import CostItem

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class ObjectType(enum.StrEnum):
    """Whether the building is a single-family house or multi-unit."""

    SFH = "sfh"  # Einfamilienhaus
    MFH = "mfh"  # Mehrfamilienhaus / Stockwerkeigentum


class ObjectRole(enum.StrEnum):
    """Per-object role with strictly decreasing privilege.

    * ``OWNER``    — full control, including memberships and deletion.
    * ``EDITOR``   — create/update cost items, uploads, etc. within scope.
    * ``VIEWER``   — read-only within scope.
    """

    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Object(Base):
    """A building tracked by Reno-Budget.

    The German term is "Objekt" — we keep the English class name to avoid
    shadowing the Python builtin in DB code, but the API and UI use "Objekt".
    """

    __tablename__ = "objects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str | None] = mapped_column(String(255), nullable=True)
    year_built: Mapped[int | None] = mapped_column(Integer, nullable=True)
    type: Mapped[ObjectType] = mapped_column(
        Enum(ObjectType, name="object_type", native_enum=False),
        nullable=False,
    )
    # Planning horizon used by the Renofond projection (Phase 5). 30 y is the
    # Swiss default for renovation reserve planning.
    planning_horizon_years: Mapped[int] = mapped_column(Integer, nullable=False, default=30)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    units: Mapped[list[Unit]] = relationship(
        back_populates="object", cascade="all, delete-orphan", order_by="Unit.label"
    )
    memberships: Mapped[list[ObjectMembership]] = relationship(
        back_populates="object", cascade="all, delete-orphan"
    )
    # Phase 3: cost items live on the object. CASCADE delete ensures dropping
    # an object cleanly removes its renovation plan and its allocations.
    cost_items: Mapped[list[CostItem]] = relationship(
        "CostItem",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        CheckConstraint(
            "planning_horizon_years BETWEEN 1 AND 100",
            name="ck_objects_planning_horizon_range",
        ),
    )


class Unit(Base):
    """A condominium unit ("Stockwerkeinheit") belonging to an :class:`Object`.

    The ``wertquote_permille`` is the Wertquote in *permille* (‰). Using
    integer permille avoids float drift when summing many units; the UI
    formats it as a percentage with one decimal where useful.
    """

    __tablename__ = "units"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    label: Mapped[str] = mapped_column(String(64), nullable=False)
    wertquote_permille: Mapped[int] = mapped_column(Integer, nullable=False)
    area_m2: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    object: Mapped[Object] = relationship(back_populates="units")

    __table_args__ = (
        # Wertquote is permille (0..1000). The aggregate-equals-1000 invariant
        # spans rows and is enforced by app.services.allocations.
        CheckConstraint(
            "wertquote_permille BETWEEN 0 AND 1000",
            name="ck_units_wertquote_range",
        ),
        CheckConstraint("area_m2 IS NULL OR area_m2 >= 0", name="ck_units_area_nonneg"),
        UniqueConstraint("object_id", "label", name="uq_units_object_label"),
    )


class ObjectMembership(Base):
    """Grant of a per-object role to a user.

    OWNER memberships ignore :class:`UnitScope` rows entirely; EDITOR/VIEWER
    memberships are restricted to listed unit IDs if any ``UnitScope`` rows
    exist for the membership (empty set == all units, i.e. unscoped).
    """

    __tablename__ = "object_memberships"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role: Mapped[ObjectRole] = mapped_column(
        Enum(ObjectRole, name="object_role", native_enum=False),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    object: Mapped[Object] = relationship(back_populates="memberships")
    unit_scopes: Mapped[list[UnitScope]] = relationship(
        back_populates="membership", cascade="all, delete-orphan"
    )

    __table_args__ = (
        UniqueConstraint("user_id", "object_id", name="uq_memberships_user_object"),
        Index("ix_memberships_object_role", "object_id", "role"),
    )


class UnitScope(Base):
    """Restricts an EDITOR/VIEWER membership to a specific :class:`Unit`.

    Multiple rows = the union of scopes. No rows for a membership = unscoped
    (all units of the object are visible/editable). Has no effect on OWNER
    memberships; the RBAC service ignores scope rows when ``role == OWNER``.
    """

    __tablename__ = "unit_scopes"

    membership_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("object_memberships.id", ondelete="CASCADE"),
        primary_key=True,
    )
    unit_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("units.id", ondelete="CASCADE"),
        primary_key=True,
    )

    membership: Mapped[ObjectMembership] = relationship(back_populates="unit_scopes")
