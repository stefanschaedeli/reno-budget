"""Authentication, invitation and password-reset business logic.

This module owns:

* login (with progressive lockout)
* refresh-token issuance + rotation + revocation
* invitation issuance + acceptance
* password reset request + confirmation

It never speaks HTTP; routers translate exceptions into ``HTTPException``.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import (
    PasswordPolicyError,
    check_password_policy,
    generate_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
)
from app.models.user import Invitation, InvitationStatus, PasswordResetToken, RefreshToken, User
from app.repositories.user import (
    get_invitation_by_token_hash,
    get_password_reset_by_token_hash,
    get_refresh_token,
    get_user_by_email,
    utcnow,
)

# ---- Exceptions --------------------------------------------------------------


class AuthError(Exception):
    """Base for auth-layer errors translated to HTTP 4xx by routers."""


class InvalidCredentialsError(AuthError):
    """Username/password mismatch or unknown user."""


class AccountLockedError(AuthError):
    """Account is in lockout window."""

    def __init__(self, locked_until: datetime) -> None:
        super().__init__("Account locked")
        self.locked_until = locked_until


class AccountInactiveError(AuthError):
    """Account exists but is_active=False."""


class InvalidTokenError(AuthError):
    """Refresh/invitation/reset token does not exist, is expired, used, or revoked."""


class InvitationConflictError(AuthError):
    """Invitation refers to an email that is already a registered user."""


# ---- Result types ------------------------------------------------------------


@dataclass(slots=True)
class IssuedRefresh:
    token: str  # plaintext to send to client
    record: RefreshToken  # persisted row


# ---- Tunables ----------------------------------------------------------------

LOCKOUT_THRESHOLD = 5  # failed attempts before lockout
LOCKOUT_DURATION = timedelta(minutes=15)
INVITATION_TTL = timedelta(days=7)
PASSWORD_RESET_TTL = timedelta(hours=1)


# ---- Refresh tokens ----------------------------------------------------------


async def issue_refresh_token(
    session: AsyncSession,
    user: User,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> IssuedRefresh:
    """Mint a new refresh token, persist its hash, return plaintext + record."""
    settings = get_settings()
    plaintext = generate_token()
    record = RefreshToken(
        user_id=user.id,
        token_hash=hash_token(plaintext),
        issued_at=utcnow(),
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
        user_agent=user_agent,
        ip_address=ip_address,
    )
    session.add(record)
    await session.flush()
    return IssuedRefresh(token=plaintext, record=record)


async def rotate_refresh_token(
    session: AsyncSession,
    presented_token: str,
    *,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> tuple[User, IssuedRefresh]:
    """Atomically revoke *presented_token* and issue a successor.

    Re-use detection: if a token presented here was already revoked, every
    refresh token for the same user is revoked (token theft mitigation).
    """
    existing = await get_refresh_token(session, hash_token(presented_token))
    if existing is None or existing.expires_at <= utcnow():
        raise InvalidTokenError("Refresh token unknown or expired")

    if existing.revoked_at is not None:
        # Replay detected: nuke the whole family
        await _revoke_all_for_user(session, existing.user_id)
        raise InvalidTokenError("Refresh token replay detected")

    user = await session.get(User, existing.user_id)
    if user is None or not user.is_active:
        raise InvalidTokenError("User no longer active")

    new = await issue_refresh_token(session, user, user_agent=user_agent, ip_address=ip_address)
    existing.revoked_at = utcnow()
    existing.replaced_by = new.record.id
    return user, new


async def revoke_refresh_token(session: AsyncSession, presented_token: str) -> None:
    """Best-effort logout: revoke the row matching *presented_token* if any."""
    record = await get_refresh_token(session, hash_token(presented_token))
    if record is not None and record.revoked_at is None:
        record.revoked_at = utcnow()


async def _revoke_all_for_user(session: AsyncSession, user_id: uuid.UUID) -> None:
    from sqlalchemy import update  # local import to keep top imports tidy

    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )


# ---- Login -------------------------------------------------------------------


async def authenticate(session: AsyncSession, email: str, password: str) -> User:
    """Validate credentials, applying progressive lockout.

    Raises one of :class:`InvalidCredentialsError`, :class:`AccountLockedError`
    or :class:`AccountInactiveError`. Never reveals whether the email exists.
    """
    user = await get_user_by_email(session, email)
    if user is None:
        # Perform a dummy verify to even out timing.
        verify_password(password, "$argon2id$v=19$m=65536,t=3,p=4$abcdefghijkl$" + "A" * 43)
        raise InvalidCredentialsError("Unknown user")

    if user.locked_until is not None and user.locked_until > _utcnow_aware():
        raise AccountLockedError(user.locked_until)

    if not verify_password(password, user.password_hash):
        user.failed_login_attempts += 1
        if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
            user.locked_until = _utcnow_aware() + LOCKOUT_DURATION
            user.failed_login_attempts = 0
        raise InvalidCredentialsError("Bad password")

    if not user.is_active:
        raise AccountInactiveError("Inactive account")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = _utcnow_aware()

    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    return user


def _utcnow_aware() -> datetime:
    """Aware UTC ``datetime`` for comparisons with TZ-aware DB columns."""
    return datetime.now(tz=UTC)


# ---- Invitations -------------------------------------------------------------


async def issue_invitation(
    session: AsyncSession,
    email: str,
    *,
    invited_by: uuid.UUID | None,
    object_id: uuid.UUID | None = None,
    role: str | None = None,
    scope_unit_ids_encoded: str | None = None,
) -> tuple[Invitation, str]:
    """Create a pending invitation; return record + plaintext token.

    When ``object_id`` and ``role`` are supplied, the invitation is bound to
    that object — accepting it will create an :class:`ObjectMembership` with
    the given role (and optional unit scope via ``scope_unit_ids_encoded``,
    a JSON string produced by
    :func:`app.services.objects.encode_scope_unit_ids`).
    """
    email = email.lower().strip()
    existing_user = await get_user_by_email(session, email)
    if existing_user is not None:
        raise InvitationConflictError("Email already registered")

    plaintext = generate_token()
    record = Invitation(
        email=email,
        invited_by=invited_by,
        token_hash=hash_token(plaintext),
        expires_at=utcnow() + INVITATION_TTL,
        object_id=object_id,
        role=role,
        scope_unit_ids=scope_unit_ids_encoded,
    )
    session.add(record)
    await session.flush()
    return record, plaintext


async def accept_invitation(
    session: AsyncSession,
    token: str,
    *,
    display_name: str,
    password: str,
) -> User:
    """Consume a pending invitation and create the user account."""
    invitation = await get_invitation_by_token_hash(session, hash_token(token))
    if (
        invitation is None
        or invitation.status != InvitationStatus.PENDING
        or invitation.expires_at <= utcnow()
    ):
        raise InvalidTokenError("Invitation invalid or expired")

    try:
        check_password_policy(password)
    except PasswordPolicyError:
        raise

    existing = await get_user_by_email(session, invitation.email)
    if existing is not None:
        invitation.status = InvitationStatus.REVOKED
        raise InvitationConflictError("Email already registered")

    user = User(
        email=invitation.email,
        display_name=display_name.strip(),
        password_hash=hash_password(password),
        is_active=True,
        is_superuser=False,
    )
    session.add(user)

    invitation.status = InvitationStatus.ACCEPTED
    invitation.accepted_at = utcnow()

    await session.flush()

    # Phase 2: if the invitation is bound to an object, create the membership.
    # Local import keeps services/auth.py independent of the object domain at
    # import time (avoids circular imports during Alembic autogenerate).
    from app.services.objects import apply_invitation_membership

    await apply_invitation_membership(session, invitation=invitation, user_id=user.id)

    return user


# ---- Password reset ----------------------------------------------------------


async def request_password_reset(session: AsyncSession, email: str) -> str | None:
    """Issue a password-reset token if the email is known; return plaintext.

    Returns ``None`` if the email is not registered. Callers MUST behave
    identically in both cases to avoid email enumeration.
    """
    user = await get_user_by_email(session, email)
    if user is None:
        return None
    plaintext = generate_token()
    record = PasswordResetToken(
        user_id=user.id,
        token_hash=hash_token(plaintext),
        expires_at=utcnow() + PASSWORD_RESET_TTL,
    )
    session.add(record)
    await session.flush()
    return plaintext


async def confirm_password_reset(session: AsyncSession, token: str, new_password: str) -> User:
    """Consume a password-reset token and rotate the user's password."""
    record = await get_password_reset_by_token_hash(session, hash_token(token))
    if record is None or record.used_at is not None or record.expires_at <= utcnow():
        raise InvalidTokenError("Reset token invalid, used, or expired")

    check_password_policy(new_password)

    user = await session.get(User, record.user_id)
    if user is None:
        raise InvalidTokenError("User no longer exists")

    user.password_hash = hash_password(new_password)
    user.failed_login_attempts = 0
    user.locked_until = None

    record.used_at = utcnow()

    # Revoke all refresh tokens — force re-login on every device.
    await _revoke_all_for_user(session, user.id)

    return user
