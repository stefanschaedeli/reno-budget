"""AI assistant ORM models.

The AI Project Assistant turns a freshly-created :class:`~app.models.project.Project`
into a better description, a rough cost estimate, and BKP positions through a
guided wizard. State is persisted so that wizard steps can be re-run later
reusing previously gathered answers, and so the user can resume a session.

Two tables
----------
:class:`AiSession`
    One per (object, project) wizard run. Holds the project-type classification
    and the **gathered answers** (the typed question/answer pairs) as JSON, so a
    later re-run of e.g. the estimate step reuses them without re-asking.

:class:`AiArtifact`
    One row per produced step output (description / estimate / bkp_scope …).
    Stores the structured LLM output and its validation report as JSON, plus a
    draft → accepted/discarded lifecycle. Nothing is written to real
    ``Project`` / ``CostItem`` data until an artifact is **accepted**.

Both cascade-delete with their parent object so AI scratch state never outlives
the property it belongs to.
"""

from __future__ import annotations

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class AiSessionStatus(enum.StrEnum):
    """Lifecycle of a wizard session."""

    ACTIVE = "active"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class AiStep(enum.StrEnum):
    """The pipeline steps. One artifact may be produced per step."""

    CLASSIFY = "classify"
    QUESTION = "question"
    DESCRIBE = "describe"
    ESTIMATE = "estimate"
    BKP_SCOPE = "bkp_scope"


class AiArtifactStatus(enum.StrEnum):
    """Lifecycle of a single step output.

    Artifacts start as ``DRAFT``. Accepting one applies it to real data
    (``Project`` fields or new ``CostItem`` rows) and marks it ``ACCEPTED``.
    ``DISCARDED`` artifacts are kept for the audit trail but never applied.
    """

    DRAFT = "draft"
    ACCEPTED = "accepted"
    DISCARDED = "discarded"


class AiSession(Base):
    """A guided-wizard run for one project."""

    __tablename__ = "ai_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    object_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("projects.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[AiSessionStatus] = mapped_column(
        Enum(AiSessionStatus, name="ai_session_status", native_enum=False),
        nullable=False,
        default=AiSessionStatus.ACTIVE,
    )
    # Project-type classification, set by the classify step (e.g. "roof",
    # "windows"). Drives which questions the questioner asks.
    project_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Typed question/answer pairs gathered across steps, keyed by question
    # ``key``. Reused on re-run so the user is not re-asked. JSON, never NULL.
    answers: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
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

    artifacts: Mapped[list[AiArtifact]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
    )


class AiArtifact(Base):
    """A single step's structured output plus its validation report."""

    __tablename__ = "ai_artifacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("ai_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    step: Mapped[AiStep] = mapped_column(
        Enum(AiStep, name="ai_step", native_enum=False),
        nullable=False,
    )
    status: Mapped[AiArtifactStatus] = mapped_column(
        Enum(AiArtifactStatus, name="ai_artifact_status", native_enum=False),
        nullable=False,
        default=AiArtifactStatus.DRAFT,
    )
    # The schema-validated LLM output for this step (QuestionSet / Estimate /
    # BkpScope …) serialised as JSON.
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    # Deterministic + critic validation findings (L1/L2/L3). JSON; may be empty.
    validation: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )

    session: Mapped[AiSession] = relationship(back_populates="artifacts")
