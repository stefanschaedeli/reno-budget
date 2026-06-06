"""Phase 4 — budget aggregation math.

Direct service-level tests against a real Postgres (testcontainers) so the
Decimal/SQL boundary is covered too. Covers:

* per-year planned/actual buckets,
* inflation compounding (rate 0 and 1.5 %),
* status filter (COMPLETED/CANCELLED excluded from planned, included via
  actual_date if there's an actual amount),
* reserve plan subtracts ``initial_reserve_chf``,
* RBAC pro-rating for scoped VIEWER.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from decimal import Decimal

import pytest
from app.models.cost import (
    BkpCode,
    CostItem,
    CostItemPriority,
    CostItemScope,
    CostItemStatus,
    CostItemUnitAllocation,
)
from app.models.object import (
    ContributionMode,
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
    UnitScope,
)
from app.models.user import User
from app.services.budgets import compute_reserve_plan, compute_timeline
from app.services.rbac import ObjectAccess, get_object_access
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CURRENT_YEAR = _dt.date.today().year


async def _seed_bkp(session: AsyncSession) -> None:
    session.add_all(
        [
            BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True),
            BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True),
            BkpCode(code="E", parent_code=None, level=1, label_de="Inneres", is_seed=True),
            BkpCode(code="E01", parent_code="E", level=2, label_de="Bad", is_seed=True),
        ]
    )
    await session.commit()


async def _mk_user(session: AsyncSession, email: str) -> User:
    from app.core.security import hash_password

    u = User(
        id=uuid.uuid4(),
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password("TestPasswort-9!ABC"),
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u


async def _mk_object(
    session: AsyncSession,
    *,
    owner: User,
    horizon: int = 30,
    inflation: Decimal = Decimal("0"),
    initial_reserve: Decimal = Decimal("0"),
) -> tuple[Object, list[Unit]]:
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.MFH,
        planning_horizon_years=horizon,
        contribution_mode=ContributionMode.YEARLY,
        inflation_rate_percent=inflation,
        initial_reserve_chf=initial_reserve,
    )
    session.add(obj)
    await session.flush()
    units = [
        Unit(object_id=obj.id, label="EG", wertquote_permille=400),
        Unit(object_id=obj.id, label="1.OG", wertquote_permille=300),
        Unit(object_id=obj.id, label="DG", wertquote_permille=300),
    ]
    for u in units:
        session.add(u)
    session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    await session.commit()
    return obj, units


async def _add_item(
    session: AsyncSession,
    *,
    obj: Object,
    units: list[Unit],
    bkp: str,
    title: str,
    planned: Decimal | None = None,
    planned_year: int | None = None,
    actual: Decimal | None = None,
    actual_date: _dt.date | None = None,
    status: CostItemStatus = CostItemStatus.PLANNED,
    priority: CostItemPriority = CostItemPriority.MED,
    allocations: list[tuple[Unit, int]] | None = None,
) -> CostItem:
    item = CostItem(
        id=uuid.uuid4(),
        object_id=obj.id,
        bkp_code=bkp,
        title=title,
        status=status,
        priority=priority,
        scope=CostItemScope.SHARED,
        planned_year=planned_year,
        planned_amount_chf=planned,
        actual_amount_chf=actual,
        actual_date=actual_date,
    )
    session.add(item)
    await session.flush()
    rows = allocations if allocations is not None else [(u, u.wertquote_permille) for u in units]
    for u, perm in rows:
        session.add(
            CostItemUnitAllocation(cost_item_id=item.id, unit_id=u.id, share_permille=perm)
        )
    await session.commit()
    return item


def _owner_access() -> ObjectAccess:
    return ObjectAccess(
        membership_id=uuid.uuid4(), role=ObjectRole.OWNER, allowed_unit_ids=None
    )


# ---- Tests ------------------------------------------------------------------


class TestTimelineBasics:
    async def test_planned_buckets_by_year(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "o1@example.ch")
        obj, units = await _mk_object(db_session, owner=owner)
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Heizung",
            planned=Decimal("10000.00"),
            planned_year=CURRENT_YEAR + 5,
        )
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="E01",
            title="Bad",
            planned=Decimal("5000.00"),
            planned_year=CURRENT_YEAR + 5,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=False
        )
        target = next(r for r in tl.rows if r.year == CURRENT_YEAR + 5)
        assert target.planned_chf == Decimal("15000.00")
        # Without inflation, inflated == planned.
        assert target.planned_inflated_chf == Decimal("15000.00")
        # Breakdown sums to row total.
        assert (
            target.by_bkp_group["D"].planned_chf + target.by_bkp_group["E"].planned_chf
            == target.planned_chf
        )

    async def test_actual_bucket_by_actual_date_year(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "o2@example.ch")
        obj, units = await _mk_object(db_session, owner=owner)
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Heizung-Reparatur",
            planned=Decimal("1.00"),  # required to satisfy the "has amount" check
            planned_year=CURRENT_YEAR - 2,
            actual=Decimal("8000.00"),
            actual_date=_dt.date(CURRENT_YEAR - 1, 4, 10),
            status=CostItemStatus.COMPLETED,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=False
        )
        last_year_row = next(r for r in tl.rows if r.year == CURRENT_YEAR - 1)
        assert last_year_row.actual_chf == Decimal("8000.00")
        # COMPLETED + planned_year set MUST NOT contribute to planned.
        assert last_year_row.planned_chf == Decimal("0.00")

    async def test_cancelled_excluded_from_planned(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "o3@example.ch")
        obj, units = await _mk_object(db_session, owner=owner)
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Abgesagt",
            planned=Decimal("999.00"),
            planned_year=CURRENT_YEAR + 3,
            status=CostItemStatus.CANCELLED,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=False
        )
        future = next(r for r in tl.rows if r.year == CURRENT_YEAR + 3)
        assert future.planned_chf == Decimal("0.00")


class TestInflation:
    async def test_rate_zero_means_identical(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "i1@example.ch")
        obj, units = await _mk_object(db_session, owner=owner)
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Z",
            planned=Decimal("1000.00"),
            planned_year=CURRENT_YEAR + 10,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=True
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 10)
        assert row.planned_inflated_chf == Decimal("1000.00")

    async def test_rate_1p5_compounds(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "i2@example.ch")
        obj, units = await _mk_object(
            db_session, owner=owner, inflation=Decimal("1.500")
        )
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Z",
            planned=Decimal("1000.00"),
            planned_year=CURRENT_YEAR + 10,
        )
        tl = await compute_timeline(
            db_session, obj.id, access=_owner_access(), inflated=True
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 10)
        # 1000 * 1.015^10 = 1160.541 -> rounded 1160.54
        assert row.planned_inflated_chf == Decimal("1160.54")


class TestReservePlan:
    async def test_subtracts_initial_reserve(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "r1@example.ch")
        obj, units = await _mk_object(
            db_session,
            owner=owner,
            horizon=10,
            initial_reserve=Decimal("4000.00"),
        )
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Z",
            planned=Decimal("10000.00"),
            planned_year=CURRENT_YEAR + 5,
        )
        plan = await compute_reserve_plan(
            db_session, obj.id, access=_owner_access()
        )
        assert plan.total_planned_inflated_chf == Decimal("10000.00")
        assert plan.initial_reserve_chf == Decimal("4000.00")
        assert plan.required_total_chf == Decimal("6000.00")
        assert plan.required_per_year_chf == Decimal("600.00")
        assert plan.required_per_month_chf == Decimal("50.00")
        # One future planned year → one lump sum row.
        assert len(plan.required_lump_sums) == 1
        assert plan.required_lump_sums[0].year == CURRENT_YEAR + 5

    async def test_reserve_floors_at_zero(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "r2@example.ch")
        obj, units = await _mk_object(
            db_session,
            owner=owner,
            horizon=10,
            initial_reserve=Decimal("999999.00"),
        )
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Z",
            planned=Decimal("1000.00"),
            planned_year=CURRENT_YEAR + 2,
        )
        plan = await compute_reserve_plan(
            db_session, obj.id, access=_owner_access()
        )
        assert plan.required_total_chf == Decimal("0.00")
        assert plan.required_per_year_chf == Decimal("0.00")


class TestRbacProRating:
    async def test_scoped_viewer_sees_pro_rated_planned(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p1@example.ch")
        viewer = await _mk_user(db_session, "p1v@example.ch")
        obj, units = await _mk_object(
            db_session, owner=owner, initial_reserve=Decimal("1000.00")
        )
        # SHARED item, split by Wertquoten (400/300/300).
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Dach",
            planned=Decimal("10000.00"),
            planned_year=CURRENT_YEAR + 2,
        )
        # Viewer scoped to EG (400‰).
        membership = ObjectMembership(
            user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER
        )
        db_session.add(membership)
        await db_session.flush()
        db_session.add(UnitScope(membership_id=membership.id, unit_id=units[0].id))
        await db_session.commit()

        access = await get_object_access(db_session, viewer, obj.id)
        assert access is not None
        tl = await compute_timeline(
            db_session, obj.id, access=access, inflated=False
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 2)
        # 10000 * 400/1000 = 4000.
        assert row.planned_chf == Decimal("4000.00")
        assert tl.scope_pro_rated is True

        plan = await compute_reserve_plan(db_session, obj.id, access=access)
        # Initial reserve also pro-rated by Wertquoten share: 1000 * 0.4 = 400.
        assert plan.initial_reserve_chf == Decimal("400.00")
        assert plan.total_planned_inflated_chf == Decimal("4000.00")
        assert plan.required_total_chf == Decimal("3600.00")
        assert plan.scope_pro_rated is True

    async def test_scoped_viewer_excludes_non_intersecting_items(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p2@example.ch")
        viewer = await _mk_user(db_session, "p2v@example.ch")
        obj, units = await _mk_object(db_session, owner=owner)
        # UNIT item attributed 100 % to units[1] (1.OG).
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            bkp="D01",
            title="Bad 1.OG",
            planned=Decimal("5000.00"),
            planned_year=CURRENT_YEAR + 1,
            allocations=[(units[1], 1000)],
        )
        # Viewer scoped to EG.
        membership = ObjectMembership(
            user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER
        )
        db_session.add(membership)
        await db_session.flush()
        db_session.add(UnitScope(membership_id=membership.id, unit_id=units[0].id))
        await db_session.commit()

        access = await get_object_access(db_session, viewer, obj.id)
        assert access is not None
        tl = await compute_timeline(
            db_session, obj.id, access=access, inflated=False
        )
        row = next(r for r in tl.rows if r.year == CURRENT_YEAR + 1)
        assert row.planned_chf == Decimal("0.00")
