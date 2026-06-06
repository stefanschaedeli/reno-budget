"""HTTP routes for reading the audit log (Phase 7).

Two endpoints:

* ``GET /objects/{id}/audit`` — OWNER-only on that object. Returns events
  scoped to ``object_id == id``.
* ``GET /audit`` — superuser-only. Returns the global feed.

Both endpoints use keyset pagination by ``(created_at, id)`` descending.
The ``before`` cursor is an ISO-8601 timestamp; rows with
``created_at < before`` are returned. We use ``<`` rather than ``<=`` and
break ties on ``id`` (descending) to guarantee distinct, stable pages even
when many events share a microsecond.

The audit log is never editable via HTTP — there are no POST/PATCH/DELETE
routes. Writes happen as a side effect of mutations in other routers via
:mod:`app.services.audit`.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionDep
from app.core.deps import SuperuserDep, require_object_access_dep
from app.models.audit import AuditEvent
from app.models.object import ObjectRole
from app.schemas.audit import AuditEventPage, AuditEventRead
from app.services.rbac import ObjectAccess

router = APIRouter(prefix="", tags=["audit"])


def _parse_cursor(before: str | None) -> datetime | None:
    """Parse the ``?before=`` query into an aware UTC ``datetime``.

    Accepts ISO 8601. Trailing ``Z`` is normalised to ``+00:00`` so
    ``datetime.fromisoformat`` accepts it on all supported Python versions.
    """
    if not before:
        return None
    raw = before.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Ungültiger Cursor",
        ) from exc


async def _page(
    session: AsyncSession,
    *,
    object_id: uuid.UUID | None,
    limit: int,
    before: datetime | None,
) -> AuditEventPage:
    """Run the keyset-paginated query.

    Returns up to ``limit`` events ordered by ``(created_at DESC, id DESC)``.
    ``next_before`` is the ``created_at`` of the last row when the page
    appears to be full; otherwise ``None``.
    """
    stmt = select(AuditEvent)
    if object_id is not None:
        stmt = stmt.where(AuditEvent.object_id == object_id)
    if before is not None:
        stmt = stmt.where(AuditEvent.created_at < before)
    stmt = stmt.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    items = [AuditEventRead.model_validate(r) for r in rows]
    # Page is "full" exactly when we got ``limit`` rows. We expose the
    # ``created_at`` of the last row as the next cursor; the next page will
    # use strict ``<`` so we never return the same row twice.
    next_before = items[-1].created_at.isoformat() if len(items) == limit else None
    return AuditEventPage(items=items, next_before=next_before)


@router.get("/objects/{object_id}/audit", response_model=AuditEventPage)
async def list_object_audit(
    object_id: uuid.UUID,
    _: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    before: str | None = Query(default=None),
) -> AuditEventPage:
    """List recent audit events for ``object_id``. Caller MUST be OWNER.

    Editors and viewers get 403; outsiders get 404 (via the dependency).
    Use ``?before=<cursor>`` from the previous response's ``next_before``
    to fetch older pages.
    """
    cursor = _parse_cursor(before)
    return await _page(session, object_id=object_id, limit=limit, before=cursor)


@router.get("/audit", response_model=AuditEventPage)
async def list_global_audit(
    _admin: SuperuserDep,
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=200),
    before: str | None = Query(default=None),
) -> AuditEventPage:
    """Global audit feed for superusers. Non-superusers get 403."""
    cursor = _parse_cursor(before)
    return await _page(session, object_id=None, limit=limit, before=cursor)
