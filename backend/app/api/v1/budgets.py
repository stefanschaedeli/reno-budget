"""HTTP routes for the per-object budget timeline + reserve plan (Phase 4).

Read-only endpoints; both require VIEWER on the object. RBAC pro-rating for
scoped EDITOR/VIEWER is handled inside :mod:`app.services.budgets`.
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.db import SessionDep
from app.core.deps import require_object_access_dep
from app.models.object import ObjectRole
from app.schemas.budget import ReserveResponse, TimelineResponse
from app.services.budgets import compute_reserve_plan, compute_timeline
from app.services.rbac import ObjectAccess

router = APIRouter(prefix="/objects/{object_id}/budget", tags=["budget"])


@router.get("/timeline", response_model=TimelineResponse)
async def get_timeline(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
    inflated: Annotated[bool, Query()] = True,
) -> TimelineResponse:
    """Per-year planned / actual aggregates for ``object_id``.

    Caller MUST hold >=VIEWER. Scoped members see pro-rated numbers based on
    their UnitScope. ``inflated`` toggles whether future planned amounts are
    compounded by the object's inflation rate.
    """
    return await compute_timeline(session, object_id, access=access, inflated=inflated)


@router.get("/reserve", response_model=ReserveResponse)
async def get_reserve(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> ReserveResponse:
    """Required monthly / yearly / lump-sum reserve contributions."""
    return await compute_reserve_plan(session, object_id, access=access)
