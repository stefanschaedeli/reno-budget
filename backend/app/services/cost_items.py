"""Business logic for cost items.

This module is the gatekeeper between cost-item HTTP handlers and the
database. It implements:

* RBAC over and above the ``require_object_access`` floor: VIEWER may only
  list; EDITOR/OWNER may create/update/delete.
* Per-unit scope enforcement: a scoped EDITOR/VIEWER sees an item only if at
  least one of its allocations intersects the membership's
  ``allowed_unit_ids``. Mutations require the new/updated allocation set to
  intersect the scope as well.
* Allocation auto-fill for SHARED-scope items: when the caller omits an
  allocation list, we materialise one row per object unit using the unit's
  Wertquote (= Swiss permille share). This is the natural default and what
  the UI does in the common case.
* Cross-row invariants: allocation rows MUST sum to 1000‰, all referenced
  units MUST belong to the cost item's object, and the eBKP-H code MUST
  exist in the catalogue.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cost import (
    CostItem,
    CostItemBkpAllocation,
    CostItemPriority,
    CostItemScope,
    CostItemUnitAllocation,
)
from app.models.object import ObjectRole, Unit
from app.models.tag import TagAssignment, TagTargetType
from app.models.user import User
from app.repositories.bkp import get_bkp_code
from app.repositories.cost_item import (
    get_cost_item as repo_get_cost_item,
)
from app.repositories.cost_item import (
    list_cost_items as repo_list_cost_items,
)
from app.repositories.cost_item import (
    replace_allocations,
)
from app.repositories.object import list_units
from app.schemas.cost import (
    BkpAllocationItem,
    CostItemAllocationIn,
    CostItemCreate,
    CostItemFilter,
    CostItemUpdate,
)
from app.services.allocations import (
    AllocationError,
    BkpAllocationError,
    validate_allocation_sum,
    validate_bkp_allocation_sum,
)
from app.services.rbac import ObjectAccess

# ---- Exceptions -------------------------------------------------------------


class CostItemServiceError(Exception):
    """Base class for cost-item business errors."""


class CostItemNotFoundError(CostItemServiceError):
    """The cost item does not exist or does not belong to this object."""


class CostItemPermissionError(CostItemServiceError):
    """Caller lacks the required role for the requested action."""


class InvalidAllocationError(CostItemServiceError):
    """Allocation set references units outside the object or sums wrong."""


class UnknownBkpCodeError(CostItemServiceError):
    """The provided ``bkp_code`` does not exist in the catalogue."""


class ScopeViolationError(CostItemServiceError):
    """A scoped editor tried to act on units outside their allowed set."""


class UnknownProjectError(CostItemServiceError):
    """The provided ``project_id`` does not exist or belongs to another object."""


# ---- Read paths -------------------------------------------------------------


async def list_cost_items_for_object(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    access: ObjectAccess,
    filters: CostItemFilter,
) -> list[CostItem]:
    """List cost items visible to ``access`` under the provided filters.

    Visibility rules:
    * OWNER (or any unscoped membership) sees every item of the object.
    * A scoped EDITOR/VIEWER sees an item iff at least one of the item's
      allocations targets a unit in ``allowed_unit_ids``. SHARED items thus
      remain visible to scoped users via their share of the object.
    """
    rows = await repo_list_cost_items(session, object_id)
    filtered = [_apply_filter(r, filters) for r in rows]
    items = [r for r in filtered if r is not None]
    if access.allowed_unit_ids is not None:
        scope = access.allowed_unit_ids
        items = [i for i in items if any(a.unit_id in scope for a in i.allocations)]
    if filters.unit_id is not None:
        target = filters.unit_id
        items = [i for i in items if any(a.unit_id == target for a in i.allocations)]
    if filters.tag_id:
        # any-of: keep items carrying at least one of the requested tags via
        # a TagAssignment row targeting the cost_item polymorphically.
        tagged_ids = await _cost_items_with_any_tag(session, filters.tag_id)
        items = [i for i in items if i.id in tagged_ids]
    return _sort_items(items, filters.sort)


async def list_tag_ids_for_cost_items(
    session: AsyncSession, cost_item_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    """Return a ``{cost_item_id: [tag_id, ...]}`` map for the given items.

    Single batched query — used by the list endpoint to avoid N+1 fetches
    when rendering tag chips per row. Items with no tags are not present
    in the map (callers should ``.get(id, [])``).
    """
    if not cost_item_ids:
        return {}
    stmt = select(TagAssignment.target_id, TagAssignment.tag_id).where(
        TagAssignment.target_type == TagTargetType.COST_ITEM,
        TagAssignment.target_id.in_(cost_item_ids),
    )
    rows = (await session.execute(stmt)).all()
    out: dict[uuid.UUID, list[uuid.UUID]] = {}
    for target_id, tag_id in rows:
        out.setdefault(target_id, []).append(tag_id)
    return out


async def _cost_items_with_any_tag(
    session: AsyncSession, tag_ids: list[uuid.UUID]
) -> set[uuid.UUID]:
    """Return the set of cost_item IDs assigned to any of ``tag_ids``."""
    stmt = select(TagAssignment.target_id).where(
        TagAssignment.target_type == TagTargetType.COST_ITEM,
        TagAssignment.tag_id.in_(tag_ids),
    )
    rows = (await session.execute(stmt)).scalars().all()
    return set(rows)


async def get_cost_item(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    cost_item_id: uuid.UUID,
    access: ObjectAccess,
) -> CostItem:
    """Fetch a single cost item, enforcing scope visibility.

    Raises :class:`CostItemNotFoundError` if the item is missing, belongs to
    a different object, or is invisible to a scoped membership.
    """
    item = await repo_get_cost_item(session, cost_item_id)
    if item is None or item.object_id != object_id:
        raise CostItemNotFoundError("Position nicht gefunden")
    if access.allowed_unit_ids is not None and not any(
        a.unit_id in access.allowed_unit_ids for a in item.allocations
    ):
        # Treat "out of scope" as 404 (not 403) to avoid leaking item existence.
        raise CostItemNotFoundError("Position nicht gefunden")
    return item


# ---- Write paths ------------------------------------------------------------


async def create_cost_item(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    access: ObjectAccess,
    actor: User,
    payload: CostItemCreate,
) -> CostItem:
    """Create a cost item under RBAC + invariants.

    Requires EDITOR or OWNER. For SHARED scope without explicit allocations,
    we materialise the per-unit split from the object's Wertquoten — this is
    the desired default and lets the UI submit a one-field "this cost is
    shared" form without re-stating Wertquoten on every line.
    """
    _require_editor(access)

    if payload.bkp_code is not None:
        bkp = await get_bkp_code(session, payload.bkp_code)
        if bkp is None:
            raise UnknownBkpCodeError(f"eBKP-H Code '{payload.bkp_code}' existiert nicht")

    bkp_allocs_in = await _resolve_bkp_allocations(session, payload.bkp_allocations)

    units = await list_units(session, object_id)
    allocations = await _resolve_allocations(
        units=units,
        scope=payload.scope,
        provided=payload.allocations,
    )
    _enforce_scope_on_allocations(access, allocations)

    if payload.project_id is not None:
        await _ensure_project_in_object(session, object_id, payload.project_id)

    item = CostItem(
        object_id=object_id,
        bkp_code=payload.bkp_code,
        project_id=payload.project_id,
        npk_code=payload.npk_code,
        title=payload.title.strip(),
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        planned_year=payload.planned_year,
        planned_amount_chf=payload.planned_amount_chf,
        actual_amount_chf=payload.actual_amount_chf,
        actual_date=payload.actual_date,
        lifespan_years=payload.lifespan_years,
        warranty_until=payload.warranty_until,
        scope=payload.scope,
        created_by=actor.id,
    )
    session.add(item)
    await session.flush()

    for a in allocations:
        session.add(
            CostItemUnitAllocation(
                cost_item_id=item.id,
                unit_id=a.unit_id,
                share_permille=a.share_permille,
            )
        )
    for ba in bkp_allocs_in:
        session.add(
            CostItemBkpAllocation(
                cost_item_id=item.id,
                bkp_code=ba.bkp_code,
                share_permille=ba.share_permille,
            )
        )
    await session.flush()
    # Reload with allocations for the response.
    return await _reload(session, item.id)


async def update_cost_item(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    cost_item_id: uuid.UUID,
    access: ObjectAccess,
    payload: CostItemUpdate,
) -> CostItem:
    """Patch a cost item. EDITOR/OWNER only; scope rules apply.

    A scoped editor may only edit items they can already see (at least one
    allocation in their scope) AND may not change the allocations to fully
    leave their scope (would orphan the item from their view).
    """
    _require_editor(access)
    item = await get_cost_item(
        session, object_id=object_id, cost_item_id=cost_item_id, access=access
    )

    update_dict = payload.model_dump(exclude_unset=True)
    new_allocations_in = update_dict.pop("allocations", None)
    new_bkp_allocations_in = update_dict.pop("bkp_allocations", None)

    if "bkp_code" in update_dict and update_dict["bkp_code"] is not None:
        bkp = await get_bkp_code(session, update_dict["bkp_code"])
        if bkp is None:
            raise UnknownBkpCodeError(f"eBKP-H Code '{update_dict['bkp_code']}' existiert nicht")

    if "project_id" in update_dict and update_dict["project_id"] is not None:
        await _ensure_project_in_object(session, object_id, update_dict["project_id"])

    # Validate + materialise the new BKP allocation set (replace-all semantics).
    bkp_allocs_in: list[BkpAllocationItem] | None = None
    if new_bkp_allocations_in is not None:
        as_models = [BkpAllocationItem(**a) for a in new_bkp_allocations_in]
        bkp_allocs_in = await _resolve_bkp_allocations(session, as_models)

    # Enforce XOR rule on the merged state (existing item + patch fields).
    # If the caller is switching to multi-BKP (non-empty list submitted) and
    # didn't explicitly clear bkp_code, we set it to NULL automatically — the
    # schema validator already rejected the case where both are explicit.
    if bkp_allocs_in is not None and bkp_allocs_in:
        if "bkp_code" not in update_dict:
            item.bkp_code = None
        elif update_dict["bkp_code"] is not None:
            raise InvalidAllocationError(
                "bkp_code und bkp_allocations dürfen nicht gleichzeitig gesetzt sein"
            )

    for field, value in update_dict.items():
        setattr(item, field, value)

    # Re-check "at least one amount" after merge.
    if item.planned_amount_chf is None and item.actual_amount_chf is None:
        raise InvalidAllocationError(
            "Mindestens ein Betrag (geplant oder effektiv) ist erforderlich"
        )

    if new_allocations_in is not None:
        units = await list_units(session, object_id)
        provided = [CostItemAllocationIn(**a) for a in new_allocations_in]
        allocations = await _resolve_allocations(
            units=units,
            scope=item.scope,
            provided=provided,
        )
        _enforce_scope_on_allocations(access, allocations)
        await replace_allocations(
            session,
            item,
            ((a.unit_id, a.share_permille) for a in allocations),
        )

    if bkp_allocs_in is not None:
        await _replace_bkp_allocations(session, item, bkp_allocs_in)

    await session.flush()
    return await _reload(session, item.id)


async def delete_cost_item(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    cost_item_id: uuid.UUID,
    access: ObjectAccess,
) -> None:
    """Delete a cost item. EDITOR/OWNER only; scope rules apply."""
    _require_editor(access)
    item = await get_cost_item(
        session, object_id=object_id, cost_item_id=cost_item_id, access=access
    )
    await session.delete(item)


# ---- Internals --------------------------------------------------------------


def _require_editor(access: ObjectAccess) -> None:
    """Raise :class:`CostItemPermissionError` for VIEWER-only members."""
    if not access.has_role(ObjectRole.EDITOR):
        raise CostItemPermissionError(
            "Berechtigung für diese Aktion fehlt (mindestens EDITOR erforderlich)"
        )


async def _resolve_allocations(
    *,
    units: Sequence[Unit],
    scope: CostItemScope,
    provided: list[CostItemAllocationIn] | None,
) -> list[CostItemAllocationIn]:
    """Materialise / validate the final allocation set for persistence.

    SHARED + no allocations → derive from object Wertquoten (one row per
    unit). All other cases use the provided list, after validating that
    every unit belongs to this object and the shares sum to 1000.
    """
    if provided is None:
        if scope == CostItemScope.UNIT:
            # Schema validator catches this; defence in depth here.
            raise InvalidAllocationError(
                "Einheit-spezifische Position erfordert explizite Aufteilung(en)"
            )
        if not units:
            raise InvalidAllocationError(
                "Objekt hat keine Einheiten — Auto-Aufteilung nicht möglich"
            )
        return [
            CostItemAllocationIn(unit_id=u.id, share_permille=u.wertquote_permille) for u in units
        ]

    valid_ids = {u.id for u in units}
    bad = [str(a.unit_id) for a in provided if a.unit_id not in valid_ids]
    if bad:
        raise InvalidAllocationError(f"Einheiten gehören nicht zu diesem Objekt: {', '.join(bad)}")
    try:
        validate_allocation_sum(a.share_permille for a in provided)
    except AllocationError as exc:
        raise InvalidAllocationError(str(exc)) from exc
    return list(provided)


async def _ensure_project_in_object(
    session: AsyncSession,
    object_id: uuid.UUID,
    project_id: uuid.UUID,
) -> None:
    """Validate that ``project_id`` exists and belongs to ``object_id``.

    Raises :class:`UnknownProjectError` (translated to 400 in the route).
    """
    from app.models.project import Project

    stmt = select(Project).where(Project.id == project_id)
    project = (await session.execute(stmt)).scalar_one_or_none()
    if project is None or project.object_id != object_id:
        raise UnknownProjectError("Projekt nicht gefunden in diesem Objekt")


async def _resolve_bkp_allocations(
    session: AsyncSession,
    provided: list[BkpAllocationItem] | None,
) -> list[BkpAllocationItem]:
    """Validate a multi-BKP allocation set and return it (possibly empty).

    ``None`` means "no list was submitted, keep the existing rows" — callers
    detect that case before calling us. An empty list is allowed and means
    "drop all multi-BKP shares" (the item then falls back to singleton
    ``bkp_code``, or stays uncategorised if that is also NULL).

    Validates: every ``bkp_code`` exists in the catalogue; the share sum is
    1000 (or empty); each share is in 0..1000. Raises
    :class:`UnknownBkpCodeError` / :class:`InvalidAllocationError`.
    """
    if provided is None or not provided:
        return []
    try:
        validate_bkp_allocation_sum(a.share_permille for a in provided)
    except BkpAllocationError as exc:
        raise InvalidAllocationError(str(exc)) from exc
    for a in provided:
        bkp = await get_bkp_code(session, a.bkp_code)
        if bkp is None:
            raise UnknownBkpCodeError(f"eBKP-H Code '{a.bkp_code}' existiert nicht")
    return list(provided)


async def _replace_bkp_allocations(
    session: AsyncSession,
    item: CostItem,
    new_rows: list[BkpAllocationItem],
) -> None:
    """Replace-all semantics for the per-item BKP allocation rows."""
    from sqlalchemy import delete as _delete

    await session.execute(
        _delete(CostItemBkpAllocation).where(CostItemBkpAllocation.cost_item_id == item.id)
    )
    for a in new_rows:
        session.add(
            CostItemBkpAllocation(
                cost_item_id=item.id,
                bkp_code=a.bkp_code,
                share_permille=a.share_permille,
            )
        )


def _enforce_scope_on_allocations(
    access: ObjectAccess, allocations: Sequence[CostItemAllocationIn]
) -> None:
    """Reject mutations whose allocations don't intersect the caller's scope.

    OWNER (always unscoped) bypasses this. Scoped EDITORs must keep at least
    one allocation row inside their permitted unit set; otherwise the
    resulting cost item would be invisible to them, which is almost
    certainly a mistake and never an authorised escalation path to "post
    invisibly into someone else's unit".
    """
    if access.allowed_unit_ids is None:
        return
    if not any(a.unit_id in access.allowed_unit_ids for a in allocations):
        raise ScopeViolationError(
            "Aufteilung muss mindestens eine Einheit im erlaubten Bereich enthalten"
        )


async def _reload(session: AsyncSession, cost_item_id: uuid.UUID) -> CostItem:
    """Re-fetch a cost item with allocations + BKP allocations eagerly loaded.

    Both ``selectinload`` clauses are required: the response schema reads
    ``bkp_allocations`` and async sessions raise on lazy-load attempts. We
    expire the cached entity first so freshly-inserted allocation rows on
    the collections show up (identity-map hit would otherwise keep the
    stale collection from the pre-mutation fetch).
    """
    existing = await session.get(CostItem, cost_item_id)
    if existing is not None:
        await session.refresh(existing, attribute_names=["allocations", "bkp_allocations"])
        return existing
    stmt = (
        select(CostItem)
        .where(CostItem.id == cost_item_id)
        .options(
            selectinload(CostItem.allocations),
            selectinload(CostItem.bkp_allocations),
        )
    )
    return (await session.execute(stmt)).scalar_one()


def _apply_filter(item: CostItem, filters: CostItemFilter) -> CostItem | None:
    """Return ``item`` iff it matches the simple scalar filters; else ``None``.

    Unit and scope filtering live in the caller because they depend on
    allocations / RBAC and are easier to express there.
    """
    if filters.status is not None and item.status != filters.status:
        return None
    if filters.priority is not None and item.priority != filters.priority:
        return None
    if filters.planned_year is not None and item.planned_year != filters.planned_year:
        return None
    if filters.bkp_code is not None:
        if item.bkp_code is None or not item.bkp_code.startswith(filters.bkp_code):
            return None
    if filters.project_id is not None and item.project_id != filters.project_id:
        return None
    if filters.q is not None:
        needle = filters.q.strip().lower()
        if needle and needle not in item.title.lower():
            return None
    return item


_SORT_KEYS: dict[str, Any] = {
    "created_at": lambda i: i.created_at,
    "title": lambda i: i.title.lower(),
    "planned_amount_chf": lambda i: i.planned_amount_chf or 0,
    "actual_amount_chf": lambda i: i.actual_amount_chf or 0,
    "planned_year": lambda i: i.planned_year or 0,
    "priority": lambda i: _PRIORITY_RANK.get(i.priority, 0),
    "status": lambda i: i.status.value,
}

_PRIORITY_RANK: dict[CostItemPriority, int] = {
    CostItemPriority.LOW: 0,
    CostItemPriority.MED: 1,
    CostItemPriority.HIGH: 2,
    CostItemPriority.URGENT: 3,
}


def _sort_items(items: list[CostItem], sort: str | None) -> list[CostItem]:
    """Apply ``?sort=field`` (prefix ``-`` for descending). Unknown → no-op."""
    if not sort:
        return items
    reverse = sort.startswith("-")
    key = sort[1:] if reverse else sort
    fn = _SORT_KEYS.get(key)
    if fn is None:
        return items
    return sorted(items, key=fn, reverse=reverse)
