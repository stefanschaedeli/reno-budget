"""HTTP routes for the AI Project Assistant (project-scoped).

Mounted under ``/objects/{object_id}/projects/{project_id}/ai``. Every endpoint
requires >=EDITOR on the parent object (running a step or accepting a draft both
cost tokens / write data — VIEWERs are excluded). State-changing endpoints also
require CSRF. Accepting a draft is the only mutation of real data and is audited.

When no Anthropic API key is configured the AI endpoints that call the model
return 503 (the feature is simply disabled, not broken).
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf
from app.models.ai import AiArtifact, AiSession, AiStep
from app.models.object import ObjectRole
from app.models.project import Project
from app.repositories import ai as ai_repo
from app.schemas.ai import (
    AiArtifactRead,
    AiSessionRead,
    AnswersSubmit,
    RunStepRequest,
)
from app.services import audit as audit_svc
from app.services.ai import pipeline
from app.services.ai.client import AiClient, AiClientError, AiNotConfiguredError
from app.services.rbac import ObjectAccess
from app.services.rbac import require_object_access as _require_access

router = APIRouter(
    prefix="/objects/{object_id}/projects/{project_id}/ai", tags=["ai"]
)

_ACCEPT_ACTIONS = {
    AiStep.DESCRIBE: audit_svc.ACTION_AI_DESCRIPTION_ACCEPT,
    AiStep.ESTIMATE: audit_svc.ACTION_AI_ESTIMATE_ACCEPT,
    AiStep.BKP_SCOPE: audit_svc.ACTION_AI_BKP_ACCEPT,
}


async def _project_and_access(
    session: SessionDep,
    user: CurrentUser,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    minimum: ObjectRole,
) -> tuple[Project, ObjectAccess]:
    """Resolve the project and the caller's access, 404 on either miss."""
    project = await session.get(Project, project_id)
    if project is None or project.object_id != object_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Projekt nicht gefunden")
    access = await _require_access(session, user, object_id, minimum)
    return project, access


def get_ai_client() -> AiClient:
    """FastAPI dependency yielding a configured :class:`AiClient`.

    Overridable in tests via ``app.dependency_overrides``. Returns 503 when no
    Anthropic API key is configured so the feature degrades cleanly.
    """
    client = AiClient()
    if not client.configured:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "KI-Assistent ist nicht konfiguriert.",
        )
    return client


AiClientDep = Annotated[AiClient, Depends(get_ai_client)]


@router.get("/session", response_model=AiSessionRead)
async def get_session_route(
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> AiSession:
    """Return the project's AI session (most recent), creating one if needed."""
    await _project_and_access(session, user, object_id, project_id, ObjectRole.EDITOR)
    existing = await ai_repo.get_active_session_for_project(session, project_id)
    ai_session = pipeline.get_or_create_session(
        session,
        existing,
        object_id=object_id,
        project_id=project_id,
        created_by=user.id,
    )
    await session.commit()
    refreshed = await ai_repo.get_session(session, ai_session.id)
    assert refreshed is not None
    return refreshed


@router.post(
    "/answers",
    response_model=AiSessionRead,
    dependencies=[Depends(require_csrf)],
)
async def submit_answers_route(
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: AnswersSubmit,
    user: CurrentUser,
    session: SessionDep,
) -> AiSession:
    """Store typed answers gathered from the question step (reused on re-run)."""
    await _project_and_access(session, user, object_id, project_id, ObjectRole.EDITOR)
    ai_session = await _load_session(session, project_id)
    pipeline.store_answers(ai_session, payload.answers)
    await session.commit()
    refreshed = await ai_repo.get_session(session, ai_session.id)
    assert refreshed is not None
    return refreshed


@router.post(
    "/run",
    response_model=AiArtifactRead,
    dependencies=[Depends(require_csrf)],
)
async def run_step_route(
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    payload: RunStepRequest,
    user: CurrentUser,
    session: SessionDep,
    client: AiClientDep,
) -> AiArtifact:
    """Run (or re-run) one pipeline step and return its draft artifact."""
    project, _ = await _project_and_access(
        session, user, object_id, project_id, ObjectRole.EDITOR
    )
    ai_session = await _load_session(session, project_id)
    try:
        artifact = await pipeline.run_step(
            session,
            client,
            ai_session=ai_session,
            project=project,
            step=payload.step,
        )
    except AiNotConfiguredError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc
    except pipeline.StepPrerequisiteError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AiClientError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    await session.commit()
    return artifact


@router.post(
    "/artifacts/{artifact_id}/accept",
    response_model=AiArtifactRead,
    dependencies=[Depends(require_csrf)],
)
async def accept_artifact_route(
    request: Request,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> AiArtifact:
    """Apply a draft artifact to real data and mark it accepted."""
    project, access = await _project_and_access(
        session, user, object_id, project_id, ObjectRole.EDITOR
    )
    ai_session = await _load_session(session, project_id)
    artifact = await ai_repo.get_artifact(session, artifact_id)
    if artifact is None or artifact.session_id != ai_session.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Entwurf nicht gefunden")
    try:
        artifact = await pipeline.accept_artifact(
            session,
            artifact=artifact,
            ai_session=ai_session,
            project=project,
            access=access,
            actor=user,
        )
    except pipeline.ArtifactNotApplicableError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    action = _ACCEPT_ACTIONS.get(artifact.step)
    if action is not None:
        await audit_svc.record(
            session,
            actor=user,
            action=action,
            object_id=object_id,
            target_type="project",
            target_id=project.id,
            summary=f"KI-{artifact.step.value} für Projekt '{project.name}' übernommen",
            request=request,
        )
    await session.commit()
    return artifact


async def _load_session(session: SessionDep, project_id: uuid.UUID) -> AiSession:
    ai_session = await ai_repo.get_active_session_for_project(session, project_id)
    if ai_session is None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Keine KI-Sitzung vorhanden. Bitte zuerst die Sitzung starten.",
        )
    return ai_session
