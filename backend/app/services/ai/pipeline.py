"""Orchestration for the AI Project Assistant.

Ties the skills, validators, and critic together into a re-runnable pipeline and
persists state via :mod:`app.repositories.ai`. Two responsibilities:

* **run_step** — execute one pipeline step (classify / question / describe /
  estimate / bkp_scope), validate the output (L1+L2, plus the L3 critic on the
  cost and BKP steps), and store the result as a *draft* artifact. Re-running a
  step reuses the session's persisted answers, so the user is not re-asked.
* **accept_artifact** — apply a draft to real data (``Project`` fields or new
  ``CostItem`` rows) through the existing services, then mark it accepted.

RBAC and CSRF are enforced by the router; this service trusts the caller has
proven >=EDITOR on the parent object and receives the resolved
:class:`~app.services.rbac.ObjectAccess` for the cost-item writes.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai import (
    AiArtifact,
    AiArtifactStatus,
    AiSession,
    AiStep,
)
from app.models.project import Project
from app.models.user import User
from app.schemas.ai import (
    BkpScope,
    Estimate,
    QuestionSet,
    ValidationReport,
)
from app.schemas.cost import CostItemCreate
from app.schemas.project import ProjectUpdate
from app.services import bkp as bkp_svc
from app.services import projects as projects_svc
from app.services.ai import critic, validators
from app.services.ai.client import AiClient
from app.services.ai.skills import (
    bkp_scoper,
    classifier,
    describer,
    estimator,
    questioner,
)
from app.services.cost_items import create_cost_item
from app.services.rbac import ObjectAccess


class PipelineError(Exception):
    """Base class for pipeline business errors."""


class StepPrerequisiteError(PipelineError):
    """A step was run before a step it depends on (e.g. estimate before classify)."""


class ArtifactNotApplicableError(PipelineError):
    """Tried to accept an artifact whose step does not write real data, or which
    failed validation."""


# --------------------------------------------------------------------------
# Running steps
# --------------------------------------------------------------------------


async def run_step(
    session: AsyncSession,
    client: AiClient,
    *,
    ai_session: AiSession,
    project: Project,
    step: AiStep,
) -> AiArtifact:
    """Run one step and persist its draft artifact. Caller commits."""
    answers: dict[str, Any] = dict(ai_session.answers or {})

    if step is AiStep.CLASSIFY:
        result = await classifier.classify(
            client, name=project.name, description=project.description
        )
        ai_session.project_type = result.project_type
        report = ValidationReport(ok=True)
        output = result.model_dump(mode="json")

    elif step is AiStep.QUESTION:
        project_type = _require_type(ai_session)
        result_qs: QuestionSet = await questioner.generate_questions(
            client,
            project_type=project_type,
            name=project.name,
            description=project.description,
        )
        report = validators.validate_question_set(result_qs)
        output = result_qs.model_dump(mode="json")

    elif step is AiStep.DESCRIBE:
        draft = await describer.describe(
            client,
            name=project.name,
            current=project.description,
            answers=answers,
        )
        report = ValidationReport(ok=True)
        output = draft.model_dump(mode="json")

    elif step is AiStep.ESTIMATE:
        project_type = _require_type(ai_session)
        est: Estimate = await estimator.estimate(
            client,
            project_type=project_type,
            name=project.name,
            description=project.description,
            answers=answers,
        )
        report = validators.validate_estimate(
            est, area_m2=_area_from_answers(answers)
        )
        # L3 critic only when deterministic checks pass (don't critique garbage).
        if report.ok:
            findings = await critic.critique_estimate(client, est)
            report = critic.merge_findings(report, findings)
        output = est.model_dump(mode="json")

    elif step is AiStep.BKP_SCOPE:
        project_type = _require_type(ai_session)
        catalogue = await bkp_svc.get_flat_catalogue(session)
        known = {c.code for c in catalogue}
        scope: BkpScope = await bkp_scoper.scope_bkp(
            client,
            project_type=project_type,
            name=project.name,
            description=project.description,
            answers=answers,
            catalogue=[{"code": c.code, "label_de": c.label_de} for c in catalogue],
        )
        report = validators.validate_bkp_scope(scope, known_codes=known)
        if report.ok:
            findings = await critic.critique_bkp_scope(client, scope)
            report = critic.merge_findings(report, findings)
        output = scope.model_dump(mode="json")

    else:  # pragma: no cover - exhaustive
        raise PipelineError(f"Unknown step: {step}")

    from app.repositories import ai as ai_repo

    artifact = ai_repo.add_artifact(
        session,
        ai_session_id=ai_session.id,
        step=step,
        output=output,
        validation=report.model_dump(mode="json"),
    )
    await session.flush()
    return artifact


def store_answers(ai_session: AiSession, answers: dict[str, Any]) -> None:
    """Merge submitted answers into the session (reused on re-run)."""
    merged = dict(ai_session.answers or {})
    merged.update(answers)
    ai_session.answers = merged


# --------------------------------------------------------------------------
# Accepting drafts → real data
# --------------------------------------------------------------------------


async def accept_artifact(
    session: AsyncSession,
    *,
    artifact: AiArtifact,
    ai_session: AiSession,
    project: Project,
    access: ObjectAccess,
    actor: User,
) -> AiArtifact:
    """Apply a draft artifact to real data and mark it accepted. Caller commits."""
    report = ValidationReport.model_validate(artifact.validation or {"ok": True})
    if not report.ok:
        raise ArtifactNotApplicableError(
            "Entwurf hat Validierungsfehler und kann nicht übernommen werden."
        )

    if artifact.step is AiStep.DESCRIBE:
        description = artifact.output.get("description")
        await projects_svc.update_project(
            session,
            object_id=project.object_id,
            project_id=project.id,
            payload=ProjectUpdate(description=description),
        )

    elif artifact.step is AiStep.ESTIMATE:
        est = Estimate.model_validate(artifact.output)
        await projects_svc.update_project(
            session,
            object_id=project.object_id,
            project_id=project.id,
            payload=ProjectUpdate(rough_estimate_chf=est.total_chf),
        )

    elif artifact.step is AiStep.BKP_SCOPE:
        scope = BkpScope.model_validate(artifact.output)
        for pos in scope.positions:
            await create_cost_item(
                session,
                object_id=project.object_id,
                access=access,
                actor=actor,
                payload=CostItemCreate(
                    title=pos.title,
                    bkp_code=pos.bkp_code,
                    project_id=project.id,
                    planned_amount_chf=pos.estimated_amount_chf,
                    description=_scope_description(pos),
                ),
            )

    else:
        raise ArtifactNotApplicableError(
            f"Schritt '{artifact.step}' erzeugt keine übernehmbaren Daten."
        )

    artifact.status = AiArtifactStatus.ACCEPTED
    await session.flush()
    return artifact


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _require_type(ai_session: AiSession) -> str:
    if not ai_session.project_type:
        raise StepPrerequisiteError(
            "Bitte zuerst den Projekttyp bestimmen (classify)."
        )
    return ai_session.project_type


def _area_from_answers(answers: dict[str, Any]) -> float | None:
    """Best-effort extraction of an area in m² for the plausibility check."""
    for key in ("area_m2", "flaeche_m2", "area", "m2"):
        val = answers.get(key)
        if isinstance(val, (int, float)):
            return float(val)
    return None


def _scope_description(pos) -> str:
    """Render in/out-of-scope bullets into the cost item's description."""
    parts: list[str] = []
    if pos.in_scope:
        parts.append("Im Umfang:\n" + "\n".join(f"- {x}" for x in pos.in_scope))
    if pos.out_of_scope:
        parts.append("Nicht im Umfang:\n" + "\n".join(f"- {x}" for x in pos.out_of_scope))
    if pos.assumptions:
        parts.append(f"Annahmen: {pos.assumptions}")
    return "\n\n".join(parts) or None


def get_or_create_session(
    session: AsyncSession,
    existing: AiSession | None,
    *,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
    created_by: uuid.UUID | None,
) -> AiSession:
    """Return the existing active session or stage a new one."""
    if existing is not None:
        return existing
    from app.repositories import ai as ai_repo

    return ai_repo.add_session(
        session,
        object_id=object_id,
        project_id=project_id,
        created_by=created_by,
    )
