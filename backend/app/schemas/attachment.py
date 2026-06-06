"""Pydantic schemas for the Attachments API (Phase 6).

Only a read DTO is needed — uploads are ``multipart/form-data`` (no JSON
body), and deletes use the row id from the path.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.attachment import AttachmentTargetType


class AttachmentRead(BaseModel):
    """Outbound DTO for a single attachment row."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_type: AttachmentTargetType
    target_id: uuid.UUID
    sha256: str
    filename: str
    mime: str
    size_bytes: int
    uploaded_by: uuid.UUID | None
    created_at: datetime
