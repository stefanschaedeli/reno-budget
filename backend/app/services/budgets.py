"""Yearly aggregation + reserve-planning math (Phase 4).

Two pure functions over the live DB:

* :func:`compute_timeline` — one row per year from
  ``min(planned_year, current_year)`` to ``current_year + horizon``, with
  planned/actual sums and breakdowns by BKP top group, unit, status, priority.
* :func:`compute_reserve_plan` — derives required contribution amounts from
  the timeline's future planned-inflated total minus any initial reserve.

Both functions respect :class:`ObjectAccess`. A scoped EDITOR/VIEWER sees
each cost item pro-rated by the sum of share_permille for units within their
scope. OWNER or unscoped EDITOR/VIEWER see full numbers.

Money is :class:`Decimal` throughout. Rounding is applied at the API
boundary only — internal sums keep full precision so breakdown buckets re-add
to the row totals exactly.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import CostItem, CostItemPriority, CostItemStatus
from app.models.object import Object
from app.repositories.cost_item import list_cost_items as repo_list_cost_items
from app.repositories.object import get_object, list_units
from app.schemas.budget import (
    ReserveLumpSum,
    ReserveResponse,
    TimelineBucket,
    TimelineResponse,
    TimelineRow,
)
from app.services.rbac import ObjectAccess

# Status values that count toward the *future* (i.e. still-to-do) plan.
_PLANNED_STATUSES: frozenset[CostItemStatus] = frozenset(
    {CostItemStatus.IDEA, CostItemStatus.PLANNED, CostItemStatus.IN_PROGRESS}
)

_CHF_QUANT = Decimal("0.01")
_HUNDRED = Decimal("100")
_THOUSAND = Decimal("1000")


def _q(value: Decimal) -> Decimal:
    """Round a CHF amount to 2 decimals, half-up (Swiss accounting convention)."""
    return value.quantize(_CHF_QUANT, rounding=ROUND_HALF_UP)


def _top_group(bkp_code: str) -> str:
    """Return the first character of an eBKP-H code (the Hauptgruppe key).

    The seed catalogue uses single-letter top-level groups (A, B, C, D, ...);
    this matches the eBKP-H standard. We deliberately key buckets by the raw
    character rather than fetching the label_de — the API caller can resolve
    labels from the catalogue endpoint if it wants to render them.
    """
    return bkp_code[:1].upper() if bkp_code else ""


def _scope_factor(item: CostItem, allowed: frozenset[uuid.UUID] | None) -> Decimal:
    """Pro-rating factor for ``item`` given the caller's unit scope.

    Returns ``Decimal('1')`` for unscoped callers. For scoped callers the
    factor is ``sum(share_permille for unit in allowed) / 1000`` — zero when
    no allocation intersects the scope (the item is effectively invisible).
    """
    if allowed is None:
        return Decimal("1")
    share = Decimal("0")
    for a in item.allocations:
        if a.unit_id in allowed:
            share += Decimal(a.share_permille)
    return share / _THOUSAND


def _inflation_factor(rate_percent: Decimal, years: int) -> Decimal:
    """Compound inflation: ``(1 + rate/100)^years``.

    For ``years <= 0`` we return 1 — past or current-year planned amounts are
    expressed in today's francs already, so we don't deflate them.
    """
    if years <= 0 or rate_percent == 0:
        return Decimal("1")
    base = Decimal("1") + rate_percent / _HUNDRED
    return base ** years


def _current_year() -> int:
    """Today's calendar year. Wrapped so tests can monkeypatch if needed."""
    return _dt.date.today().year


# ---- Public API -------------------------------------------------------------


