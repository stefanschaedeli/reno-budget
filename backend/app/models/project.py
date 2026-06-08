"""Project ORM model (Phase 11A).

A :class:`Project` groups related :class:`~app.models.cost.CostItem` rows
within an :class:`~app.models.object.Object` (e.g. "Badsanierung 2027",
"Dachstock Ausbau"). Projects are optional — cost items may still exist
without a project. Each project belongs to exactly one object and cascades
on delete.

Soft-delete
-----------
``archived_at`` is set when a project is archived (kept for historical
totals) rather than physically deleted. A hard ``DELETE`` cascades cost
items' ``project_id`` to ``NULL`` (FK ``ON DELETE SET NULL``) so the cost
history survives.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime

from decimal import Decimal

from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
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


class ProjectStatus(enum.StrEnum):
    """Lifecycle of a project (mirrors :class:`~app.models.cost.CostItemStatus`)."""

    IDEA = "idea"
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Project(Base):
    """A planning group of cost items within one object."""

    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[ProjectStatus] = mapped_column(
        Enum(ProjectStatus, name="project_status", native_enum=False),
        nullable=False,
        default=ProjectStatus.IDEA,
    )
    planned_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    rough_estimate_chf: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        # SET NULL: preserve project history if the author user is removed.
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
        back_populates="project",
    )



# Late import to avoid circular dependency at module load time. The mapper
# only needs the string ``"CostItem"`` reference resolved when relationships
# are configured.
from app.models.cost import CostItem  # noqa: E402, F401
