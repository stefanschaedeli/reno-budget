"""Cryptographic primitives for authentication.

Centralises every security-sensitive operation so that audits review one file:

* :func:`hash_password` / :func:`verify_password` — Argon2id via passlib.
* :func:`generate_token` — URL-safe opaque secrets for refresh / invitation /
  reset tokens.
* :func:`hash_token` — SHA-256 digest used to store opaque secrets at rest
  without enabling impersonation if the DB is leaked.
* :func:`create_access_token` / :func:`decode_access_token` — short-lived JWTs.
* :func:`check_password_policy` — server-side minimum-strength check.

Never bypass these helpers; never reach into ``passlib`` / ``jwt`` directly
from routers or services.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from passlib.context import CryptContext

from app.core.config import get_settings

# Argon2id parameters: passlib defaults for argon2 are tuned for interactive
# logins (~50 ms on modern hardware). We accept these — they match OWASP
# guidance for 2024+.
_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")

# Minimum entropy gate. We do **not** ship zxcvbn (extra dep, heavy) in v1;
# we enforce length + character-class diversity, which already prevents the
# most common offline-cracking targets. Upgrade to zxcvbn in Phase 10 hardening.
_MIN_PASSWORD_LEN = 12
_MAX_PASSWORD_LEN = 128
_LOWER_RE = re.compile(r"[a-z]")
_UPPER_RE = re.compile(r"[A-Z]")
_DIGIT_RE = re.compile(r"\d")
_SPECIAL_RE = re.compile(r"[^A-Za-z0-9]")


class PasswordPolicyError(ValueError):
    """Raised when a candidate password fails the policy."""


def hash_password(plain: str) -> str:
    """Return an Argon2id hash for *plain*."""
    return _pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time-ish password verification."""
    try:
        return _pwd_context.verify(plain, hashed)
    except (ValueError, TypeError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Whether *hashed* should be re-computed (parameters out of date)."""
    return _pwd_context.needs_update(hashed)


def check_password_policy(password: str) -> None:
    """Raise :class:`PasswordPolicyError` if *password* is too weak.

    Policy: length 12-128, must contain at least three of {lowercase, uppercase,
    digit, non-alphanumeric}. Common passwords are rejected via a small denylist.
    """
    if len(password) < _MIN_PASSWORD_LEN:
        raise PasswordPolicyError(
            f"Passwort muss mindestens {_MIN_PASSWORD_LEN} Zeichen lang sein."
        )
    if len(password) > _MAX_PASSWORD_LEN:
        raise PasswordPolicyError(f"Passwort darf höchstens {_MAX_PASSWORD_LEN} Zeichen lang sein.")
    classes = sum(
        bool(rx.search(password)) for rx in (_LOWER_RE, _UPPER_RE, _DIGIT_RE, _SPECIAL_RE)
    )
    if classes < 3:
        raise PasswordPolicyError(
            "Passwort muss Klein-, Grossbuchstaben, Ziffern oder Sonderzeichen "
            "kombinieren (mindestens drei Zeichenklassen)."
        )
    if password.lower() in _COMMON_PASSWORDS:
        raise PasswordPolicyError("Passwort ist zu häufig — bitte ein anderes wählen.")


# A *minimal* denylist; not a full HIBP integration but blocks the worst
# offenders without external dependencies.
_COMMON_PASSWORDS: frozenset[str] = frozenset(
    {
        "passwordpassword",
        "password1234",
        "qwertyuiop12",
        "123456789012",
        "letmeinplease",
        "welcome12345",
        "adminadmin12",
    }
)


# ----- Opaque tokens (refresh / invitation / reset) ---------------------------

_TOKEN_BYTES = 48  # ⇒ 64-char URL-safe string with > 256 bits of entropy


def generate_token() -> str:
    """Return a URL-safe random opaque token."""
    return secrets.token_urlsafe(_TOKEN_BYTES)


def hash_token(token: str) -> str:
    """Return the SHA-256 hex digest of *token* (64 chars)."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ----- JWT access tokens ------------------------------------------------------


@dataclass(slots=True)
class AccessTokenClaims:
    """Decoded JWT payload."""

    sub: uuid.UUID
    exp: datetime
    iat: datetime
    jti: uuid.UUID


def create_access_token(user_id: uuid.UUID, *, ttl: timedelta | None = None) -> str:
    """Issue a short-lived signed JWT for *user_id*."""
    settings = get_settings()
    now = datetime.now(tz=UTC)
    exp = now + (ttl or timedelta(minutes=settings.access_token_ttl_minutes))
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "jti": str(uuid.uuid4()),
        "typ": "access",
    }
    return jwt.encode(
        payload,
        settings.jwt_secret.get_secret_value(),
        algorithm=settings.jwt_algorithm,
    )


def decode_access_token(token: str) -> AccessTokenClaims:
    """Verify *token* and return its claims, raising :class:`jwt.PyJWTError` on failure."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret.get_secret_value(),
        algorithms=[settings.jwt_algorithm],
        options={"require": ["sub", "exp", "iat", "jti"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("Wrong token type")
    return AccessTokenClaims(
        sub=uuid.UUID(payload["sub"]),
        exp=datetime.fromtimestamp(payload["exp"], tz=UTC),
        iat=datetime.fromtimestamp(payload["iat"], tz=UTC),
        jti=uuid.UUID(payload["jti"]),
    )


# ----- CSRF token (double-submit cookie) --------------------------------------


def generate_csrf_token() -> str:
    """Return a URL-safe random CSRF token (kept in a non-HttpOnly cookie)."""
    return secrets.token_urlsafe(32)


def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison."""
    return secrets.compare_digest(a, b)
