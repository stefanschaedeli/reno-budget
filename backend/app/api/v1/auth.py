"""Authentication routes (login / refresh / logout / me / invite / reset).

All cookie-bearing endpoints set:

* ``reno_refresh`` — HttpOnly, Secure, SameSite=Lax, path=``/api/v1/auth``.
* ``reno_csrf``   — readable JS cookie used for the double-submit CSRF pattern.

Rate limits (via :mod:`slowapi`) bracket the brute-forceable endpoints. The
limiter is attached at app-level in :mod:`app.main`.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings
from app.core.db import SessionDep
from app.core.deps import CurrentUser, SuperuserDep, require_csrf
from app.core.security import (
    PasswordPolicyError,
    create_access_token,
    generate_csrf_token,
)
from app.models.user import User
from app.schemas.auth import (
    AcceptInviteRequest,
    InviteRequest,
    InviteResponse,
    LoginRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    TokenResponse,
    UserPublic,
)
from app.services import auth as auth_svc
from app.services.mailer import render_invitation, render_password_reset, send_email

router = APIRouter(prefix="/auth", tags=["auth"])

limiter = Limiter(key_func=get_remote_address, default_limits=[])

REFRESH_COOKIE = "reno_refresh"
CSRF_COOKIE = "reno_csrf"


def _set_session_cookies(response: Response, refresh_token: str, csrf_token: str) -> None:
    settings = get_settings()
    secure = settings.environment != "development"
    max_age = settings.refresh_token_ttl_days * 24 * 3600
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=max_age,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/api/v1/auth",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf_token,
        max_age=max_age,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.delete_cookie(CSRF_COOKIE, path="/")


def _access_token_response(user: User) -> TokenResponse:
    settings = get_settings()
    return TokenResponse(
        access_token=create_access_token(user.id),
        expires_in=settings.access_token_ttl_minutes * 60,
    )


# ---------------------------------------------------------------------------
# Login / refresh / logout / me
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    session: SessionDep,
) -> TokenResponse:
    """Validate credentials and start a session."""
    try:
        user = await auth_svc.authenticate(session, payload.email, payload.password)
    except auth_svc.AccountLockedError as exc:
        await session.commit()  # persist incremented lockout counter
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"Konto gesperrt bis {exc.locked_until.isoformat()}",
        ) from exc
    except auth_svc.AccountInactiveError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Konto deaktiviert",
        ) from exc
    except auth_svc.InvalidCredentialsError as exc:
        await session.commit()  # persist failed-attempt counter
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="E-Mail oder Passwort ungültig",
        ) from exc

    issued = await auth_svc.issue_refresh_token(
        session,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    csrf = generate_csrf_token()
    await session.commit()
    _set_session_cookies(response, issued.token, csrf)
    return _access_token_response(user)


@router.post("/refresh", response_model=TokenResponse, dependencies=[Depends(require_csrf)])
@limiter.limit("60/minute")
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse:
    """Rotate the refresh cookie and issue a fresh access JWT."""
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Keine Sitzung")
    try:
        user, issued = await auth_svc.rotate_refresh_token(
            session,
            refresh_cookie,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except auth_svc.InvalidTokenError as exc:
        await session.commit()  # persist any revocations from replay detection
        _clear_session_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Sitzung ungültig"
        ) from exc

    csrf = generate_csrf_token()
    await session.commit()
    _set_session_cookies(response, issued.token, csrf)
    return _access_token_response(user)


@router.post("/logout", status_code=204, dependencies=[Depends(require_csrf)])
async def logout(
    response: Response,
    session: SessionDep,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    """Revoke the current refresh token and clear cookies."""
    if refresh_cookie:
        await auth_svc.revoke_refresh_token(session, refresh_cookie)
        await session.commit()
    _clear_session_cookies(response)
    return Response(status_code=204)


@router.get("/me", response_model=UserPublic)
async def me(current: CurrentUser) -> User:
    return current


# ---------------------------------------------------------------------------
# Invitations
# ---------------------------------------------------------------------------


@router.post("/invitations", response_model=InviteResponse, status_code=201)
async def create_invitation(
    payload: InviteRequest,
    session: SessionDep,
    admin: SuperuserDep,
) -> InviteResponse:
    """Issue an invitation. Only superusers may invite in Phase 1."""
    try:
        record, token = await auth_svc.issue_invitation(session, payload.email, invited_by=admin.id)
    except auth_svc.InvitationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-Mail ist bereits registriert",
        ) from exc

    await session.commit()

    settings = get_settings()
    subject, body = render_invitation(token, app_base_url="https://reno.local")
    await send_email(record.email, subject, body)

    return InviteResponse(
        id=record.id,
        email=record.email,
        expires_at=record.expires_at,
        token=token if settings.environment in ("development", "test") else None,
    )


@router.post("/invitations/accept", response_model=TokenResponse)
@limiter.limit("20/hour")
async def accept_invitation(
    request: Request,
    response: Response,
    payload: AcceptInviteRequest,
    session: SessionDep,
) -> TokenResponse:
    """Consume an invitation, create the user, start a session."""
    try:
        user = await auth_svc.accept_invitation(
            session,
            payload.token,
            display_name=payload.display_name,
            password=payload.password,
        )
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except auth_svc.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Einladung ungültig oder abgelaufen",
        ) from exc
    except auth_svc.InvitationConflictError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="E-Mail ist bereits registriert",
        ) from exc

    issued = await auth_svc.issue_refresh_token(
        session,
        user,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    csrf = generate_csrf_token()
    await session.commit()
    _set_session_cookies(response, issued.token, csrf)
    return _access_token_response(user)


# ---------------------------------------------------------------------------
# Password reset
# ---------------------------------------------------------------------------


@router.post("/password-reset/request", status_code=202)
@limiter.limit("5/hour")
async def request_password_reset(
    request: Request,
    payload: PasswordResetRequest,
    session: SessionDep,
) -> Response:
    """Issue a reset token if the email is known. Always returns 202."""
    token = await auth_svc.request_password_reset(session, payload.email)
    await session.commit()

    if token is not None:
        subject, body = render_password_reset(token, app_base_url="https://reno.local")
        await send_email(payload.email, subject, body)

    return Response(status_code=202)


@router.post("/password-reset/confirm", status_code=204)
@limiter.limit("10/hour")
async def confirm_password_reset(
    request: Request,
    payload: PasswordResetConfirm,
    session: SessionDep,
) -> Response:
    try:
        await auth_svc.confirm_password_reset(session, payload.token, payload.new_password)
    except PasswordPolicyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc
    except auth_svc.InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reset-Token ungültig, gebraucht oder abgelaufen",
        ) from exc
    await session.commit()
    return Response(status_code=204)
