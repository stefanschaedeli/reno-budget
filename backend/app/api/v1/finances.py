"""Cross-object finance roll-up (Phase 4).

Returns one row per object the current user belongs to, with totals pro-rated
to that user's scope on each object. No new RBAC primitive is introduced —
we resolve :class:`ObjectAccess` per object via the existing service.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.core.db import SessionDep
from app.core.deps import CurrentUser
from app.repositories.object import list_objects_for_user
from app.schemas.budget import FinanceOverviewItem, FinanceOverviewResponse
from app.services.budgets import compute_object_totals
from app.services.rbac import get_object_access

router = APIRouter(prefix="/finances", tags=["finances"])


@router.get("/overview", response_model=FinanceOverviewResponse)
async def get_overview(user: CurrentUser, session: SessionDep) -> FinanceOverviewResponse:
    """Per-object totals for every object the current user belongs to.

    Objects the user has no membership on are simply absent — there is no
    "404" path because the resource is the user's own portfolio. Each row's
    numbers respect the user's scope on that object (full numbers for OWNER /
    unscoped EDITOR/VIEWER, pro-rated otherwise).
    """
    objects = await list_objects_for_user(session, user.id)
    items: list[FinanceOverviewItem] = []
    for obj in objects:
        access = await get_object_access(session, user, obj.id)
        if access is None:
            # Defence in depth: list_objects_for_user only returns objects
            # the user is a member of, so this branch is unreachable in
            # normal operation. Skip silently rather than 500.
            continue
        planned_infl, actual, per_year = await compute_object_totals(
            session, obj, access=access
        )
        items.append(
            FinanceOverviewItem(
                object_id=obj.id,
                name=obj.name,
                role=access.role,
                total_planned_inflated_chf=planned_infl,
                total_actual_chf=actual,
                required_per_year_chf=per_year,
                scope_pro_rated=access.allowed_unit_ids is not None,
            )
        )
    return FinanceOverviewResponse(items=items)
