"""HTTP routes for Projects (Phase 11A).

Two routers are exported from this module:

* :data:`router_objects` — object-scoped list/create (mounted under
  ``/objects/{object_id}/projects``); both endpoints require >=VIEWER for
  read / >=EDITOR for write on the parent object.
* :data:`router_projects` — per-project get / patch / archive / delete
  (mounted under ``/projects/{project_id}``). RBAC is resolved by looking
  up the project's parent object first and applying the standard object
  access dependency.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.object import ObjectRole
from app.models.project import Project
from app.repositories.object import list_objects_for_user
from app.schemas.project import ProjectCreate, ProjectListItem, ProjectRead, ProjectUpdate
from app.services import audit as audit_svc
from app.services.projects import (
    ProjectNotFoundError,
    ProjectServiceError,
    archive_project,
    create_project,
    delete_project,
    list_projects,
    update_project,
)
from app.services.rbac import ObjectAccess
from app.services.rbac import require_object_access as _require_access

router_objects = APIRouter(prefix="/objects/{object_id}/projects", tags=["projects"])
router_projects = APIRouter(prefix="/projects", tags=["projects"])


def _to_read(p: Project) -> ProjectRead:
    return ProjectRead.model_validate(p)


def _raise_for(exc: ProjectServiceError) -> None:
    if isinstance(exc, ProjectNotFoundError):
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


async def _project_and_access(
    session: SessionDep,
    user: CurrentUser,
    project_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Project, ObjectAccess]:
    """Resolve a project and the caller's access to its parent object.

    Returns 404 if the project is missing OR the user has no membership on
    the object (the object lookup raises 404 in that case as well).
    """
    project = await session.get(Project, project_id)
    if project is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden")
    access = await _require_access(session, user, project.object_id, minimum)
    return project, access


# ---- Object-scoped list / create -------------------------------------------


@router_objects.get("", response_model=list[ProjectRead])
async def list_object_projects(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
    include_archived: bool = False,
) -> list[ProjectRead]:
    """List projects of an object. Caller MUST hold >=VIEWER."""
    projects = await list_projects(session, object_id=object_id, include_archived=include_archived)
    return [_to_read(p) for p in projects]


@router_objects.post(
    "",
    response_model=ProjectRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_object_project(
    request: Request,
    object_id: uuid.UUID,
    payload: ProjectCreate,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
) -> ProjectRead:
    """Create a new project under ``object_id``. Caller MUST hold >=EDITOR."""
    try:
        project = await create_project(session, object_id=object_id, actor=user, payload=payload)
    except ProjectServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_PROJECT_CREATE,
        object_id=object_id,
        target_type="project",
        target_id=project.id,
        summary=f"Projekt '{project.name}' angelegt",
        request=request,
    )
    await session.commit()
    return _to_read(project)


# ---- Cross-object list ------------------------------------------------------


@router_projects.get("", response_model=list[ProjectListItem])
async def list_all_projects(
    user: CurrentUser,
    session: SessionDep,
) -> list[ProjectListItem]:
    """All non-archived projects across every object the user can access.

    Mirrors the ``/finances/overview`` pattern: enumerate the user's objects
    via ``list_objects_for_user`` (which joins through ``ObjectMembership``),
    then per object call the existing service. Archived rows are excluded.
    """
    objects = await list_objects_for_user(session, user.id)
    items: list[ProjectListItem] = []
    for obj in objects:
        rows = await list_projects(session, object_id=obj.id, include_archived=False)
        for p in rows:
            items.append(
                ProjectListItem.model_validate(
                    {**ProjectRead.model_validate(p).model_dump(), "object_name": obj.name}
                )
            )
    return items


# ---- Per-project get / patch / archive / delete ----------------------------


@router_projects.get("/{project_id}", response_model=ProjectRead)
async def get_project_route(
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> ProjectRead:
    project, _ = await _project_and_access(session, user, project_id, ObjectRole.VIEWER)
    return _to_read(project)


@router_projects.patch(
    "/{project_id}",
    response_model=ProjectRead,
    dependencies=[Depends(require_csrf)],
)
async def update_project_route(
    request: Request,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
    user: CurrentUser,
    session: SessionDep,
) -> ProjectRead:
    project, _ = await _project_and_access(session, user, project_id, ObjectRole.EDITOR)
    changed = sorted(payload.model_dump(exclude_unset=True).keys())
    try:
        project = await update_project(
            session, object_id=project.object_id, project_id=project_id, payload=payload
        )
    except ProjectServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_PROJECT_UPDATE,
        object_id=project.object_id,
        target_type="project",
        target_id=project.id,
        summary=f"Projekt '{project.name}' aktualisiert",
        payload={"fields": changed} if changed else None,
        request=request,
    )
    await session.commit()
    return _to_read(project)


@router_projects.post(
    "/{project_id}/archive",
    response_model=ProjectRead,
    dependencies=[Depends(require_csrf)],
)
async def archive_project_route(
    request: Request,
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> ProjectRead:
    project, _ = await _project_and_access(session, user, project_id, ObjectRole.EDITOR)
    try:
        project = await archive_project(session, object_id=project.object_id, project_id=project_id)
    except ProjectServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_PROJECT_ARCHIVE,
        object_id=project.object_id,
        target_type="project",
        target_id=project.id,
        summary=f"Projekt '{project.name}' archiviert",
        request=request,
    )
    await session.commit()
    return _to_read(project)


@router_projects.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_project_route(
    request: Request,
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    project, _ = await _project_and_access(session, user, project_id, ObjectRole.EDITOR)
    object_id = project.object_id
    name = project.name
    try:
        await delete_project(session, object_id=object_id, project_id=project_id)
    except ProjectServiceError as exc:
        _raise_for(exc)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_PROJECT_DELETE,
        object_id=object_id,
        target_type="project",
        target_id=project_id,
        summary=f"Projekt '{name}' gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
