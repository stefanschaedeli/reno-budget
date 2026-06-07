"""HTTP routes for Quotes + Award transaction (Phase 11C).

Two routers:

* :data:`router_lots` — list/create at ``/lots/{lot_id}/quotes`` and
  ``POST /lots/{lot_id}/quotes/{quote_id}/award``.
* :data:`router_quotes` — per-quote get/patch/delete at
  ``/quotes/{quote_id}``.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf
from app.models.lot import Lot
from app.models.object import ObjectRole
from app.models.quote import Quote
from app.schemas.quote import QuoteCreate, QuoteRead, QuoteUpdate
from app.services import audit as audit_svc
from app.services.quotes import (
    QuoteAwardConflictError,
    QuoteDeleteForbiddenError,
    QuoteNotFoundError,
    QuoteScopeError,
    QuoteServiceError,
    QuoteStatusForbiddenError,
    award_quote,
    create_quote,
    delete_quote,
    get_quote,
    list_quotes,
    update_quote,
)
from app.services.rbac import ObjectAccess
from app.services.rbac import require_object_access as _require_access

router_lots = APIRouter(prefix="/lots/{lot_id}/quotes", tags=["quotes"])
router_quotes = APIRouter(prefix="/quotes", tags=["quotes"])


def _to_read(q: Quote) -> QuoteRead:
    return QuoteRead.model_validate(q)


def _raise_for(exc: QuoteServiceError) -> None:
    if isinstance(exc, QuoteNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, QuoteScopeError | QuoteStatusForbiddenError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    if isinstance(exc, QuoteAwardConflictError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, QuoteDeleteForbiddenError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _lot_and_access(
    session: SessionDep,
    user: CurrentUser,
    lot_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Lot, ObjectAccess]:
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Los nicht gefunden")
    access = await _require_access(session, user, lot.object_id, minimum)
    return lot, access


async def _quote_and_access(
    session: SessionDep,
    user: CurrentUser,
    quote_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Quote, Lot, ObjectAccess]:
    quote = await session.get(Quote, quote_id)
    if quote is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Angebot nicht gefunden")
    lot = await session.get(Lot, quote.lot_id)
    if lot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Los nicht gefunden")
    access = await _require_access(session, user, lot.object_id, minimum)
    return quote, lot, access


# ---- List / create per lot --------------------------------------------------


@router_lots.get("", response_model=list[QuoteRead])
async def list_lot_quotes(
    lot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[QuoteRead]:
    """List quotes for a lot. Caller MUST hold >=VIEWER on the parent object."""
    await _lot_and_access(session, user, lot_id, ObjectRole.VIEWER)
    quotes = await list_quotes(session, lot_id=lot_id)
    return [_to_read(q) for q in quotes]


@router_lots.post(
    "",
    response_model=QuoteRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_lot_quote(
    request: Request,
    lot_id: uuid.UUID,
    payload: QuoteCreate,
    user: CurrentUser,
    session: SessionDep,
) -> QuoteRead:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    try:
        quote = await create_quote(session, lot_id=lot_id, actor=user, payload=payload)
    except QuoteServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_QUOTE_CREATE,
        object_id=lot.object_id,
        target_type="quote",
        target_id=quote.id,
        summary=f"Angebot für Los '{lot.name}' erfasst",
        payload={"amount_chf": str(quote.amount_chf), "supplier_id": str(quote.supplier_id)},
        request=request,
    )
    await session.commit()
    return _to_read(quote)


# ---- Award ------------------------------------------------------------------


@router_lots.post(
    "/{quote_id}/award",
    response_model=QuoteRead,
    dependencies=[Depends(require_csrf)],
)
async def award_quote_route(
    request: Request,
    lot_id: uuid.UUID,
    quote_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> QuoteRead:
    """Award ``quote_id`` on ``lot_id`` — atomic. Idempotent."""
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    try:
        lot, quote = await award_quote(
            session, lot_id=lot_id, quote_id=quote_id, actor=user
        )
    except QuoteServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_QUOTE_AWARD,
        object_id=lot.object_id,
        target_type="quote",
        target_id=quote.id,
        summary=f"Angebot für Los '{lot.name}' vergeben",
        payload={"lot_id": str(lot.id), "amount_chf": str(quote.amount_chf)},
        request=request,
    )
    await session.commit()
    return _to_read(quote)


# ---- Per-quote get / patch / delete ----------------------------------------


@router_quotes.get("/{quote_id}", response_model=QuoteRead)
async def get_quote_route(
    quote_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> QuoteRead:
    quote, _, _ = await _quote_and_access(
        session, user, quote_id, ObjectRole.VIEWER
    )
    return _to_read(quote)


@router_quotes.patch(
    "/{quote_id}",
    response_model=QuoteRead,
    dependencies=[Depends(require_csrf)],
)
async def update_quote_route(
    request: Request,
    quote_id: uuid.UUID,
    payload: QuoteUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> QuoteRead:
    quote, lot, _ = await _quote_and_access(
        session, user, quote_id, ObjectRole.EDITOR
    )
    changed = sorted(payload.model_dump(exclude_unset=True).keys())
    try:
        quote = await update_quote(session, quote_id=quote_id, payload=payload)
    except QuoteServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_QUOTE_UPDATE,
        object_id=lot.object_id,
        target_type="quote",
        target_id=quote.id,
        summary=f"Angebot für Los '{lot.name}' aktualisiert",
        payload={"fields": changed} if changed else None,
        request=request,
    )
    await session.commit()
    return _to_read(quote)


@router_quotes.delete(
    "/{quote_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_quote_route(
    request: Request,
    quote_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    quote, lot, _ = await _quote_and_access(
        session, user, quote_id, ObjectRole.EDITOR
    )
    qid = quote.id
    try:
        await delete_quote(session, quote_id=quote_id)
    except QuoteServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_QUOTE_DELETE,
        object_id=lot.object_id,
        target_type="quote",
        target_id=qid,
        summary=f"Angebot für Los '{lot.name}' gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# Re-export :func:`get_quote` so tests can introspect ORM state easily.
__all__ = ["router_lots", "router_quotes", "get_quote"]
