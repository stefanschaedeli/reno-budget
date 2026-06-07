"""Business logic for Lots + Lot membership (Phase 11B — API layer).

A :class:`~app.models.lot.Lot` is a cross-project tender package scoped to
one Object. Cost-item membership is recorded in
:class:`~app.models.lot.LotCostItem` (whole-item, no share). The
:func:`add_cost_item_to_lot` operation enforces the cross-object invariant
that a Lot can only contain items from its own Object.

RBAC is the caller's responsibility (route layer); this module trusts the
session is already scoped to a user with the right role on the parent
object.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import CostItem
from app.models.lot import Lot, LotCostItem
from app.models.user import User
from app.schemas.lot import LotCreate, LotUpdate


class LotServiceError(Exception):
    """Base class for lot business errors."""


class LotNotFoundError(LotServiceError):
    """The lot does not exist or belongs to another object."""


class LotMembershipScopeError(LotServiceError):
    """The cost item and the lot do not share the same object."""


class LotMembershipTargetMissingError(LotServiceError):
    """The cost item referenced by the membership operation does not exist."""


# ---- CRUD -------------------------------------------------------------------


async def create_lot(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    actor: User,
    payload: LotCreate,
) -> Lot:
    """Create a new lot under ``object_id`` owned by ``actor``."""
    lot = Lot(
        object_id=object_id,
        name=payload.name.strip(),
        description=payload.description,
        status=payload.status,
        tender_deadline=payload.tender_deadline,
        created_by=actor.id,
    )
    session.add(lot)
    await session.flush()
    return lot


async def list_lots(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    include_archived: bool = False,
) -> list[Lot]:
    """List lots of an object. Archived rows are excluded by default."""
    stmt = select(Lot).where(Lot.object_id == object_id)
    if not include_archived:
        stmt = stmt.where(Lot.archived_at.is_(None))
    stmt = stmt.order_by(Lot.created_at)
    return list((await session.execute(stmt)).scalars().all())


async def get_lot(session: AsyncSession, *, lot_id: uuid.UUID) -> Lot:
    """Fetch a single lot. Raises :class:`LotNotFoundError` if missing."""
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise LotNotFoundError("Los nicht gefunden")
    return lot


async def update_lot(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
    payload: LotUpdate,
) -> Lot:
    """Patch a lot. Only fields present in ``payload`` are touched."""
    lot = await get_lot(session, lot_id=lot_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(lot, field, value)
    await session.flush()
    return lot


async def archive_lot(session: AsyncSession, *, lot_id: uuid.UUID) -> Lot:
    """Soft-archive a lot (sets ``archived_at`` to now). Idempotent."""
    lot = await get_lot(session, lot_id=lot_id)
    if lot.archived_at is None:
        lot.archived_at = datetime.now(tz=UTC)
        await session.flush()
    return lot


async def delete_lot(session: AsyncSession, *, lot_id: uuid.UUID) -> None:
    """Hard-delete a lot. Junction rows cascade via FK ON DELETE CASCADE."""
    lot = await get_lot(session, lot_id=lot_id)
    await session.delete(lot)


# ---- Membership -------------------------------------------------------------


async def add_cost_item_to_lot(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
    cost_item_id: uuid.UUID,
) -> LotCostItem:
    """Add a cost item to a lot. Same-object only. Idempotent."""
    lot = await get_lot(session, lot_id=lot_id)
    item = await session.get(CostItem, cost_item_id)
    if item is None:
        raise LotMembershipTargetMissingError(
            f"Kostenposition ({cost_item_id}) nicht gefunden"
        )
    if item.object_id != lot.object_id:
        raise LotMembershipScopeError(
            "Los und Kostenposition gehören zu unterschiedlichen Objekten"
        )
    existing = await session.get(LotCostItem, {"lot_id": lot_id, "cost_item_id": cost_item_id})
    if existing is not None:
        return existing
    link = LotCostItem(lot_id=lot_id, cost_item_id=cost_item_id)
    session.add(link)
    await session.flush()
    return link


async def remove_cost_item_from_lot(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
    cost_item_id: uuid.UUID,
) -> bool:
    """Remove a cost item from a lot. Returns ``True`` iff a row was deleted."""
    result = await session.execute(
        delete(LotCostItem).where(
            LotCostItem.lot_id == lot_id,
            LotCostItem.cost_item_id == cost_item_id,
        )
    )
    return (result.rowcount or 0) > 0


async def list_cost_items_for_lot(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
) -> list[CostItem]:
    """All cost items currently a member of ``lot_id``."""
    stmt = (
        select(CostItem)
        .join(LotCostItem, LotCostItem.cost_item_id == CostItem.id)
        .where(LotCostItem.lot_id == lot_id)
        .order_by(CostItem.title)
    )
    return list((await session.execute(stmt)).scalars().all())


async def list_lots_for_cost_item(
    session: AsyncSession,
    *,
    cost_item_id: uuid.UUID,
) -> list[Lot]:
    """All lots containing ``cost_item_id``."""
    stmt = (
        select(Lot)
        .join(LotCostItem, LotCostItem.lot_id == Lot.id)
        .where(LotCostItem.cost_item_id == cost_item_id)
        .order_by(Lot.name)
    )
    return list((await session.execute(stmt)).scalars().all())


async def count_cost_items_per_lot(
    session: AsyncSession,
    *,
    lot_ids: list[uuid.UUID],
) -> dict[uuid.UUID, int]:
    """Return ``{lot_id: count}`` for the given lots (single batched query)."""
    if not lot_ids:
        return {}
    stmt = (
        select(LotCostItem.lot_id, func.count(LotCostItem.cost_item_id))
        .where(LotCostItem.lot_id.in_(lot_ids))
        .group_by(LotCostItem.lot_id)
    )
    rows = (await session.execute(stmt)).all()
    return {lot_id: int(n) for lot_id, n in rows}


async def list_cost_item_ids_for_lot(
    session: AsyncSession,
    *,
    lot_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Return the cost-item ids currently linked to ``lot_id``."""
    stmt = select(LotCostItem.cost_item_id).where(LotCostItem.lot_id == lot_id)
    return list((await session.execute(stmt)).scalars().all())
