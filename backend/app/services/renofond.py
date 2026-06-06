"""Renofond projection + actual-contribution service (Phase 5).

Builds on Phase 4 (``app.services.budgets``) which already computes the
required-contribution math from the inflated timeline. This module adds the
**time-series** view: an end-of-year balance for each planning year that
walks the reserve forward through the planning horizon and surfaces years
where the balance dips below zero (underfunding).

Math (all Decimal, half-up rounding to 2 decimals at the API boundary)::

    balance[Y_0 - 1] = initial_reserve
    for each Y in [current_year .. current_year + horizon]:
        balance[Y] = balance[Y-1]
                   + required_per_year_chf       # idealised target deposit
                   + Σ actual_contributions(Y)   # owner-recorded deposits
                   - Σ planned_spend(Y)          # inflated planned cost-items
        is_underfunded[Y] = balance[Y] < 0

We surface BOTH the required contribution (so the UI can show the target)
and the actual recorded contributions (so the UI can show what really
happened). The projection uses the required figure as the modelled deposit
because that's what the owner committed to in Phase 4; the actuals tell the
user whether they're keeping up.

Scoped EDITOR/VIEWER access pro-rates **everything** (initial reserve,
required contribution, planned spend, actual contributions) by the same
Wertquoten share. Outsiders never reach this code — :func:`require_object_access_dep`
rejects them with 404.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.renofond import ReserveContribution
from app.schemas.renofond import (
    ContributionRead,
    ProjectionResponse,
    ProjectionRow,
    UnderfundingYear,
)
from app.services.budgets import compute_reserve_plan, compute_timeline
from app.services.rbac import ObjectAccess

_CHF_QUANT = Decimal("0.01")
_THOUSAND = Decimal("1000")


def _q(value: Decimal) -> Decimal:
    """Round a CHF amount to 2 decimals, half-up."""
    return value.quantize(_CHF_QUANT, rounding=ROUND_HALF_UP)


def _current_year() -> int:
    """Today's calendar year — wrapped so tests can monkeypatch if needed."""
    return _dt.date.today().year


async def _scope_factor(
    session: AsyncSession, object_id: uuid.UUID, access: ObjectAccess
) -> Decimal:
    """Pro-rate factor for an object-wide quantity (initial reserve, contributions).

    Mirrors the helper in :mod:`app.services.budgets` so we stay consistent.
    """
    if access.allowed_unit_ids is None:
        return Decimal("1")
    from app.repositories.object import list_units

    units = await list_units(session, object_id)
    in_scope = Decimal("0")
    for u in units:
        if u.id in access.allowed_unit_ids:
            in_scope += Decimal(u.wertquote_permille)
    return in_scope / _THOUSAND


async def list_contributions(
    session: AsyncSession, object_id: uuid.UUID
) -> list[ReserveContribution]:
    """Return all contribution rows for ``object_id`` ordered by (year, created_at)."""
    rows = (
        await session.execute(
            select(ReserveContribution)
            .where(ReserveContribution.object_id == object_id)
            .order_by(ReserveContribution.year, ReserveContribution.created_at)
        )
    ).scalars().all()
    return list(rows)


async def create_contribution(
    session: AsyncSession,
    object_id: uuid.UUID,
    *,
    year: int,
    amount_chf: Decimal,
    note: str | None,
) -> ReserveContribution:
    """Insert a new contribution row (caller has already verified OWNER)."""
    row = ReserveContribution(
        object_id=object_id, year=year, amount_chf=amount_chf, note=note
    )
    session.add(row)
    await session.flush()
    return row


async def delete_contribution(
    session: AsyncSession, object_id: uuid.UUID, contribution_id: uuid.UUID
) -> bool:
    """Delete a contribution; returns True if a row was removed."""
    row = (
        await session.execute(
            select(ReserveContribution).where(
                ReserveContribution.id == contribution_id,
                ReserveContribution.object_id == object_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    await session.delete(row)
    return True


def _to_read(row: ReserveContribution) -> ContributionRead:
    return ContributionRead.model_validate(row)


async def compute_projection(
    session: AsyncSession,
    object_id: uuid.UUID,
    *,
    access: ObjectAccess,
) -> ProjectionResponse:
    """Walk the reserve balance forward year-by-year over the planning horizon.

    Returns one :class:`ProjectionRow` per year in
    ``[current_year .. current_year + horizon]`` plus a digested list of
    ``underfunding_years`` for quick UI banner rendering.
    """
    # Phase 4 already does the hard math (pro-rating, inflation, reserve floor).
    plan = await compute_reserve_plan(session, object_id, access=access)
    timeline = await compute_timeline(
        session, object_id, access=access, inflated=True
    )

    current_year = timeline.current_year
    horizon_end = timeline.horizon_until_year

    # Inflated planned spend per year (post-pro-rating already).
    planned_per_year: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for r in timeline.rows:
        if r.year >= current_year:
            planned_per_year[r.year] += r.planned_inflated_chf

    # Actual contributions per year (pro-rated for scoped callers).
    scope_factor = await _scope_factor(session, object_id, access)
    raw_rows = await list_contributions(session, object_id)
    actual_per_year: dict[int, Decimal] = defaultdict(lambda: Decimal("0"))
    for row in raw_rows:
        actual_per_year[row.year] += row.amount_chf * scope_factor

    initial_reserve = plan.initial_reserve_chf
    required_per_year = plan.required_per_year_chf

    rows: list[ProjectionRow] = []
    underfunding: list[UnderfundingYear] = []
    balance = initial_reserve
    cumulative_planned = Decimal("0")
    for year in range(current_year, horizon_end + 1):
        planned = planned_per_year.get(year, Decimal("0"))
        actual = actual_per_year.get(year, Decimal("0"))
        # In the current year we don't yet model a "required" deposit because
        # the reserve plan is forward-looking from next year; this keeps the
        # opening balance equal to the initial reserve and avoids
        # double-counting against the cumulative target in Y0.
        contribution = required_per_year if year > current_year else Decimal("0")
        balance = balance + contribution + actual - planned
        cumulative_planned += planned
        is_underfunded = balance < 0
        rows.append(
            ProjectionRow(
                year=year,
                required_contribution_chf=_q(contribution),
                actual_contribution_chf=_q(actual),
                planned_spend_chf=_q(planned),
                balance_chf=_q(balance),
                cumulative_planned_chf=_q(cumulative_planned),
                is_underfunded=is_underfunded,
            )
        )
        if is_underfunded:
            underfunding.append(
                UnderfundingYear(year=year, shortfall_chf=_q(-balance))
            )

    return ProjectionResponse(
        object_id=object_id,
        current_year=current_year,
        horizon_until_year=horizon_end,
        inflation_rate_percent=plan.inflation_rate_percent,
        initial_reserve_chf=_q(initial_reserve),
        required_per_year_chf=_q(required_per_year),
        rows=rows,
        underfunding_years=underfunding,
        scope_pro_rated=access.allowed_unit_ids is not None,
    )


__all__ = [
    "compute_projection",
    "create_contribution",
    "delete_contribution",
    "list_contributions",
]
