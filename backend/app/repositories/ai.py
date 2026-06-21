"""Data-access helpers for AI assistant sessions and artifacts.

Pure SQL layer — no validation, no RBAC, no commits. RBAC scoping and the
draft → accept lifecycle live in the service layer.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ai import AiArtifact, AiSession, AiStep


async def get_session(
    session: AsyncSession, ai_session_id: uuid.UUID
) -> AiSession | None:
    stmt = (
        select(AiSession)
        .where(AiSession.id == ai_session_id)
        .options(selectinload(AiSession.artifacts))
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_active_session_for_project(
    session: AsyncSession, project_id: uuid.UUID
) -> AiSession | None:
    """Most recent session for a project, with artifacts eagerly loaded."""
    stmt = (
        select(AiSession)
        .where(AiSession.project_id == project_id)
        .options(selectinload(AiSession.artifacts))
        .order_by(AiSession.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


def add_session(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by: uuid.UUID | None,
) -> AiSession:
    """Create and stage a new session (caller flushes/commits)."""
    ai_session = AiSession(
        object_id=object_id,
        project_id=project_id,
        created_by=created_by,
    )
    session.add(ai_session)
    return ai_session


async def get_latest_artifact(
    session: AsyncSession, ai_session_id: uuid.UUID, step: AiStep
) -> AiArtifact | None:
    """The newest artifact for a given (session, step)."""
    stmt = (
        select(AiArtifact)
        .where(
            AiArtifact.session_id == ai_session_id,
            AiArtifact.step == step,
        )
        .order_by(AiArtifact.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalar_one_or_none()


async def get_artifact(
    session: AsyncSession, artifact_id: uuid.UUID
) -> AiArtifact | None:
    stmt = select(AiArtifact).where(AiArtifact.id == artifact_id)
    return (await session.execute(stmt)).scalar_one_or_none()


def add_artifact(
    session: AsyncSession,
    *,
    ai_session_id: uuid.UUID,
    step: AiStep,
    output: dict,
    validation: dict,
) -> AiArtifact:
    """Create and stage a new draft artifact (caller flushes/commits)."""
    artifact = AiArtifact(
        session_id=ai_session_id,
        step=step,
        output=output,
        validation=validation,
    )
    session.add(artifact)
    return artifact


async def list_artifacts(
    session: AsyncSession, ai_session_id: uuid.UUID
) -> Sequence[AiArtifact]:
    stmt = (
        select(AiArtifact)
        .where(AiArtifact.session_id == ai_session_id)
        .order_by(AiArtifact.created_at)
    )
    return (await session.execute(stmt)).scalars().all()
