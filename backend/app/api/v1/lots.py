"""HTTP routes for Lots + Lot membership (Phase 11B).

Two routers exported:

* :data:`router_objects` — object-scoped list/create at
  ``/objects/{object_id}/lots`` (viewer for reads, editor for writes).
* :data:`router_lots` — per-lot get/patch/archive/delete + cost-item
  membership operations at ``/lots/{lot_id}``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.lot import Lot
from app.models.object import ObjectRole
from app.repositories.object import list_objects_for_user
from app.schemas.cost import CostItemRead
from app.schemas.lot import LotCreate, LotListItem, LotRead, LotUpdate
from app.services import audit as audit_svc
from app.services.lots import (
    LotMembershipScopeError,
    LotMembershipTargetMissingError,
    LotNotFoundError,
    LotServiceError,
    add_cost_item_to_lot,
    archive_lot,
    count_cost_items_per_lot,
    create_lot,
    delete_lot,
    get_lot,
    list_cost_item_ids_for_lot,
    list_cost_items_for_lot,
    list_lots,
    remove_cost_item_from_lot,
    update_lot,
)
from app.services.rbac import ObjectAccess
from app.services.rbac import require_object_access as _require_access

router_objects = APIRouter(prefix="/objects/{object_id}/lots", tags=["lots"])
router_lots = APIRouter(prefix="/lots", tags=["lots"])


def _to_read(
    lot: Lot,
    *,
    cost_item_count: int = 0,
    cost_item_ids: list[uuid.UUID] | None = None,
) -> LotRead:
    data = LotRead.model_validate(lot)
    return data.model_copy(update={"cost_item_count": cost_item_count, "cost_item_ids": cost_item_ids})


def _raise_for(exc: LotServiceError) -> None:
    if isinstance(exc, LotNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, LotMembershipScopeError | LotMembershipTargetMissingError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _lot_and_access(
    session: SessionDep,
    user: CurrentUser,
    lot_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Lot, ObjectAccess]:
    """Resolve a lot and the caller's access to its parent object."""
    lot = await session.get(Lot, lot_id)
    if lot is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Los nicht gefunden")
    access = await _require_access(session, user, lot.object_id, minimum)
    return lot, access


# ---- Object-scoped list / create -------------------------------------------


@router_objects.get("", response_model=list[LotRead])
async def list_object_lots(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
    include_archived: bool = False,
) -> list[LotRead]:
    """List lots of an object. Caller MUST hold >=VIEWER."""
    lots = await list_lots(session, object_id=object_id, include_archived=include_archived)
    counts = await count_cost_items_per_lot(session, lot_ids=[lot.id for lot in lots])
    return [_to_read(lot, cost_item_count=counts.get(lot.id, 0)) for lot in lots]


