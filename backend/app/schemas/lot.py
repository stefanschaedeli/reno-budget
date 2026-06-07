"""Pydantic schemas for Lots (Phase 11B — API layer).

A :class:`~app.models.lot.Lot` is a cross-project tender package scoped to
one Object. ``object_id`` is taken from the URL on create; ``created_by``
from the JWT. Membership (cost items) is managed through the dedicated
``/lots/{id}/cost-items`` endpoints — never via the lot CRUD payloads.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.lot import LotStatus
from app.schemas.quote import QuoteRead


class _LotBase(BaseModel):
    """Common fields shared by create / update payloads."""

    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    status: LotStatus = LotStatus.DRAFT
    tender_deadline: date | None = None


class LotCreate(_LotBase):
    """Create payload. ``object_id`` is taken from the URL."""


class LotUpdate(BaseModel):
    """Patch payload — every field optional. Archive goes through the dedicated endpoint."""

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    status: LotStatus | None = None
    tender_deadline: date | None = None


class LotRead(_LotBase):
    """Outbound DTO including server-assigned fields and a count helper.

    ``cost_item_count`` is computed by the service layer (single batched
    query for the list endpoint). ``cost_item_ids`` is populated only on
    the detail endpoint where the caller needs to render member rows.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    awarded_quote_id: uuid.UUID | None = None
    archived_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    cost_item_count: int = 0
    cost_item_ids: list[uuid.UUID] | None = None
    awarded_quote: QuoteRead | None = None
