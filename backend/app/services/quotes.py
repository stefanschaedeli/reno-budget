"""Business logic for Quotes + Award transaction (Phase 11C — API layer).

A :class:`~app.models.quote.Quote` is a supplier offer attached to a
:class:`~app.models.lot.Lot`. The :func:`award_quote` operation is the
heart of this module: it atomically marks one quote as awarded, points
the lot at it and flips the lot status to ``awarded``. The DB-level
partial unique index ``uq_quotes_one_awarded_per_lot`` guarantees that
at most one quote per lot can ever sit in the awarded state, even under
concurrent requests.

RBAC is the caller's responsibility (route layer).
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lot import Lot, LotStatus
from app.models.quote import Quote, QuoteStatus
from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.quote import QuoteCreate, QuoteUpdate


class QuoteServiceError(Exception):
    """Base class for quote business errors."""


class QuoteNotFoundError(QuoteServiceError):
    """The quote does not exist or belongs to a different lot."""


class QuoteScopeError(QuoteServiceError):
    """Lot and supplier belong to different objects."""


class QuoteAwardConflictError(QuoteServiceError):
    """Another quote is already awarded for this lot."""


class QuoteDeleteForbiddenError(QuoteServiceError):
    """The quote is currently awarded on a non-cancelled lot — cannot delete."""


class QuoteStatusForbiddenError(QuoteServiceError):
    """The status transition is not allowed via the generic update endpoint."""


# ---- CRUD -------------------------------------------------------------------


async def create_quote(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
    actor: User,
    payload: QuoteCreate,
) -> Quote:
    """Create a quote on ``lot_id``.

    Validates that the chosen supplier belongs to the same Object as the
    lot. ``status`` defaults to ``received``; setting it to ``awarded``
    here is allowed only as the conventional path through
    :func:`award_quote`. Direct ``awarded`` on create is rejected to keep
    invariants explicit.
    """
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise QuoteNotFoundError("Los nicht gefunden")
    supplier = await session.get(Supplier, payload.supplier_id)
    if supplier is None:
        raise QuoteScopeError("Lieferant nicht gefunden")
    if supplier.object_id != lot.object_id:
        raise QuoteScopeError(
            "Lieferant und Los gehören zu unterschiedlichen Objekten"
        )
    if payload.status == QuoteStatus.AWARDED:
        raise QuoteStatusForbiddenError(
            "Vergabe muss über den dedizierten Endpoint erfolgen"
        )
    quote = Quote(
        lot_id=lot_id,
        supplier_id=payload.supplier_id,
        amount_chf=Decimal(payload.amount_chf),
        received_at=payload.received_at,
        valid_until=payload.valid_until,
        notes=payload.notes,
        status=payload.status,
        created_by=actor.id,
    )
    session.add(quote)
    await session.flush()
    return quote


async def list_quotes(
    session: AsyncSession, *, lot_id: uuid.UUID
) -> list[Quote]:
    """List quotes for a lot, ordered by received_at desc, then amount asc."""
    stmt = (
        select(Quote)
        .where(Quote.lot_id == lot_id)
        .order_by(Quote.received_at.desc(), Quote.amount_chf.asc())
    )
    return list((await session.execute(stmt)).scalars().all())


async def get_quote(
    session: AsyncSession, *, quote_id: uuid.UUID
) -> Quote:
    """Fetch a single quote. Raises if missing."""
    quote = await session.get(Quote, quote_id)
    if quote is None:
        raise QuoteNotFoundError("Angebot nicht gefunden")
    return quote


async def update_quote(
    session: AsyncSession,
    *,
    quote_id: uuid.UUID,
    payload: QuoteUpdate,
) -> Quote:
    """Patch a quote. Setting ``status='awarded'`` is forbidden here."""
    quote = await get_quote(session, quote_id=quote_id)
    changes = payload.model_dump(exclude_unset=True)
    if changes.get("status") == QuoteStatus.AWARDED and quote.status != QuoteStatus.AWARDED:
        raise QuoteStatusForbiddenError(
            "Vergabe muss über den dedizierten Endpoint erfolgen"
        )
    for field, value in changes.items():
        setattr(quote, field, value)
    await session.flush()
    return quote


async def delete_quote(
    session: AsyncSession, *, quote_id: uuid.UUID
) -> None:
    """Delete a quote. RESTRICTed if it is the awarded quote on a non-cancelled lot."""
    quote = await get_quote(session, quote_id=quote_id)
    if quote.status == QuoteStatus.AWARDED:
        lot = await session.get(Lot, quote.lot_id)
        if lot is not None and lot.awarded_quote_id == quote.id and lot.status != LotStatus.CANCELLED:
            raise QuoteDeleteForbiddenError(
                "Vergebenes Angebot kann nicht gelöscht werden — Los zuerst stornieren"
            )
    await session.delete(quote)
    await session.flush()


# ---- Award transaction ------------------------------------------------------


async def award_quote(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
    quote_id: uuid.UUID,
    actor: User,
) -> tuple[Lot, Quote]:
    """Award ``quote_id`` on ``lot_id``.

    Idempotent: re-awarding the already-awarded quote is a no-op (no DB
    change, but the caller still records an audit event). If another
    quote is currently awarded the DB partial unique index raises an
    IntegrityError which is mapped to :class:`QuoteAwardConflictError`
    for a clean 409 at the route layer.
    """
    del actor  # actor identity is logged by the route via audit_svc
    quote = await get_quote(session, quote_id=quote_id)
    if quote.lot_id != lot_id:
        raise QuoteNotFoundError("Angebot gehört nicht zu diesem Los")
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise QuoteNotFoundError("Los nicht gefunden")

    # Idempotent path: already awarded.
    if (
        quote.status == QuoteStatus.AWARDED
        and lot.awarded_quote_id == quote.id
        and lot.status == LotStatus.AWARDED
    ):
        return lot, quote

    # Pre-check: is another quote already awarded on this lot? We don't
    # rely solely on the partial unique index because asyncpg sometimes
    # defers constraint violation until commit, which would force the
    # route to handle the error too late (after audit log row written).
    existing_awarded = await session.execute(
        select(Quote).where(
            Quote.lot_id == lot_id,
            Quote.status == QuoteStatus.AWARDED,
            Quote.id != quote.id,
        )
    )
    if existing_awarded.scalars().first() is not None:
        raise QuoteAwardConflictError(
            "Für dieses Los ist bereits ein anderes Angebot vergeben"
        )

    quote.status = QuoteStatus.AWARDED
    lot.awarded_quote_id = quote.id
    lot.status = LotStatus.AWARDED
    try:
        await session.flush()
    except IntegrityError as exc:
        # Belt-and-braces: the partial unique index is the source of
        # truth for concurrent races; we map any leftover violation back
        # to a clean 409 for the route layer.
        await session.rollback()
        raise QuoteAwardConflictError(
            "Für dieses Los ist bereits ein anderes Angebot vergeben"
        ) from exc
    return lot, quote


__all__ = [
    "QuoteAwardConflictError",
    "QuoteDeleteForbiddenError",
    "QuoteNotFoundError",
    "QuoteScopeError",
    "QuoteServiceError",
    "QuoteStatusForbiddenError",
    "award_quote",
    "create_quote",
    "delete_quote",
    "get_quote",
    "list_quotes",
    "update_quote",
]
