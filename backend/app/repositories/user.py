"""Data-access helpers for :class:`User` and auth-adjacent entities.

Repositories return ORM objects but never commit; commits live in the service
layer to keep transactional boundaries explicit.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Invitation, PasswordResetToken, RefreshToken, User


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    stmt = select(User).where(User.email == email.lower())
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_user_by_id(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)


async def get_refresh_token(session: AsyncSession, token_hash: str) -> RefreshToken | None:
    stmt = select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_invitation_by_token_hash(session: AsyncSession, token_hash: str) -> Invitation | None:
    stmt = select(Invitation).where(Invitation.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_password_reset_by_token_hash(
    session: AsyncSession, token_hash: str
) -> PasswordResetToken | None:
    stmt = select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    return (await session.execute(stmt)).scalar_one_or_none()


def utcnow() -> datetime:
    return datetime.now(tz=UTC)
