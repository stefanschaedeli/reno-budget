"""Pydantic schemas for the audit-log read API (Phase 7).

Only read DTOs are needed — audit events are never created via JSON; they
are written by routers as a side effect of mutations.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class AuditEventRead(BaseModel):
    """Outbound DTO for one audit event row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    actor_user_id: uuid.UUID | None
    actor_email: str
    action: str
    object_id: uuid.UUID | None
    target_type: str | None
    target_id: uuid.UUID | None
    summary: str
    payload: dict[str, Any] | None
    ip_address: str | None
    user_agent: str | None


class AuditEventPage(BaseModel):
    """Keyset-paginated page of audit events.

    ``next_before`` is the ``created_at`` of the last row encoded as ISO
    8601, suitable for the next call's ``?before=`` parameter. ``None``
    means "no more rows".
    """

    items: list[AuditEventRead]
    next_before: str | None
