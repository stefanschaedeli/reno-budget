"""HTTP routes for cost items per object (Phase 3).

Security invariants
-------------------
* Every endpoint is gated by :func:`require_object_access_dep` which raises
  404 if the caller has no membership on ``object_id`` and 403 if the role
  is below the minimum. Read endpoints require VIEWER; write endpoints
  require EDITOR (OWNER inherits).
* Scoped EDITOR/VIEWER memberships filter listings to items intersecting
  ``allowed_unit_ids`` and reject mutations whose final allocation set has
  no overlap with that scope (enforced in :mod:`app.services.cost_items`).
* CSRF double-submit applies to every state-changing endpoint via
  :func:`require_csrf`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.object import ObjectRole
from app.schemas.cost import (
    CostItemCreate,
    CostItemFilter,
    CostItemRead,
    CostItemUpdate,
)
from app.services import audit as audit_svc
from app.services.cost_items import (
    CostItemNotFoundError,
    CostItemPermissionError,
    CostItemServiceError,
    InvalidAllocationError,
    ScopeViolationError,
    UnknownBkpCodeError,
    UnknownProjectError,
    create_cost_item,
    delete_cost_item,
    get_cost_item,
    list_cost_items_for_object,
    list_lot_ids_for_cost_items,
    list_tag_ids_for_cost_items,
    update_cost_item,
)
from app.services.rbac import ObjectAccess

router = APIRouter(prefix="/objects/{object_id}/cost-items", tags=["cost-items"])


# ---- Helpers ---------------------------------------------------------------


def _to_read(item: object) -> CostItemRead:
    """Materialise the response DTO from an ORM cost item with allocations."""
    return CostItemRead.model_validate(item)


def _raise_for(exc: CostItemServiceError) -> None:
    """Translate service exceptions to HTTP statuses with German messages."""
    if isinstance(exc, CostItemNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, CostItemPermissionError | ScopeViolationError):
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(exc))
    if isinstance(exc, UnknownBkpCodeError | InvalidAllocationError | UnknownProjectError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


# ---- Endpoints --------------------------------------------------------------


@router.get("", response_model=list[CostItemRead])
async def list_items(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
    filters: Annotated[CostItemFilter, Query()],
) -> list[CostItemRead]:
    """List cost items of ``object_id`` visible to the caller.

    Caller MUST hold >=VIEWER for ``object_id``. Scoped memberships see only
    items whose allocations touch their allowed units.

    When ``include_tag_ids=true`` is passed, each returned item carries the
    ``tag_ids`` field populated from a single batched ``TagAssignment`` query
    — this keeps the cost-items list page from N+1-ing per-row tag fetches.
    """
    items = await list_cost_items_for_object(
        session, object_id=object_id, access=access, filters=filters
    )
    if not filters.include_tag_ids and not filters.include_lot_ids:
        return [_to_read(i) for i in items]
    ids = [i.id for i in items]
    tag_map = (
        await list_tag_ids_for_cost_items(session, ids) if filters.include_tag_ids else {}
    )
    lot_map = (
        await list_lot_ids_for_cost_items(session, ids) if filters.include_lot_ids else {}
    )
    result: list[CostItemRead] = []
    for i in items:
        read = _to_read(i)
        patch: dict[str, list[uuid.UUID]] = {}
        if filters.include_tag_ids:
            patch["tag_ids"] = tag_map.get(i.id, [])
        if filters.include_lot_ids:
            patch["lot_ids"] = lot_map.get(i.id, [])
        # Pydantic v2: model_copy(update=...) preserves the rest of the dump.
        result.append(read.model_copy(update=patch))
    return result


@router.post(
    "",
    response_model=CostItemRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_item(
    request: Request,
    object_id: uuid.UUID,
    payload: CostItemCreate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> CostItemRead:
    """Create a new cost item under ``object_id``.

    Caller MUST hold >=EDITOR. For SHARED scope without explicit allocations,
    the per-unit split is derived from the object's Wertquoten. Returns 400
    on invalid allocations or unknown eBKP-H code.
    """
    try:
        item = await create_cost_item(
            session,
            object_id=object_id,
            access=access,
            actor=user,
            payload=payload,
        )
    except CostItemServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_COST_ITEM_CREATE,
        object_id=object_id,
        target_type="cost_item",
        target_id=item.id,
        summary=f"Kostenposition '{item.title}' erstellt",
        payload={"bkp_code": item.bkp_code},
        request=request,
    )
    await session.commit()
    return _to_read(item)


@router.get("/{item_id}", response_model=CostItemRead)
async def get_item(
    object_id: uuid.UUID,
    item_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> CostItemRead:
    """Fetch a single cost item. Caller MUST hold >=VIEWER and have scope on it."""
    try:
        item = await get_cost_item(
            session, object_id=object_id, cost_item_id=item_id, access=access
        )
    except CostItemServiceError as exc:
        _raise_for(exc)
    return _to_read(item)


@router.patch(
    "/{item_id}",
    response_model=CostItemRead,
    dependencies=[Depends(require_csrf)],
)
async def update_item(
    request: Request,
    object_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: CostItemUpdate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> CostItemRead:
    """Patch a cost item. Caller MUST hold >=EDITOR and have scope on it."""
    changed = sorted(payload.model_dump(exclude_unset=True).keys())
    try:
        item = await update_cost_item(
            session,
            object_id=object_id,
            cost_item_id=item_id,
            access=access,
            payload=payload,
        )
    except CostItemServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_COST_ITEM_UPDATE,
        object_id=object_id,
        target_type="cost_item",
        target_id=item.id,
        summary=f"Kostenposition '{item.title}' aktualisiert",
        payload={"fields": changed} if changed else None,
        request=request,
    )
    await session.commit()
    return _to_read(item)


@router.delete(
    "/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_item(
    request: Request,
    object_id: uuid.UUID,
    item_id: uuid.UUID,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> Response:
    """Delete a cost item. Caller MUST hold >=EDITOR and have scope on it."""
    # Capture the title before delete so the audit summary keeps sense.
    try:
        existing = await get_cost_item(
            session, object_id=object_id, cost_item_id=item_id, access=access
        )
    except CostItemServiceError as exc:
        _raise_for(exc)
    title = existing.title
    try:
        await delete_cost_item(session, object_id=object_id, cost_item_id=item_id, access=access)
    except CostItemServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_COST_ITEM_DELETE,
        object_id=object_id,
        target_type="cost_item",
        target_id=item_id,
        summary=f"Kostenposition '{title}' gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