@router_objects.post(
    "",
    response_model=LotRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_object_lot(
    request: Request,
    object_id: uuid.UUID,
    payload: LotCreate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> LotRead:
    """Create a new lot under ``object_id``. Caller MUST hold >=EDITOR."""
    try:
        lot = await create_lot(session, object_id=object_id, actor=user, payload=payload)
    except LotServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_LOT_CREATE,
        object_id=object_id,
        target_type="lot",
        target_id=lot.id,
        summary=f"Los '{lot.name}' angelegt",
        request=request,
    )
    await session.commit()
    return _to_read(lot, cost_item_count=0)


# ---- Cross-object list ------------------------------------------------------


@router_lots.get("", response_model=list[LotListItem])
async def list_all_lots(
    user: CurrentUser,
    session: SessionDep,
) -> list[LotListItem]:
    """All non-archived lots across every object the user can access."""
    objects = await list_objects_for_user(session, user.id)
    items: list[LotListItem] = []
    for obj in objects:
        rows = await list_lots(session, object_id=obj.id, include_archived=False)
        for l in rows:
            items.append(
                LotListItem.model_validate(
                    {**LotRead.model_validate(l).model_dump(), "object_name": obj.name}
                )
            )
    return items


# ---- Per-lot get / patch / archive / delete --------------------------------


@router_lots.get("/{lot_id}", response_model=LotRead)
async def get_lot_route(
    lot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> LotRead:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.VIEWER)
    ids = await list_cost_item_ids_for_lot(session, lot_id=lot_id)
    return _to_read(lot, cost_item_count=len(ids), cost_item_ids=ids)


@router_lots.patch(
    "/{lot_id}",
    response_model=LotRead,
    dependencies=[Depends(require_csrf)],
)
async def update_lot_route(
    request: Request,
    lot_id: uuid.UUID,
    payload: LotUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> LotRead:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    changed = sorted(payload.model_dump(exclude_unset=True).keys())
    try:
        lot = await update_lot(session, lot_id=lot_id, payload=payload)
    except LotServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_LOT_UPDATE,
        object_id=lot.object_id,
        target_type="lot",
        target_id=lot.id,
        summary=f"Los '{lot.name}' aktualisiert",
        payload={"fields": changed} if changed else None,
        request=request,
    )
    await session.commit()
    ids = await list_cost_item_ids_for_lot(session, lot_id=lot_id)
    return _to_read(lot, cost_item_count=len(ids), cost_item_ids=ids)


@router_lots.post(
    "/{lot_id}/archive",
    response_model=LotRead,
    dependencies=[Depends(require_csrf)],
)
async def archive_lot_route(
    request: Request,
    lot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> LotRead:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    try:
        lot = await archive_lot(session, lot_id=lot_id)
    except LotServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_LOT_ARCHIVE,
        object_id=lot.object_id,
        target_type="lot",
        target_id=lot.id,
        summary=f"Los '{lot.name}' archiviert",
        request=request,
    )
    await session.commit()
    ids = await list_cost_item_ids_for_lot(session, lot_id=lot_id)
    return _to_read(lot, cost_item_count=len(ids), cost_item_ids=ids)


@router_lots.delete(
    "/{lot_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_lot_route(
    request: Request,
    lot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    object_id = lot.object_id
    name = lot.name
    try:
        await delete_lot(session, lot_id=lot_id)
    except LotServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_LOT_DELETE,
        object_id=object_id,
        target_type="lot",
        target_id=lot_id,
        summary=f"Los '{name}' gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Membership -------------------------------------------------------------


class LotMembershipCreate(BaseModel):
    """Payload for ``POST /lots/{lot_id}/cost-items``."""

    cost_item_id: uuid.UUID


class LotMembershipRead(BaseModel):
    """Outbound shape for a membership row."""

    lot_id: uuid.UUID
    cost_item_id: uuid.UUID


@router_lots.get(
    "/{lot_id}/cost-items",
    response_model=list[CostItemRead],
)
async def list_lot_cost_items_route(
    lot_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[CostItemRead]:
    """List cost items currently a member of ``lot_id``."""
    await _lot_and_access(session, user, lot_id, ObjectRole.VIEWER)
    items = await list_cost_items_for_lot(session, lot_id=lot_id)
    # We need allocations/bkp_allocations eagerly loaded for the response.
    # ``list_cost_items_for_lot`` returns the entities; access via the relationship
    # would lazy-load — refresh each row with attributes we need.
    out: list[CostItemRead] = []
    for item in items:
        await session.refresh(item, attribute_names=["allocations", "bkp_allocations"])
        out.append(CostItemRead.model_validate(item))
    return out


@router_lots.post(
    "/{lot_id}/cost-items",
    response_model=LotMembershipRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def add_cost_item_route(
    request: Request,
    lot_id: uuid.UUID,
    payload: LotMembershipCreate,
    user: CurrentUser,
    session: SessionDep,
) -> LotMembershipRead:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    try:
        link = await add_cost_item_to_lot(
            session, lot_id=lot_id, cost_item_id=payload.cost_item_id
        )
    except LotServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_LOT_ADD_ITEM,
        object_id=lot.object_id,
        target_type="lot",
        target_id=lot_id,
        summary=f"Kostenposition zu Los '{lot.name}' hinzugefügt",
        payload={"cost_item_id": str(payload.cost_item_id)},
        request=request,
    )
    await session.commit()
    return LotMembershipRead(lot_id=link.lot_id, cost_item_id=link.cost_item_id)


@router_lots.delete(
    "/{lot_id}/cost-items/{cost_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def remove_cost_item_route(
    request: Request,
    lot_id: uuid.UUID,
    cost_item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    lot, _ = await _lot_and_access(session, user, lot_id, ObjectRole.EDITOR)
    removed = await remove_cost_item_from_lot(
        session, lot_id=lot_id, cost_item_id=cost_item_id
    )
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Mitgliedschaft nicht gefunden")
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_LOT_REMOVE_ITEM,
        object_id=lot.object_id,
        target_type="lot",
        target_id=lot_id,
        summary=f"Kostenposition aus Los '{lot.name}' entfernt",
        payload={"cost_item_id": str(cost_item_id)},
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
