"""HTTP routes for the object / unit / membership domain (Phase 2).

Every state-changing endpoint requires the appropriate per-object role via
:func:`app.core.deps.require_object_access_dep`. The dependency is the
*only* place RBAC is enforced for these routes — no ad-hoc role checks.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.config import get_settings
from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.object import Object, ObjectMembership, ObjectRole, Unit
from app.repositories.object import (
    get_membership,
    get_object,
    list_memberships,
    list_objects_for_user,
    list_units,
)
from app.schemas.auth import InviteResponse
from app.schemas.object import (
    InviteToObjectRequest,
    MembershipPublic,
    MembershipUpdate,
    ObjectCreate,
    ObjectDetail,
    ObjectPublic,
    ObjectUpdate,
    UnitCreate,
    UnitPublic,
)
from app.services import audit as audit_svc
from app.services import auth as auth_svc
from app.services.mailer import render_invitation, send_email
from app.services.objects import (
    InvalidUnitScopeError,
    LastOwnerError,
    ObjectServiceError,
    create_object_with_units,
    encode_scope_unit_ids,
    remove_membership,
    replace_units,
    update_membership,
)
from app.services.rbac import ObjectAccess

router = APIRouter(prefix="/objects", tags=["objects"])


# ---- Helpers ----------------------------------------------------------------


def _membership_to_public(m: ObjectMembership, scope_ids: list[uuid.UUID]) -> MembershipPublic:
    return MembershipPublic(
        id=m.id,
        user_id=m.user_id,
        object_id=m.object_id,
        role=m.role,
        scope_unit_ids=scope_ids,
    )


def _to_detail(obj: Object, units: Sequence[Unit]) -> ObjectDetail:
    return ObjectDetail(
        id=obj.id,
        name=obj.name,
        address=obj.address,
        year_built=obj.year_built,
        type=obj.type,
        planning_horizon_years=obj.planning_horizon_years,
        contribution_mode=obj.contribution_mode,
        inflation_rate_percent=obj.inflation_rate_percent,
        initial_reserve_chf=obj.initial_reserve_chf,
        created_at=obj.created_at,
        units=[UnitPublic.model_validate(u) for u in units],
    )


# ---- Object CRUD ------------------------------------------------------------


@router.get("", response_model=list[ObjectPublic])
async def list_my_objects(user: CurrentUser, session: SessionDep) -> list[ObjectPublic]:
    """Objects the current user has any membership on."""
    objs = await list_objects_for_user(session, user.id)
    return [ObjectPublic.model_validate(o) for o in objs]


@router.post(
    "",
    response_model=ObjectDetail,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_object(
    request: Request,
    payload: ObjectCreate,
    user: CurrentUser,
    session: SessionDep,
) -> ObjectDetail:
    """Create a new object and become its OWNER."""
    try:
        obj = await create_object_with_units(session, payload=payload, owner_user_id=user.id)
    except ObjectServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_OBJECT_CREATE,
        object_id=obj.id,
        target_type="object",
        target_id=obj.id,
        summary=f"Objekt '{obj.name}' angelegt",
        request=request,
    )
    await session.commit()
    units = await list_units(session, obj.id)
    return _to_detail(obj, units)


@router.get("/{object_id}", response_model=ObjectDetail)
async def get_object_detail(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> ObjectDetail:
    obj = await get_object(session, object_id)
    assert obj is not None  # require_object_access_dep would have 404'd
    units = await list_units(session, object_id)
    return _to_detail(obj, units)


@router.patch(
    "/{object_id}",
    response_model=ObjectDetail,
    dependencies=[Depends(require_csrf)],
)
async def update_object(
    request: Request,
    object_id: uuid.UUID,
    payload: ObjectUpdate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    session: SessionDep,
) -> ObjectDetail:
    obj = await get_object(session, object_id)
    assert obj is not None
    changed = payload.model_dump(exclude_unset=True)
    for field, value in changed.items():
        setattr(obj, field, value)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_OBJECT_UPDATE,
        object_id=obj.id,
        target_type="object",
        target_id=obj.id,
        summary=f"Objekt '{obj.name}' aktualisiert",
        payload={"fields": sorted(changed.keys())} if changed else None,
        request=request,
    )
    await session.commit()
    units = await list_units(session, object_id)
    return _to_detail(obj, units)


@router.delete(
    "/{object_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_object(
    request: Request,
    object_id: uuid.UUID,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    session: SessionDep,
) -> Response:
    obj = await get_object(session, object_id)
    assert obj is not None
    name = obj.name
    # Record the event BEFORE the delete so we can still reference the
    # object name. Because audit_events.object_id is ON DELETE SET NULL,
    # the row survives the cascade — only the link goes to NULL.
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_OBJECT_DELETE,
        object_id=obj.id,
        target_type="object",
        target_id=obj.id,
        summary=f"Objekt '{name}' gelöscht",
        request=request,
    )
    await session.delete(obj)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Units ------------------------------------------------------------------


@router.get("/{object_id}/units", response_model=list[UnitPublic])
async def list_object_units(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> list[UnitPublic]:
    units = await list_units(session, object_id)
    # Scoped viewers/editors only see their own units (OWNER sees all).
    if access.allowed_unit_ids is not None:
        units = [u for u in units if u.id in access.allowed_unit_ids]
    return [UnitPublic.model_validate(u) for u in units]


@router.put(
    "/{object_id}/units",
    response_model=list[UnitPublic],
    dependencies=[Depends(require_csrf)],
)
async def replace_object_units(
    request: Request,
    object_id: uuid.UUID,
    payload: list[UnitCreate],
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    session: SessionDep,
) -> list[UnitPublic]:
    """Replace the unit set of an object (OWNER only).

    Submitted Wertquoten MUST sum to 1000‰. Operation is atomic; on validation
    failure no changes are persisted.
    """
    obj = await get_object(session, object_id)
    assert obj is not None
    try:
        units = await replace_units(session, obj, payload)
    except ObjectServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_OBJECT_UNITS_REPLACE,
        object_id=obj.id,
        target_type="unit",
        summary=f"Einheiten von '{obj.name}' ersetzt ({len(units)})",
        payload={"count": len(units)},
        request=request,
    )
    await session.commit()
    return [UnitPublic.model_validate(u) for u in units]


# ---- Memberships ------------------------------------------------------------


@router.get("/{object_id}/members", response_model=list[MembershipPublic])
async def list_object_members(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> list[MembershipPublic]:
    members = await list_memberships(session, object_id)
    return [_membership_to_public(m, [s.unit_id for s in m.unit_scopes]) for m in members]


@router.patch(
    "/{object_id}/members/{user_id}",
    response_model=MembershipPublic,
    dependencies=[Depends(require_csrf)],
)
async def update_object_member(
    request: Request,
    object_id: uuid.UUID,
    user_id: uuid.UUID,
    payload: MembershipUpdate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    session: SessionDep,
) -> MembershipPublic:
    obj = await get_object(session, object_id)
    assert obj is not None
    membership = await get_membership(session, user_id, object_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mitgliedschaft nicht gefunden")
    try:
        await update_membership(
            session,
            obj=obj,
            membership=membership,
            new_role=payload.role,
            new_scope_unit_ids=payload.scope_unit_ids,
        )
    except LastOwnerError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except InvalidUnitScopeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except ObjectServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_MEMBERSHIP_UPDATE,
        object_id=obj.id,
        target_type="membership",
        target_id=membership.id,
        summary=f"Mitgliedschaft aktualisiert (Rolle={membership.role.value})",
        payload={
            "user_id": str(user_id),
            "role": membership.role.value,
        },
        request=request,
    )
    await session.commit()
    # Reload scopes for response.
    refreshed = await get_membership(session, user_id, object_id)
    assert refreshed is not None
    scope_ids = [s.unit_id for s in refreshed.unit_scopes]
    return _membership_to_public(refreshed, scope_ids)


@router.delete(
    "/{object_id}/members/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def remove_object_member(
    request: Request,
    object_id: uuid.UUID,
    user_id: uuid.UUID,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    session: SessionDep,
) -> Response:
    obj = await get_object(session, object_id)
    assert obj is not None
    membership = await get_membership(session, user_id, object_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mitgliedschaft nicht gefunden")
    try:
        await remove_membership(session, obj=obj, membership=membership)
    except LastOwnerError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_MEMBERSHIP_REVOKE,
        object_id=obj.id,
        target_type="membership",
        target_id=membership.id,
        summary=f"Mitgliedschaft entfernt für Benutzer {user_id}",
        payload={"user_id": str(user_id)},
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Object-bound invitations -----------------------------------------------


@router.post(
    "/{object_id}/invitations",
    response_model=InviteResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def invite_to_object(
    request: Request,
    object_id: uuid.UUID,
    payload: InviteToObjectRequest,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))],
    user: CurrentUser,
    session: SessionDep,
) -> InviteResponse:
    """OWNER invites an e-mail address to join this object with a chosen role."""
    obj = await get_object(session, object_id)
    assert obj is not None

    # Validate scope unit IDs against this object (defence in depth — the
    # schema only enforces "not for OWNER", not actual membership of units).
    if payload.scope_unit_ids:
        valid_units = {u.id for u in await list_units(session, object_id)}
        bad = [uid for uid in payload.scope_unit_ids if uid not in valid_units]
        if bad:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"Einheiten gehören nicht zu diesem Objekt: {bad}",
            )

    try:
        invitation, plaintext = await auth_svc.issue_invitation(
            session,
            payload.email,
            invited_by=user.id,
            object_id=object_id,
            role=payload.role.value,
            scope_unit_ids_encoded=encode_scope_unit_ids(payload.scope_unit_ids),
        )
    except auth_svc.InvitationConflictError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc

    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_MEMBERSHIP_GRANT,
        object_id=obj.id,
        target_type="invitation",
        target_id=invitation.id,
        summary=f"Einladung an {payload.email} mit Rolle {payload.role.value}",
        payload={
            "email": payload.email,
            "role": payload.role.value,
        },
        request=request,
    )
    await session.commit()

    settings = get_settings()
    subject, body = render_invitation(plaintext, app_base_url="https://reno.local")
    await send_email(invitation.email, subject, body)

    return InviteResponse(
        id=invitation.id,
        email=invitation.email,
        expires_at=invitation.expires_at,
        token=plaintext if settings.environment != "production" else None,
    )
