"""Pydantic schemas for Quotes (Phase 11C — API layer).

A Quote is a supplier offer attached to a Lot. ``lot_id`` comes from the
URL on create; ``supplier_id`` from the payload (validated server-side
to belong to the same Object). The ``awarded`` status is set ONLY via
the dedicated award endpoint — direct PATCH ignores attempts to set it.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.quote import QuoteStatus


class _QuoteBase(BaseModel):
    """Common fields shared by create / update payloads."""

    amount_chf: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    received_at: date
    valid_until: date | None = None
    notes: str | None = None
    status: QuoteStatus = QuoteStatus.RECEIVED


class QuoteCreate(BaseModel):
    """Create payload. ``lot_id`` is taken from the URL."""

    supplier_id: uuid.UUID
    amount_chf: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    received_at: date
    valid_until: date | None = None
    notes: str | None = None
    status: QuoteStatus = QuoteStatus.RECEIVED


class QuoteUpdate(BaseModel):
    """Patch payload — every field optional. Status may NOT be set to
    ``awarded`` here; use the dedicated award endpoint instead."""

    amount_chf: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )
    received_at: date | None = None
    valid_until: date | None = None
    notes: str | None = None
    status: QuoteStatus | None = None


class QuoteRead(_QuoteBase):
    """Outbound DTO including server-assigned fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lot_id: uuid.UUID
    supplier_id: uuid.UUID
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
