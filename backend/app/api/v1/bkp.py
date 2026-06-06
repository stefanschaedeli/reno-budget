"""HTTP routes for the eBKP-H code catalogue (Phase 3).

Security invariants
-------------------
* All endpoints require an authenticated user (no anonymous catalogue read).
* ``POST /bkp-codes`` requires superuser; caller MUST be ``is_superuser``.
* The catalogue is global — custom codes are visible to every tenant. This
  is acceptable for a self-hosted single-tenant deployment (the entire
  Reno-Budget instance belongs to one family). When/if we add multi-tenancy
  this endpoint will gain a tenant scope.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.db import SessionDep
from app.core.deps import CurrentUser, SuperuserDep, require_csrf
from app.schemas.cost import BkpCodeCreate, BkpCodeRead, BkpCodeTree
from app.services.bkp import (
    BkpCodeServiceError,
    DuplicateBkpCodeError,
    UnknownParentBkpCodeError,
    create_custom_code,
    get_catalogue_tree,
    get_flat_catalogue,
)

router = APIRouter(prefix="/bkp-codes", tags=["bkp-codes"])


@router.get("", response_model=list[BkpCodeRead])
async def list_codes(_user: CurrentUser, session: SessionDep) -> list[BkpCodeRead]:
    """Return every eBKP-H code as a flat, code-sorted list.

    Visible to every authenticated user; the catalogue contains no
    user-specific data (German labels, no monetary content).
    """
    return await get_flat_catalogue(session)


@router.get("/tree", response_model=list[BkpCodeTree])
async def list_codes_tree(_user: CurrentUser, session: SessionDep) -> list[BkpCodeTree]:
    """Return the catalogue as a nested forest (one tree per root code)."""
    return await get_catalogue_tree(session)


@router.post(
    "",
    response_model=BkpCodeRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def create_code(
    payload: BkpCodeCreate,
    _admin: SuperuserDep,
    session: SessionDep,
) -> BkpCodeRead:
    """Create a custom (non-seed) catalogue row. Superuser only.

    Side effects: writes one row to ``bkp_codes`` with ``is_seed = False``.
    Raises 409 on duplicate code, 400 on missing parent.
    """
    try:
        row = await create_custom_code(session, payload)
    except DuplicateBkpCodeError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except UnknownParentBkpCodeError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except BkpCodeServiceError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    await session.commit()
    return BkpCodeRead.model_validate(row)
