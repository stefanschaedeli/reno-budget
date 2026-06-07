"""Pydantic schemas for Tags + polymorphic TagAssignment (Phase 11A — API layer).

Tags are per-object ``key=value`` labels with optional hex colour. They are
attached to other entities via :class:`~app.models.tag.TagAssignment` rows
whose ``(target_type, target_id)`` pair points polymorphically at a
:class:`~app.models.project.Project` or a :class:`~app.models.cost.CostItem`.

The route layer enforces that the tag and its target belong to the same
object (cross-object assignments are rejected as 422).
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.tag import TagTargetType

_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{6}$")


class _TagBase(BaseModel):
    """Shared fields for create / update payloads."""

    key: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=64)
    color: str | None = Field(default=None, min_length=7, max_length=7)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("Farbe muss ein Hex-Wert wie '#aabbcc' sein")
        return v.lower()


class TagCreate(_TagBase):
    """Create payload. ``object_id`` is taken from the URL."""


class TagUpdate(BaseModel):
    """Patch payload — every field optional."""

    key: str | None = Field(default=None, min_length=1, max_length=64)
    value: str | None = Field(default=None, min_length=1, max_length=64)
    color: str | None = Field(default=None, min_length=7, max_length=7)

    @field_validator("color")
    @classmethod
    def _validate_color(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if not _HEX_COLOR_RE.match(v):
            raise ValueError("Farbe muss ein Hex-Wert wie '#aabbcc' sein")
        return v.lower()


class TagRead(_TagBase):
    """Outbound DTO."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    created_at: datetime


# ---- Tag assignments --------------------------------------------------------


class TagAssignmentCreate(BaseModel):
    """Payload for ``POST /tags/{tag_id}/assignments``."""

    target_type: TagTargetType
    target_id: uuid.UUID


class TagAssignmentRead(BaseModel):
    """Outbound DTO for a tag assignment row."""

    model_config = ConfigDict(from_attributes=True)

    tag_id: uuid.UUID
    target_type: TagTargetType
    target_id: uuid.UUID
