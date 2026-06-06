"""Object/Unit/Membership business logic.

Lives between the routers (HTTP-shaped) and the repository (SQL-shaped). It
owns:

* atomic creation of objects together with their initial unit set,
* enforcement of cross-row invariants (Wertquoten summing to 1000),
* membership mutations (with "must keep at least one OWNER" check),
* the Phase-2 extension of the invitation flow that binds an invitation to
  an object + role + optional unit scope.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.object import (
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
    UnitScope,
)
from app.models.user import Invitation
from app.repositories.object import (
    count_owner_memberships,
    get_membership,
    list_units,
    replace_unit_scopes,
)
from app.schemas.object import ObjectCreate, UnitCreate
from app.services.allocations import WertquoteError, validate_wertquoten_sum

# ---- Exceptions -------------------------------------------------------------


class ObjectServiceError(Exception):
    """Base class for object-domain business errors."""


class LastOwnerError(ObjectServiceError):
    """Refused to demote/remove the last OWNER of an object."""


class InvalidUnitScopeError(ObjectServiceError):
    """Provided unit IDs do not all belong to the target object."""


# ---- Object creation --------------------------------------------------------


async def create_object_with_units(
    session: AsyncSession,
    *,
    payload: ObjectCreate,
    owner_user_id: uuid.UUID,
) -> Object:
    """Create an :class:`Object`, its initial units, and an OWNER membership.

    Wertquote sum is re-checked here even though the schema validates it,
    because Pydantic validation is bypassable (e.g. when called from tests
    or future internal callers). Defence in depth is cheap.
    """
    try:
        validate_wertquoten_sum(u.wertquote_permille for u in payload.units)
    except WertquoteError as exc:
        raise ObjectServiceError(str(exc)) from exc

    obj = Object(
        name=payload.name.strip(),
        address=payload.address,
        year_built=payload.year_built,
        type=payload.type,
        planning_horizon_years=payload.planning_horizon_years,
        contribution_mode=payload.contribution_mode,
        inflation_rate_percent=payload.inflation_rate_percent,
        initial_reserve_chf=payload.initial_reserve_chf,
    )
    session.add(obj)
    await session.flush()  # need obj.id before adding units

    for u in payload.units:
        session.add(
            Unit(
                object_id=obj.id,
                label=u.label.strip(),
                wertquote_permille=u.wertquote_permille,
                area_m2=u.area_m2,
            )
        )

    session.add(
        ObjectMembership(
            user_id=owner_user_id,
            object_id=obj.id,
            role=ObjectRole.OWNER,
        )
    )

    await session.flush()
    return obj


# ---- Unit management --------------------------------------------------------


async def replace_units(
    session: AsyncSession,
    obj: Object,
    new_units: Sequence[UnitCreate],
) -> Sequence[Unit]:
    """Replace the unit set of an object atomically.

    This is the simplest correct way to keep Wertquoten consistent: validate
    the proposed totals up-front, then delete-and-recreate. We do NOT support
    partial unit edits while cost items reference units (Phase 3 will add a
    safer per-unit editor); for Phase 2 this is sufficient and explicit.
    """
    if obj.type == ObjectType.SFH and (
        len(new_units) != 1 or new_units[0].wertquote_permille != 1000
    ):
        raise ObjectServiceError("Einfamilienhaus muss genau eine Einheit mit 1000‰ enthalten")
    try:
        validate_wertquoten_sum(u.wertquote_permille for u in new_units)
    except WertquoteError as exc:
        raise ObjectServiceError(str(exc)) from exc

    from sqlalchemy import delete

    # CASCADE handles unit_scopes; cost-item allocations don't exist yet in Phase 2.
    await session.execute(delete(Unit).where(Unit.object_id == obj.id))

    for u in new_units:
        session.add(
            Unit(
                object_id=obj.id,
                label=u.label.strip(),
                wertquote_permille=u.wertquote_permille,
                area_m2=u.area_m2,
            )
        )
    await session.flush()
    return await list_units(session, obj.id)


# ---- Membership mutations ---------------------------------------------------


async def update_membership(
    session: AsyncSession,
    *,
    obj: Object,
    membership: ObjectMembership,
    new_role: ObjectRole | None,
    new_scope_unit_ids: list[uuid.UUID] | None,
) -> ObjectMembership:
    """Change role and/or unit scope of a membership.

    Guards:
    * Cannot demote the last OWNER (would orphan the object).
    * Cannot scope an OWNER membership (scope rows are ignored for OWNERs).
    * Provided unit IDs must belong to ``obj``.
    """
    if new_role is not None and new_role != membership.role:
        if membership.role == ObjectRole.OWNER and new_role != ObjectRole.OWNER:
            remaining = await count_owner_memberships(session, obj.id)
            if remaining <= 1:
                raise LastOwnerError("Letzter Eigentümer kann nicht herabgestuft werden")
        membership.role = new_role

    if new_scope_unit_ids is not None:
        if membership.role == ObjectRole.OWNER and new_scope_unit_ids:
            raise ObjectServiceError("OWNER-Mitgliedschaft darf nicht unit-eingeschränkt sein")
        await _verify_units_belong_to_object(session, obj.id, new_scope_unit_ids)
        await replace_unit_scopes(session, membership, new_scope_unit_ids)

    return membership


async def remove_membership(
    session: AsyncSession, *, obj: Object, membership: ObjectMembership
) -> None:
    """Delete a membership; refuses to remove the last OWNER."""
    if membership.role == ObjectRole.OWNER:
        remaining = await count_owner_memberships(session, obj.id)
        if remaining <= 1:
            raise LastOwnerError("Letzter Eigentümer kann nicht entfernt werden")
    await session.delete(membership)


async def _verify_units_belong_to_object(
    session: AsyncSession, object_id: uuid.UUID, unit_ids: Sequence[uuid.UUID]
) -> None:
    if not unit_ids:
        return
    units = await list_units(session, object_id)
    valid = {u.id for u in units}
    bad = [str(u) for u in unit_ids if u not in valid]
    if bad:
        raise InvalidUnitScopeError(f"Einheiten gehören nicht zu diesem Objekt: {', '.join(bad)}")


# ---- Invitation extension (object-bound invites) ----------------------------


def encode_scope_unit_ids(unit_ids: Sequence[uuid.UUID]) -> str | None:
    """Serialise a unit-scope set for storage on an :class:`Invitation`."""
    if not unit_ids:
        return None
    return json.dumps([str(u) for u in unit_ids])


def decode_scope_unit_ids(raw: str | None) -> list[uuid.UUID]:
    """Inverse of :func:`encode_scope_unit_ids`; returns ``[]`` for ``None``."""
    if not raw:
        return []
    return [uuid.UUID(s) for s in json.loads(raw)]


async def apply_invitation_membership(
    session: AsyncSession, *, invitation: Invitation, user_id: uuid.UUID
) -> ObjectMembership | None:
    """Create the membership implied by an object-bound invitation, if any.

    Called from the auth-layer ``accept_invitation`` flow *after* the
    :class:`User` row is inserted. Returns ``None`` for admin-only
    invitations (``object_id is None``).
    """
    if invitation.object_id is None or invitation.role is None:
        return None

    # Idempotency: an existing membership wins; we don't downgrade or duplicate.
    existing = await get_membership(session, user_id, invitation.object_id)
    if existing is not None:
        return existing

    role = ObjectRole(invitation.role)
    membership = ObjectMembership(
        user_id=user_id,
        object_id=invitation.object_id,
        role=role,
    )
    session.add(membership)
    await session.flush()

    scope_ids = decode_scope_unit_ids(invitation.scope_unit_ids)
    if scope_ids and role != ObjectRole.OWNER:
        # Silently drop unit IDs that no longer exist (a unit could have been
        # deleted between invite issuance and acceptance). The remaining set
        # is still the inviter's intent.
        valid_units = await list_units(session, invitation.object_id)
        valid_ids = {u.id for u in valid_units}
        for uid in scope_ids:
            if uid in valid_ids:
                session.add(UnitScope(membership_id=membership.id, unit_id=uid))
        await session.flush()

    return membership
