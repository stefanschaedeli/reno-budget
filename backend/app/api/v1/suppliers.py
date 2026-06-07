"""HTTP routes for Suppliers (Phase 11C).

Two routers:

* :data:`router_objects` — object-scoped list/create at
  ``/objects/{object_id}/suppliers`` (VIEWER for read, EDITOR for write).
* :data:`router_suppliers` — per-supplier get/patch/archive/delete at
  ``/suppliers/{supplier_id}``.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.object import ObjectRole
from app.models.supplier import Supplier
from app.schemas.supplier import SupplierCreate, SupplierRead, SupplierUpdate
from app.services import audit as audit_svc
from app.services.rbac import ObjectAccess
from app.services.rbac import require_object_access as _require_access
from app.services.suppliers import (
    SupplierInUseError,
    SupplierNotFoundError,
    SupplierServiceError,
    archive_supplier,
    create_supplier,
    delete_supplier,
    get_supplier,
    list_suppliers,
    update_supplier,
)

router_objects = APIRouter(
    prefix="/objects/{object_id}/suppliers", tags=["suppliers"]
)
router_suppliers = APIRouter(prefix="/suppliers", tags=["suppliers"])


def _to_read(s: Supplier) -> SupplierRead:
    return SupplierRead.model_validate(s)


def _raise_for(exc: SupplierServiceError) -> None:
    if isinstance(exc, SupplierNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, SupplierInUseError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _supplier_and_access(
    session: SessionDep,
    user: CurrentUser,
    supplier_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Supplier, ObjectAccess]:
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lieferant nicht gefunden")
    access = await _require_access(session, user, supplier.object_id, minimum)
    return supplier, access


# ---- Object-scoped list / create -------------------------------------------


@router_objects.get("", response_model=list[SupplierRead])
async def list_object_suppliers(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
    include_archived: bool = False,
) -> list[SupplierRead]:
    """List suppliers of an object. Caller MUST hold >=VIEWER."""
    del access
    suppliers = await list_suppliers(
        session, object_id=object_id, include_archived=include_archived
    )
    return [_to_read(s) for s in suppliers]


@router_objects.post(
    "",
    response_model=SupplierRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_object_supplier(
    request: Request,
    object_id: uuid.UUID,
    payload: SupplierCreate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> SupplierRead:
    """Create a new supplier under ``object_id``. Caller MUST hold >=EDITOR."""
    del access
    try:
        supplier = await create_supplier(
            session, object_id=object_id, actor=user, payload=payload
        )
    except SupplierServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_SUPPLIER_CREATE,
        object_id=object_id,
        target_type="supplier",
        target_id=supplier.id,
        summary=f"Lieferant '{supplier.name}' angelegt",
        request=request,
    )
    await session.commit()
    return _to_read(supplier)


# ---- Per-supplier get / patch / archive / delete ---------------------------


@router_suppliers.get("/{supplier_id}", response_model=SupplierRead)
async def get_supplier_route(
    supplier_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> SupplierRead:
    supplier, _ = await _supplier_and_access(
        session, user, supplier_id, ObjectRole.VIEWER
    )
    return _to_read(supplier)


@router_suppliers.patch(
    "/{supplier_id}",
    response_model=SupplierRead,
    dependencies=[Depends(require_csrf)],
)
async def update_supplier_route(
    request: Request,
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> SupplierRead:
    supplier, _ = await _supplier_and_access(
        session, user, supplier_id, ObjectRole.EDITOR
    )
    changed = sorted(payload.model_dump(exclude_unset=True).keys())
    try:
        supplier = await update_supplier(
            session, supplier_id=supplier_id, payload=payload
        )
    except SupplierServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_SUPPLIER_UPDATE,
        object_id=supplier.object_id,
        target_type="supplier",
        target_id=supplier.id,
        summary=f"Lieferant '{supplier.name}' aktualisiert",
        payload={"fields": changed} if changed else None,
        request=request,
    )
    await session.commit()
    return _to_read(supplier)


@router_suppliers.post(
    "/{supplier_id}/archive",
    response_model=SupplierRead,
    dependencies=[Depends(require_csrf)],
)
async def archive_supplier_route(
    request: Request,
    supplier_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> SupplierRead:
    supplier, _ = await _supplier_and_access(
        session, user, supplier_id, ObjectRole.EDITOR
    )
    try:
        supplier = await archive_supplier(session, supplier_id=supplier_id)
    except SupplierServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_SUPPLIER_ARCHIVE,
        object_id=supplier.object_id,
        target_type="supplier",
        target_id=supplier.id,
        summary=f"Lieferant '{supplier.name}' archiviert",
        request=request,
    )
    await session.commit()
    return _to_read(supplier)


@router_suppliers.delete(
    "/{supplier_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_supplier_route(
    request: Request,
    supplier_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    supplier, _ = await _supplier_and_access(
        session, user, supplier_id, ObjectRole.EDITOR
    )
    object_id = supplier.object_id
    name = supplier.name
    try:
        await delete_supplier(session, supplier_id=supplier_id)
    except SupplierServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_SUPPLIER_DELETE,
        object_id=object_id,
        target_type="supplier",
        target_id=supplier_id,
        summary=f"Lieferant '{name}' gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ``get_supplier`` is re-exported to share the same error helper in tests.
__all__ = ["router_objects", "router_suppliers", "get_supplier"]
