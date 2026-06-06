"""Data-access helpers for cost items and their per-unit allocations.

Pure SQL layer — no validation, no RBAC, no commits. RBAC scoping is applied
in the service layer (which has the resolved :class:`ObjectAccess` in hand).
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cost import CostItem, CostItemUnitAllocation


async def get_cost_item(session: AsyncSession, cost_item_id: uuid.UUID) -> CostItem | None:
    stmt = (
        select(CostItem)
        .where(CostItem.id == cost_item_id)
        .options(selectinload(CostItem.allocations))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def list_cost_items(session: AsyncSession, object_id: uuid.UUID) -> Sequence[CostItem]:
    """All cost items of an object, with allocations eagerly loaded."""
    stmt = (
        select(CostItem)
        .where(CostItem.object_id == object_id)
        .options(selectinload(CostItem.allocations))
        .order_by(CostItem.created_at)
    )
    return (await session.execute(stmt)).scalars().all()


async def replace_allocations(
    session: AsyncSession,
    cost_item: CostItem,
    allocations: Iterable[tuple[uuid.UUID, int]],
) -> None:
    """Atomically replace the allocation rows of a cost item.

    Callers MUST have validated the sum-to-1000 invariant and that every
    ``unit_id`` belongs to the cost item's object. Empty iterable wipes the
    allocations (the service layer rejects this for cost items in practice).
    """
    await session.execute(
        delete(CostItemUnitAllocation).where(CostItemUnitAllocation.cost_item_id == cost_item.id)
    )
    for unit_id, share in allocations:
        session.add(
            CostItemUnitAllocation(
                cost_item_id=cost_item.id,
                unit_id=unit_id,
                share_permille=share,
            )
        )