async def compute_timeline(
    session: AsyncSession,
    object_id: uuid.UUID,
    *,
    access: ObjectAccess,
    inflated: bool,
) -> TimelineResponse:
    """Build the per-year planning timeline for ``object_id``.

    The row range spans ``min(planned_year, current_year) .. current_year +
    horizon``. Planned sums include IDEA/PLANNED/IN_PROGRESS items (everything
    still expected to spend money); COMPLETED/CANCELLED contribute only via
    their actuals (``actual_amount_chf`` bucketed by ``actual_date`` year).

    ``inflated=False`` returns ``planned_inflated_chf == planned_chf``.
    """
    obj = await get_object(session, object_id)
    assert obj is not None  # caller resolves 404 via require_object_access

    items = list(await repo_list_cost_items(session, object_id))
    rate = obj.inflation_rate_percent if inflated else Decimal("0")
    current_year = _current_year()
    horizon_end = current_year + obj.planning_horizon_years

    # Determine the first year we need to surface. If a user has stale planned
    # years in the past, we still want to show them so the totals balance.
    planned_years = [i.planned_year for i in items if i.planned_year is not None]
    actual_years = [
        i.actual_date.year for i in items if i.actual_date is not None
    ]
    earliest = min([current_year, *planned_years, *actual_years])

    row_accumulators: dict[int, _RowAcc] = {
        y: _RowAcc() for y in range(earliest, horizon_end + 1)
    }

    allowed = access.allowed_unit_ids
    for item in items:
        factor = _scope_factor(item, allowed)
        if factor == 0:
            continue

        if (
            item.planned_amount_chf is not None
            and item.planned_year is not None
            and item.status in _PLANNED_STATUSES
        ):
            year = item.planned_year
            if year not in row_accumulators:
                # Outside the requested window (shouldn't happen because we
                # widened ``earliest`` above) — skip to keep the row set tight.
                continue
            planned = item.planned_amount_chf * factor
            inflate_years = year - current_year
            planned_infl = planned * _inflation_factor(rate, inflate_years)

            acc = row_accumulators[year]
            acc.planned += planned
            acc.planned_inflated += planned_infl
            acc.add_breakdown_planned(item, factor, planned, allowed)

        if item.actual_amount_chf is not None and item.actual_date is not None:
            year = item.actual_date.year
            if year not in row_accumulators:
                continue
            actual = item.actual_amount_chf * factor
            acc = row_accumulators[year]
            acc.actual += actual
            acc.add_breakdown_actual(item, factor, actual, allowed)

    rows = [
        _materialise_row(year, acc)
        for year, acc in sorted(row_accumulators.items(), key=lambda kv: kv[0])
    ]

    return TimelineResponse(
        object_id=object_id,
        inflated=inflated,
        inflation_rate_percent=obj.inflation_rate_percent,
        current_year=current_year,
        horizon_until_year=horizon_end,
        scope_pro_rated=allowed is not None,
        rows=rows,
    )


async def compute_reserve_plan(
    session: AsyncSession,
    object_id: uuid.UUID,
    *,
    access: ObjectAccess,
) -> ReserveResponse:
    """Compute the required-contribution plan from the inflated timeline.

    ``required_total = max(0, sum_future_planned_inflated - initial_reserve)``
    divided by the planning horizon gives the per-year contribution; we also
    surface the per-month figure (yearly/12) and the inflated per-year planned
    list so the OWNER can opt for a lump-sum strategy.

    Initial reserve is pro-rated for scoped callers using the same factor we'd
    apply if the reserve were a SHARED cost item — i.e. it scales by the
    object's Wertquoten total for the scope. That way a 30 %-Wertquote viewer
    sees "your share" rather than the family's total.
    """
    obj = await get_object(session, object_id)
    assert obj is not None

    timeline = await compute_timeline(session, object_id, access=access, inflated=True)
    current_year = timeline.current_year

    future_total = Decimal("0")
    for r in timeline.rows:
        if r.year > current_year:
            future_total += r.planned_inflated_chf

    initial_reserve = obj.initial_reserve_chf * await _reserve_scope_factor(
        session, object_id, access
    )

    required_total = future_total - initial_reserve
    if required_total < 0:
        required_total = Decimal("0")
    horizon = obj.planning_horizon_years
    per_year = required_total / horizon if horizon else Decimal("0")
    per_month = per_year / Decimal("12")

    lump_sums = [
        ReserveLumpSum(year=r.year, amount_chf=_q(r.planned_inflated_chf))
        for r in timeline.rows
        if r.year > current_year and r.planned_inflated_chf > 0
    ]

    return ReserveResponse(
        object_id=object_id,
        contribution_mode=obj.contribution_mode,
        horizon_years=horizon,
        inflation_rate_percent=obj.inflation_rate_percent,
        initial_reserve_chf=_q(initial_reserve),
        total_planned_inflated_chf=_q(future_total),
        required_total_chf=_q(required_total),
        required_per_year_chf=_q(per_year),
        required_per_month_chf=_q(per_month),
        required_lump_sums=lump_sums,
        scope_pro_rated=access.allowed_unit_ids is not None,
    )


async def _reserve_scope_factor(
    session: AsyncSession, object_id: uuid.UUID, access: ObjectAccess
) -> Decimal:
    """Pro-rate the initial reserve by the share of object Wertquoten in scope."""
    if access.allowed_unit_ids is None:
        return Decimal("1")
    units = await list_units(session, object_id)
    in_scope = Decimal("0")
    for u in units:
        if u.id in access.allowed_unit_ids:
            in_scope += Decimal(u.wertquote_permille)
    return in_scope / _THOUSAND


# ---- Internal row accumulator -----------------------------------------------


