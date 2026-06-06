"""Audit-log write service (Phase 7).

Single entry point :func:`record` is called from routers (or services that
already have the actor + request in scope) to append a single
:class:`~app.models.audit.AuditEvent` row.

Contract
--------
* The function **flushes** so the row's ``id``/``created_at`` are available
  if the caller needs them, but it **does not commit**. The caller's
  transaction owns the commit so that the audit row and the side effect
  it describes land atomically — either both or neither.
* The function is best-effort safe: any persistence failure here aborts the
  surrounding transaction (we never silently swallow). That is by design:
  if we can't write the log, we should not pretend the action succeeded.
* IP / User-Agent are sniffed from the ``Request`` when provided. We never
  store anything from the body — only the few headers a load balancer
  would already see.
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditEvent
from app.models.user import User

# Action verb constants. Keep verbs short and stable — they appear in the
# DB and any operator querying historical events relies on them.
ACTION_AUTH_LOGIN = "auth.login"
ACTION_AUTH_PASSWORD_RESET_REQUEST = "auth.password_reset_request"  # noqa: S105
ACTION_AUTH_PASSWORD_RESET_CONFIRM = "auth.password_reset_confirm"  # noqa: S105
ACTION_AUTH_INVITATION_ACCEPT = "auth.invitation_accept"

ACTION_OBJECT_CREATE = "object.create"
ACTION_OBJECT_UPDATE = "object.update"
ACTION_OBJECT_DELETE = "object.delete"
ACTION_OBJECT_UNITS_REPLACE = "object.units_replace"
ACTION_OBJECT_EXPORT = "object.export"

ACTION_MEMBERSHIP_GRANT = "membership.grant"
ACTION_MEMBERSHIP_UPDATE = "membership.update"
ACTION_MEMBERSHIP_REVOKE = "membership.revoke"

ACTION_COST_ITEM_CREATE = "cost_item.create"
ACTION_COST_ITEM_UPDATE = "cost_item.update"
ACTION_COST_ITEM_DELETE = "cost_item.delete"

ACTION_ATTACHMENT_UPLOAD = "attachment.upload"
ACTION_ATTACHMENT_DELETE = "attachment.delete"

ACTION_RESERVE_CONTRIBUTION_CREATE = "reserve_contribution.create"
ACTION_RESERVE_CONTRIBUTION_DELETE = "reserve_contribution.delete"

ACTION_BKP_CODE_CREATE = "bkp_code.create"


def _client_meta(request: Request | None) -> tuple[str | None, str | None]:
    """Extract ``(ip_address, user_agent)`` from ``request`` if present.

    The IP is the direct socket peer. Operators running this behind an
    upstream proxy (the recommended deployment) get the proxy's address
    here; the upstream proxy logs the original client. We do NOT honour
    ``X-Forwarded-For`` because it is trivially spoofable.
    """
    if request is None:
        return None, None
    ip = request.client.host if request.client else None
    ua = request.headers.get("user-agent")
    if ua is not None and len(ua) > 255:
        ua = ua[:255]
    return ip, ua


async def record(
    session: AsyncSession,
    *,
    actor: User | None,
    actor_email: str | None = None,
    action: str,
    object_id: uuid.UUID | None = None,
    target_type: str | None = None,
    target_id: uuid.UUID | None = None,
    summary: str,
    payload: dict[str, Any] | None = None,
    request: Request | None = None,
) -> AuditEvent:
    """Append a single audit event.

    Parameters
    ----------
    actor:
        The acting user. Pass ``None`` for system-driven events
        (e.g. password reset confirmation via token where no JWT was
        presented). ``actor_email`` is required in that case.
    actor_email:
        Optional override; defaults to ``actor.email``. Useful when the
        actor row is mid-creation (invitation accept) or absent.
    action:
        Stable verb-noun string. Use a constant from this module.
    object_id:
        Object scope for the per-object viewer. Optional.
    target_type / target_id:
        Free-form classification of the affected row.
    summary:
        Short human-readable German one-liner.
    payload:
        Optional structured diff (JSON-serialisable).
    request:
        FastAPI :class:`Request` — used to capture ip + user-agent.
    """
    if actor is None and not actor_email:
        raise ValueError("audit.record requires either actor or actor_email")
    email = actor_email or (actor.email if actor is not None else "")
    ip, ua = _client_meta(request)
    event = AuditEvent(
        actor_user_id=actor.id if actor is not None else None,
        actor_email=email,
        action=action,
        object_id=object_id,
        target_type=target_type,
        target_id=target_id,
        summary=summary,
        payload=payload,
        ip_address=ip,
        user_agent=ua,
    )
    session.add(event)
    await session.flush()
    return event
