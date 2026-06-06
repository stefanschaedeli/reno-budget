"""HTTP routes for Renofond projection + actual contributions (Phase 5).

Security
--------
* ``GET /projection`` and ``GET /contributions`` require >= VIEWER on the
  object (scoped members see pro-rated amounts via the service).
* ``POST`` / ``DELETE`` on ``/contributions`` require OWNER + CSRF — only
  the owner records actual deposits.
* Outsiders receive 404 via :func:`require_object_access_dep`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.object import ObjectRole
from app.schemas.renofond import (
    ContributionCreate,
    ContributionListResponse,
    ContributionRead,
    ProjectionResponse,
)
from app.services import audit as audit_svc
from app.services.rbac import ObjectAccess
from app.services.renofond import (
    compute_projection,
    create_contribution,
    delete_contribution,
    list_contributions,
)

router = APIRouter(
    prefix="/objects/{object_id}/renofond", tags=["renofond"]
)


@router.get("/projection", response_model=ProjectionResponse)
async def get_projection(
    object_id: uuid.UUID,
    access: Annotated[
        ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))
    ],
    session: SessionDep,
) -> ProjectionResponse:
    """Year-by-year reserve balance projection for ``object_id``.

    Returns ``rows`` (one per planning year), ``underfunding_years`` (digest
    of years with negative balance) and the headline figures (initial
    reserve, required per-year contribution). Scoped members get pro-rated
    numbers; ``scope_pro_rated`` is True in that case.
    """
    return await compute_projection(session, object_id, access=access)


@router.get("/contributions", response_model=ContributionListResponse)
async def list_contributions_endpoint(
    object_id: uuid.UUID,
    access: Annotated[
        ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))
    ],
    session: SessionDep,
) -> ContributionListResponse:
    """List recorded contributions for ``object_id`` (>= VIEWER)."""
    rows = await list_contributions(session, object_id)
    return ContributionListResponse(
        items=[ContributionRead.model_validate(r) for r in rows],
        my_role=access.role,
    )


@router.post(
    "/contributions",
    response_model=ContributionRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_contribution_endpoint(
    request: Request,
    object_id: uuid.UUID,
    payload: ContributionCreate,
    user: CurrentUser,
    _: Annotated[
        ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))
    ],
    session: SessionDep,
) -> ContributionRead:
    """Record an actual deposit. OWNER-only + CSRF."""
    row = await create_contribution(
        session,
        object_id,
        year=payload.year,
        amount_chf=payload.amount_chf,
        note=payload.note,
    )
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_RESERVE_CONTRIBUTION_CREATE,
        object_id=object_id,
        target_type="reserve_contribution",
        target_id=row.id,
        summary=f"Einzahlung {payload.year}: CHF {payload.amount_chf}",
        payload={"year": payload.year, "amount_chf": str(payload.amount_chf)},
        request=request,
    )
    await session.commit()
    await session.refresh(row)
    return ContributionRead.model_validate(row)


@router.delete(
    "/contributions/{contribution_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_contribution_endpoint(
    request: Request,
    object_id: uuid.UUID,
    contribution_id: uuid.UUID,
    user: CurrentUser,
    _: Annotated[
        ObjectAccess, Depends(require_object_access_dep(ObjectRole.OWNER))
    ],
    session: SessionDep,
) -> Response:
    """Delete a contribution. OWNER-only + CSRF."""
    removed = await delete_contribution(session, object_id, contribution_id)
    if not removed:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Einzahlung nicht gefunden",
        )
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_RESERVE_CONTRIBUTION_DELETE,
        object_id=object_id,
        target_type="reserve_contribution",
        target_id=contribution_id,
        summary="Einzahlung gelöscht",
        request=request,
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
