"""Audit-event ORM model (Phase 7).

Append-only ledger of mutating actions across the system. Owners read their
object's events via ``GET /objects/{id}/audit``; superusers see a global
feed via ``GET /audit``.

Design notes
------------
* **Append-only at the application layer.** We never expose an UPDATE or
  DELETE route for ``audit_events``; routers only write. A future
  worker-phase purge job may delete rows older than the configured
  retention window, but no online code path may.
* ``actor_email`` is denormalised at write-time. If the user row is later
  deleted (``actor_user_id`` is SET NULL via FK), the historical record
  still names the actor. This is the standard pattern for audit log
  longevity.
* ``object_id`` is set when the event has a natural per-object scope so the
  owner-only viewer can filter without a join through ``target_type`` and
  ``target_id``. Auth events (login, password reset) leave it NULL.
* ``payload`` is JSONB and intended for small structured diffs (changed
  field names, before/after of short strings). It must not contain
  secrets, full request bodies, or attachment bytes — anything that
  shouldn't be readable by every owner with viewer access to the log.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


def _utcnow() -> datetime:
    """Tz-aware UTC ``datetime`` for timestamp defaults."""
    return datetime.now(tz=UTC)


class AuditEvent(Base):
    """A single immutable audit-log entry.

    Verbs follow ``noun.verb`` (e.g. ``cost_item.create``). ``summary`` is a
    short German one-liner suitable for direct display in the viewer table.
    """

    __tablename__ = "audit_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False, index=True
    )

    # Actor. NULL for system-driven events (password-reset confirm by token
    # has no logged-in caller). The denormalised email persists if the user
    # is later removed.
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actor_email: Mapped[str] = mapped_column(String(254), nullable=False)

    action: Mapped[str] = mapped_column(String(64), nullable=False)

    # Optional per-object scope used by the owner-viewer.
    object_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("objects.id", ondelete="SET NULL"),
        nullable=True,
    )

    target_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    summary: Mapped[str] = mapped_column(String(500), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)

    __table_args__ = (
        # Per-object viewer query: WHERE object_id = ? ORDER BY created_at DESC, id DESC
        Index(
            "ix_audit_events_object_id_created_at",
            "object_id",
            "created_at",
        ),
        # Global feed for superusers, plus keyset pagination support.
        Index("ix_audit_events_created_at_desc", "created_at"),
        Index("ix_audit_events_actor_user_id", "actor_user_id"),
    )
