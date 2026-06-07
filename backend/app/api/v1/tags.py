"""HTTP routes for Tags + polymorphic TagAssignment (Phase 11A).

Routers exported from this module:

* :data:`router_objects` — object-scoped list / create of tags
  (``/objects/{object_id}/tags``). RBAC via the standard object access dep.
* :data:`router_tags` — per-tag update / delete / assignment management
  (``/tags/{tag_id}``). RBAC resolved by looking up the tag's parent object.
* :data:`router_target_tags` — read-only "tags on this target" listing
  (``/projects/{id}/tags``, ``/cost_items/{id}/tags``).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.cost import CostItem
from app.models.lot import Lot
from app.models.object import ObjectRole
from app.models.project import Project
from app.models.tag import Tag, TagTargetType
from app.schemas.tag import (
    TagAssignmentCreate,
    TagAssignmentRead,
    TagCreate,
    TagRead,
    TagUpdate,
)
from app.services import audit as audit_svc
from app.services.rbac import ObjectAccess
from app.services.rbac import require_object_access as _require_access
from app.services.tags import (
    TagAssignmentScopeError,
    TagAssignmentTargetMissingError,
    TagConflictError,
    TagNotFoundError,
    TagServiceError,
    assign_tag,
    create_tag,
    delete_tag,
    list_tags,
    list_tags_for_target,
    unassign_tag,
    update_tag,
)

router_objects = APIRouter(prefix="/objects/{object_id}/tags", tags=["tags"])
router_tags = APIRouter(prefix="/tags", tags=["tags"])
router_target_tags = APIRouter(prefix="", tags=["tags"])


def _to_read(t: Tag) -> TagRead:
    return TagRead.model_validate(t)


def _raise_for(exc: TagServiceError) -> None:
    if isinstance(exc, TagNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    if isinstance(exc, TagConflictError):
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc))
    if isinstance(exc, TagAssignmentScopeError | TagAssignmentTargetMissingError):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _tag_and_access(
    session: SessionDep,
    user: CurrentUser,
    tag_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Tag, ObjectAccess]:
    """Resolve a tag and the caller's access to its parent object."""
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag nicht gefunden")
    access = await _require_access(session, user, tag.object_id, minimum)
    return tag, access


# ---- Object-scoped list / create -------------------------------------------


@router_objects.get("", response_model=list[TagRead])
async def list_object_tags(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> list[TagRead]:
    tags = await list_tags(session, object_id=object_id)
    return [_to_read(t) for t in tags]


@router_objects.post(
    "",
    response_model=TagRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_object_tag(
    request: Request,
    object_id: uuid.UUID,
    payload: TagCreate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> TagRead:
    try:
        tag = await create_tag(session, object_id=object_id, payload=payload)
    except TagServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_TAG_CREATE,
        object_id=object_id,
        target_type="tag",
        target_id=tag.id,
        summary=f"Tag '{tag.key}={tag.value}' angelegt",
        request=request,
    )
    await session.commit()
    return _to_read(tag)


# ---- Per-tag update / delete + assignments ---------------------------------


@router_tags.patch(
    "/{tag_id}",
    response_model=TagRead,
    dependencies=[Depends(require_csrf)],
)
async def update_tag_route(
    request: Request,
    tag_id: uuid.UUID,
    payload: TagUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> TagRead:
    tag, _ = await _tag_and_access(session, user, tag_id, ObjectRole.EDITOR)
    try:
        tag = await update_tag(session, tag_id=tag_id, payload=payload)
    except TagServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_TAG_UPDATE,
        object_id=tag.object_id,
        target_type="tag",
        target_id=tag.id,
        summary=f"Tag '{tag.key}={tag.value}' aktualisiert",
        request=request,
    )
    await session.commit()
    return _to_read(tag)


@router_tags.delete(
    "/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_tag_route(
    request: Request,
    tag_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    tag, _ = await _tag_and_access(session, user, tag_id, ObjectRole.EDITOR)
    object_id = tag.object_id
    label = f"{tag.key}={tag.value}"
    try:
        await delete_tag(session, tag_id=tag_id)
    except TagServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_TAG_DELETE,
        object_id=object_id,
        target_type="tag",
        target_id=tag_id,
        summary=f"Tag '{label}' gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router_tags.post(
    "/{tag_id}/assignments",
    response_model=TagAssignmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def assign_tag_route(
    request: Request,
    tag_id: uuid.UUID,
    payload: TagAssignmentCreate,
    user: CurrentUser,
    session: SessionDep,
) -> TagAssignmentRead:
    tag, _ = await _tag_and_access(session, user, tag_id, ObjectRole.EDITOR)
    try:
        assignment = await assign_tag(
            session,
            tag_id=tag_id,
            target_type=payload.target_type,
            target_id=payload.target_id,
        )
    except TagServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_TAG_ASSIGN,
        object_id=tag.object_id,
        target_type=payload.target_type.value,
        target_id=payload.target_id,
        summary=f"Tag '{tag.key}={tag.value}' zugewiesen",
        payload={"tag_id": str(tag_id)},
        request=request,
    )
    await session.commit()
    return TagAssignmentRead.model_validate(assignment)


@router_tags.delete(
    "/{tag_id}/assignments/{target_type}/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def unassign_tag_route(
    request: Request,
    tag_id: uuid.UUID,
    target_type: TagTargetType,
    target_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    tag, _ = await _tag_and_access(session, user, tag_id, ObjectRole.EDITOR)
    removed = await unassign_tag(
        session, tag_id=tag_id, target_type=target_type, target_id=target_id
    )
    if not removed:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Zuweisung nicht gefunden")
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_TAG_UNASSIGN,
        object_id=tag.object_id,
        target_type=target_type.value,
        target_id=target_id,
        summary=f"Tag '{tag.key}={tag.value}' entfernt",
        payload={"tag_id": str(tag_id)},
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---- Per-target tag listing -------------------------------------------------

# Only ``project`` and ``cost_item`` are valid path values — declared as the
# Literal-shaped enum so an unknown value yields 422 before the handler runs.


@router_target_tags.get(
    "/{target_type}/{target_id}/tags",
    response_model=list[TagRead],
)
async def list_target_tags(
    target_type: Annotated[TagTargetType, Path()],
    target_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[TagRead]:
    """List tags attached to the given target.

    RBAC: look up the target's object and require >=VIEWER on it. Returns
    404 if the target is missing or the user lacks access.
    """
    if target_type == TagTargetType.PROJECT:
        project = await session.get(Project, target_id)
        if project is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden")
        object_id = project.object_id
    elif target_type == TagTargetType.COST_ITEM:
        item = await session.get(CostItem, target_id)
        if item is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Position nicht gefunden")
        object_id = item.object_id
    elif target_type == TagTargetType.LOT:
        lot = await session.get(Lot, target_id)
        if lot is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Los nicht gefunden")
        object_id = lot.object_id
    else:  # pragma: no cover — enum constraint above prevents this
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Zieltyp nicht erlaubt")

    await _require_access(session, user, object_id, ObjectRole.VIEWER)
    tags = await list_tags_for_target(session, target_type=target_type, target_id=target_id)
    return [_to_read(t) for t in tags]
