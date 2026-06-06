"""FastAPI dependencies for the auth-aware request scope.

* :func:`get_current_user` decodes the Bearer JWT and loads the matching user.
* :func:`require_superuser` rejects non-admins.
* :func:`get_csrf_protected` enforces the double-submit cookie pattern on
  state-changing requests that use the refresh cookie.

These are dependency factories — never call them directly; always inject via
``Depends`` / ``Annotated``.
"""

from __future__ import annotations

from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, status

from app.core.db import SessionDep
from app.core.security import constant_time_compare, decode_access_token
from app.models.user import User
from app.repositories.user import get_user_by_id


async def get_current_user(
    session: SessionDep,
    authorization: Annotated[str | None, Header()] = None,
) -> User:
    """Return the user identified by the ``Authorization: Bearer <jwt>`` header."""
    if authorization is None or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nicht authentifiziert",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = authorization.split(" ", 1)[1].strip()
    try:
        claims = decode_access_token(token)
    except jwt.PyJWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token ungültig oder abgelaufen",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = await get_user_by_id(session, claims.sub)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Konto nicht verfügbar",
        )
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_superuser(user: CurrentUser) -> User:
    if not user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administratorrechte erforderlich",
        )
    return user


SuperuserDep = Annotated[User, Depends(require_superuser)]


def require_csrf(
    csrf_cookie: Annotated[str | None, Cookie(alias="reno_csrf")] = None,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    """Enforce double-submit CSRF on cookie-bearing state-changing requests."""
    if not csrf_cookie or not csrf_header or not constant_time_compare(csrf_cookie, csrf_header):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF-Token fehlt oder ist ungültig",
        )