class _RowAcc:
    """Mutable accumulator for one timeline year.

    Kept separate from the Pydantic DTO so the hot aggregation loop stays in
    plain Decimal arithmetic; we quantise once at materialisation.
    """

    __slots__ = (
        "actual",
        "by_bkp_group",
        "by_priority",
        "by_status",
        "by_unit",
        "planned",
        "planned_inflated",
    )

    def __init__(self) -> None:
        self.planned: Decimal = Decimal("0")
        self.planned_inflated: Decimal = Decimal("0")
        self.actual: Decimal = Decimal("0")
        self.by_bkp_group: dict[str, list[Decimal]] = defaultdict(_zero_pair)
        self.by_unit: dict[uuid.UUID, list[Decimal]] = defaultdict(_zero_pair)
        self.by_status: dict[CostItemStatus, list[Decimal]] = defaultdict(_zero_pair)
        self.by_priority: dict[CostItemPriority, list[Decimal]] = defaultdict(_zero_pair)

    def add_breakdown_planned(
        self,
        item: CostItem,
        factor: Decimal,
        planned: Decimal,
        allowed: frozenset[uuid.UUID] | None,
    ) -> None:
        group = _top_group(item.bkp_code)
        self.by_bkp_group[group][0] += planned
        self.by_status[item.status][0] += planned
        self.by_priority[item.priority][0] += planned
        _spread_by_unit(self.by_unit, item, factor, planned, allowed, index=0)

    def add_breakdown_actual(
        self,
        item: CostItem,
        factor: Decimal,
        actual: Decimal,
        allowed: frozenset[uuid.UUID] | None,
    ) -> None:
        group = _top_group(item.bkp_code)
        self.by_bkp_group[group][1] += actual
        self.by_status[item.status][1] += actual
        self.by_priority[item.priority][1] += actual
        _spread_by_unit(self.by_unit, item, factor, actual, allowed, index=1)


def _zero_pair() -> list[Decimal]:
    """``[planned, actual]`` pair for a breakdown bucket."""
    return [Decimal("0"), Decimal("0")]


def _spread_by_unit(
    bucket: dict[uuid.UUID, list[Decimal]],
    item: CostItem,
    factor: Decimal,
    amount: Decimal,
    allowed: frozenset[uuid.UUID] | None,
    *,
    index: int,
) -> None:
    """Distribute ``amount`` across an item's allocations.

    ``amount`` already includes the ``factor`` (= scope's permille share /
    1000). We need to split it back across the individual in-scope units in
    proportion to their permille so per-unit totals make sense to a scoped
    viewer. For unscoped callers we use *all* allocations.
    """
    if factor == 0:
        return
    if allowed is None:
        # amount = sum(share_permille)/1000 * raw = raw, so split by share/1000.
        for a in item.allocations:
            unit_share = Decimal(a.share_permille) / _THOUSAND
            bucket[a.unit_id][index] += amount * unit_share
        return
    # Scoped: redistribute ``amount`` across in-scope units proportionally.
    in_scope = [a for a in item.allocations if a.unit_id in allowed]
    total_perm = Decimal("0")
    for a in in_scope:
        total_perm += Decimal(a.share_permille)
    if total_perm == 0:
        return
    for a in in_scope:
        share = Decimal(a.share_permille) / total_perm
        bucket[a.unit_id][index] += amount * share


def _materialise_row(year: int, acc: _RowAcc) -> TimelineRow:
    """Quantise an accumulator into the response DTO."""
    return TimelineRow(
        year=year,
        planned_chf=_q(acc.planned),
        planned_inflated_chf=_q(acc.planned_inflated),
        actual_chf=_q(acc.actual),
        by_bkp_group=_quant_pairs(acc.by_bkp_group),
        by_unit=_quant_pairs(acc.by_unit),
        by_status=_quant_pairs(acc.by_status),
        by_priority=_quant_pairs(acc.by_priority),
    )


def _quant_pairs[K](raw: dict[K, list[Decimal]]) -> dict[K, TimelineBucket]:
    """Convert raw ``[planned, actual]`` pairs into :class:`TimelineBucket` DTOs."""
    return {
        key: TimelineBucket(planned_chf=_q(pair[0]), actual_chf=_q(pair[1]))
        for key, pair in raw.items()
    }


# ---- Object-level totals (used by /finances/overview) -----------------------


async def compute_object_totals(
    session: AsyncSession,
    obj: Object,
    *,
    access: ObjectAccess,
) -> tuple[Decimal, Decimal, Decimal]:
    """Return ``(total_planned_inflated, total_actual, required_per_year)``.

    This is the lightweight roll-up used by the cross-object finance overview.
    We reuse :func:`compute_reserve_plan` so the math stays defined in one
    place and the overview row matches the per-object dashboard exactly.
    """
    reserve = await compute_reserve_plan(session, obj.id, access=access)
    timeline = await compute_timeline(session, obj.id, access=access, inflated=True)
    actual_total = Decimal("0")
    for r in timeline.rows:
        actual_total += r.actual_chf
    return (
        reserve.total_planned_inflated_chf,
        _q(actual_total),
        reserve.required_per_year_chf,
    )


__all__ = [
    "compute_object_totals",
    "compute_reserve_plan",
    "compute_timeline",
]
