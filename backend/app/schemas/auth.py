"""Pydantic request/response schemas for authentication endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"  # noqa: S105 — OAuth2 standard literal, not a secret
    expires_in: int  # seconds


class UserPublic(BaseModel):
    """User fields safe to return to a client."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    display_name: str
    is_active: bool
    is_superuser: bool
    last_login_at: datetime | None = None
    created_at: datetime


class InviteRequest(BaseModel):
    email: EmailStr


class InviteResponse(BaseModel):
    id: uuid.UUID
    email: EmailStr
    expires_at: datetime
    # ``token`` is only returned in non-production builds so an admin can
    # hand-deliver an invitation link when SMTP isn't configured yet.
    token: str | None = None


class AcceptInviteRequest(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=128)


class PasswordResetRequest(BaseModel):
    email: EmailStr


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=128)
    new_password: str = Field(min_length=12, max_length=128)
