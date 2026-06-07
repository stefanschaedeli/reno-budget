"""Business logic for Projects (Phase 11A — API layer).

Pure CRUD around :class:`~app.models.project.Project` with archive
semantics. RBAC is enforced by the calling router (via
``require_object_access_dep``); this service trusts that the caller has
already proven the right to read/write the underlying object.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User
from app.schemas.project import ProjectCreate, ProjectUpdate


class ProjectServiceError(Exception):
    """Base class for project business errors."""


class ProjectNotFoundError(ProjectServiceError):
    """The project does not exist or belongs to another object."""


async def create_project(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    actor: User,
    payload: ProjectCreate,
) -> Project:
    """Create a new project under ``object_id`` owned by ``actor``."""
    project = Project(
        object_id=object_id,
        name=payload.name.strip(),
        description=payload.description,
        status=payload.status,
        planned_year=payload.planned_year,
        created_by=actor.id,
    )
    session.add(project)
    await session.flush()
    return project


async def list_projects(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    include_archived: bool = False,
) -> list[Project]:
    """List projects of an object. Archived rows are excluded by default."""
    stmt = select(Project).where(Project.object_id == object_id)
    if not include_archived:
        stmt = stmt.where(Project.archived_at.is_(None))
    stmt = stmt.order_by(Project.created_at)
    return list((await session.execute(stmt)).scalars().all())


async def get_project(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    """Fetch a single project. Raises :class:`ProjectNotFoundError` if missing."""
    project = await session.get(Project, project_id)
    if project is None or project.object_id != object_id:
        raise ProjectNotFoundError("Projekt nicht gefunden")
    return project


async def update_project(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: ProjectUpdate,
) -> Project:
    """Patch a project. Only the fields present in the payload are touched."""
    project = await get_project(session, object_id=object_id, project_id=project_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(project, field, value)
    await session.flush()
    return project


async def archive_project(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
) -> Project:
    """Soft-archive a project (sets ``archived_at`` to now). Idempotent."""
    project = await get_project(session, object_id=object_id, project_id=project_id)
    if project.archived_at is None:
        project.archived_at = datetime.now(tz=UTC)
        await session.flush()
    return project


async def delete_project(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Hard-delete a project. Cost items' ``project_id`` cascades to NULL via FK."""
    project = await get_project(session, object_id=object_id, project_id=project_id)
    await session.delete(project)
