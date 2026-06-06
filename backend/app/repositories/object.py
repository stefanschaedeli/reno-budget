"""Data-access helpers for objects, units, memberships and scopes.

As with :mod:`app.repositories.user`, these functions never commit; the
service / router layer owns transactional boundaries.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.object import Object, ObjectMembership, ObjectRole, Unit, UnitScope

# ---- Objects ----------------------------------------------------------------


async def get_object(session: AsyncSession, object_id: uuid.UUID) -> Object | None:
    return await session.get(Object, object_id)


async def list_objects_for_user(session: AsyncSession, user_id: uuid.UUID) -> Sequence[Object]:
    """All objects on which ``user_id`` holds any membership, sorted by name."""
    stmt = (
        select(Object)
        .join(ObjectMembership, ObjectMembership.object_id == Object.id)
        .where(ObjectMembership.user_id == user_id)
        .order_by(Object.name)
    )
    return (await session.execute(stmt)).scalars().all()


# ---- Units -----------------------------------------------------------------


async def list_units(session: AsyncSession, object_id: uuid.UUID) -> Sequence[Unit]:
    stmt = select(Unit).where(Unit.object_id == object_id).order_by(Unit.label)
    return (await session.execute(stmt)).scalars().all()


async def get_unit(session: AsyncSession, unit_id: uuid.UUID) -> Unit | None:
    return await session.get(Unit, unit_id)


# ---- Memberships -----------------------------------------------------------


async def list_memberships(
    session: AsyncSession, object_id: uuid.UUID
) -> Sequence[ObjectMembership]:
    stmt = (
        select(ObjectMembership)
        .where(ObjectMembership.object_id == object_id)
        .options(selectinload(ObjectMembership.unit_scopes))
        .order_by(ObjectMembership.created_at)
    )
    return (await session.execute(stmt)).scalars().all()


async def get_membership(
    session: AsyncSession, user_id: uuid.UUID, object_id: uuid.UUID
) -> ObjectMembership | None:
    stmt = select(ObjectMembership).where(
        ObjectMembership.user_id == user_id,
        ObjectMembership.object_id == object_id,
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def count_owner_memberships(session: AsyncSession, object_id: uuid.UUID) -> int:
    """Used to prevent removing the last OWNER of an object."""
    stmt = select(ObjectMembership).where(
        ObjectMembership.object_id == object_id,
        ObjectMembership.role == ObjectRole.OWNER,
    )
    return len((await session.execute(stmt)).scalars().all())


async def replace_unit_scopes(
    session: AsyncSession,
    membership: ObjectMembership,
    unit_ids: Sequence[uuid.UUID],
) -> None:
    """Atomically replace the unit scopes for a membership.

    Empty ``unit_ids`` ⇒ removes all scope rows ⇒ membership becomes unscoped.
    Callers MUST verify each unit_id belongs to the membership's object.
    """
    from sqlalchemy import delete

    await session.execute(delete(UnitScope).where(UnitScope.membership_id == membership.id))
    for uid in unit_ids:
        session.add(UnitScope(membership_id=membership.id, unit_id=uid))
