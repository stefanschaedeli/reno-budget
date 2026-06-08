"""Pydantic schemas for Projects (Phase 11A — API layer).

A Project groups cost items within a single Object. Projects are
soft-archived (``archived_at`` set to a timestamp) before being optionally
hard-deleted. ``object_id`` and ``created_by`` are always assigned by the
service / route layer — never accepted from the client.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.project import ProjectStatus


class _ProjectBase(BaseModel):
    """Common fields shared by create / update payloads."""

    name: str = Field(min_length=1, max_length=160)
    description: str | None = None
    status: ProjectStatus = ProjectStatus.IDEA
    planned_year: int | None = Field(default=None, ge=1900, le=2200)
    rough_estimate_chf: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )


class ProjectCreate(_ProjectBase):
    """Create payload. ``object_id`` is taken from the URL, ``created_by`` from the JWT."""


class ProjectUpdate(BaseModel):
    """Patch payload — every field optional. Setting ``archived_at`` goes through the
    dedicated archive endpoint instead.
    """

    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = None
    status: ProjectStatus | None = None
    planned_year: int | None = Field(default=None, ge=1900, le=2200)
    rough_estimate_chf: Decimal | None = Field(
        default=None, ge=0, max_digits=12, decimal_places=2
    )


class ProjectRead(_ProjectBase):
    """Outbound DTO including server-assigned fields."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    archived_at: datetime | None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime


class ProjectListItem(ProjectRead):
    """ProjectRead enriched with the parent object's name.

    Used by the cross-object list endpoint at ``GET /api/v1/projects``
    where rows span multiple objects and the UI needs to render the
    parent's name without a second fetch.
    """

    object_name: str
