"""Pydantic schemas for Suppliers (Phase 11C — API layer).

Suppliers are per-object address-book entries. ``object_id`` is taken
from the URL on create; ``created_by`` from the JWT. Soft-archive via
the dedicated archive endpoint.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class _SupplierBase(BaseModel):
    """Common fields shared by create / update payloads."""

    name: str = Field(min_length=1, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierCreate(_SupplierBase):
    """Create payload. ``object_id`` is taken from the URL."""


class SupplierUpdate(BaseModel):
    """Patch payload — every field optional."""

    name: str | None = Field(default=None, min_length=1, max_length=160)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=40)
    address: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class SupplierRead(_SupplierBase):
    """Outbound DTO including server-assigned fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    archived_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class SupplierListItem(SupplierRead):
    """SupplierRead enriched with the parent object's name (cross-object listing)."""

    object_name: str
