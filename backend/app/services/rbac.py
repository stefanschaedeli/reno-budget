"""Per-object role + unit-scope resolution.

This module is the **single source of truth** for "what may user X do to
object Y, and on which units?". Every router that touches object-scoped data
MUST go through :func:`get_object_access` (typically via the
:func:`app.core.deps.require_object_access` dependency) — never query
``ObjectMembership`` directly from a route.

Security invariants
-------------------
* A user with no :class:`ObjectMembership` for an object has **no access**,
  regardless of ``is_superuser``. Superusers receive elevated *admin* APIs
  (user management, eBKP-H catalog) but do not silently inherit object data
  access; this prevents accidental data exposure.
* OWNER role grants full access to all units of the object and ignores any
  :class:`UnitScope` rows that may exist.
* For EDITOR / VIEWER, an empty :class:`UnitScope` set means **unscoped**
  (all units). A non-empty set restricts visibility to those units. This is
  intentional: deleting all scope rows == "open it up to all units".
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.object import ObjectMembership, ObjectRole, UnitScope
from app.models.user import User

# Strict ordering so we can implement `role >= required`. Higher = more power.
_ROLE_RANK: dict[ObjectRole, int] = {
    ObjectRole.VIEWER: 1,
    ObjectRole.EDITOR: 2,
    ObjectRole.OWNER: 3,
}


@dataclass(frozen=True, slots=True)
class ObjectAccess:
    """Resolved access for a (user, object) pair.

    ``allowed_unit_ids`` is ``None`` when the user is unscoped (sees every
    unit). An empty *set* would mean "explicitly no units" — we never emit
    that; absence of scope rows is represented as ``None``.
    """

    membership_id: uuid.UUID
    role: ObjectRole
    allowed_unit_ids: frozenset[uuid.UUID] | None

    def has_role(self, minimum: ObjectRole) -> bool:
        """Return True iff the resolved role is at least ``minimum``."""
        return _ROLE_RANK[self.role] >= _ROLE_RANK[minimum]

    def can_see_unit(self, unit_id: uuid.UUID) -> bool:
        """Return True iff the user may see/modify the given unit of this object."""
        if self.allowed_unit_ids is None:
            return True
        return unit_id in self.allowed_unit_ids


async def get_object_access(
    session: AsyncSession, user: User, object_id: uuid.UUID
) -> ObjectAccess | None:
    """Resolve the role and unit-scope of ``user`` on ``object_id``.

    Returns ``None`` if the user has no membership on that object. Callers
    must translate ``None`` into HTTP 403/404 themselves (we deliberately
    don't raise here so this function stays usable from non-HTTP contexts —
    e.g. the worker that sends reminder digests).
    """
    membership = (
        await session.execute(
            select(ObjectMembership).where(
                ObjectMembership.user_id == user.id,
                ObjectMembership.object_id == object_id,
            )
        )
    ).scalar_one_or_none()

    if membership is None:
        return None

    # OWNER always sees every unit, even if stale scope rows happen to exist.
    if membership.role == ObjectRole.OWNER:
        return ObjectAccess(
            membership_id=membership.id,
            role=membership.role,
            allowed_unit_ids=None,
        )

    scope_rows = (
        (
            await session.execute(
                select(UnitScope.unit_id).where(UnitScope.membership_id == membership.id)
            )
        )
        .scalars()
        .all()
    )

    allowed: frozenset[uuid.UUID] | None = frozenset(scope_rows) if scope_rows else None
    return ObjectAccess(
        membership_id=membership.id,
        role=membership.role,
        allowed_unit_ids=allowed,
    )


async def require_object_access(
    session: AsyncSession,
    user: User,
    object_id: uuid.UUID,
    minimum_role: ObjectRole,
) -> ObjectAccess:
    """Resolve access and raise HTTP 403 if absent or insufficient.

    Returns ``404`` rather than ``403`` when the user has no membership at
    all — this is the conventional behaviour to avoid leaking the existence
    of objects the user has no business knowing about.
    """
    access = await get_object_access(session, user, object_id)
    if access is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Objekt nicht gefunden")
    if not access.has_role(minimum_role):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Berechtigung für diese Aktion fehlt",
        )
    return access
