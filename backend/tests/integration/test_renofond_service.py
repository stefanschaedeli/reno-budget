"""Phase 5 — Renofond projection math (service layer).

Direct service-level tests over a real Postgres (testcontainers) so the
Decimal/SQL boundary is covered. Covers:

* Per-year balance walk with zero inflation,
* Projection picks up planned spend in the right year (balance dips),
* Actual contributions raise the balance,
* Initial reserve plus required contributions covers the plan -> no underfunding,
* Underfunding-year digest is correct,
* Scoped VIEWER sees pro-rated balances and pro-rated contributions.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from decimal import Decimal

import pytest
from app.models.cost import (
    BkpCode,
    CostItem,
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
from app.services.rbac import ObjectAccess, get_object_access
from app.services.renofond import (
    compute_projection,
    create_contribution,
    delete_contribution,
    list_contributions,
)
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

CURRENT_YEAR = _dt.date.today().year


async def _seed_bkp(session: AsyncSession) -> None:
    session.add_all(
        [
            BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True),
            BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True),
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
    horizon: int = 10,
    initial_reserve: Decimal = Decimal("0"),
) -> tuple[Object, list[Unit]]:
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.MFH,
        planning_horizon_years=horizon,
        contribution_mode=ContributionMode.YEARLY,
        inflation_rate_percent=Decimal("0"),
        initial_reserve_chf=initial_reserve,
    )
    session.add(obj)
    await session.flush()
    units = [
        Unit(object_id=obj.id, label="EG", wertquote_permille=400),
        Unit(object_id=obj.id, label="OG", wertquote_permille=600),
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
    planned: Decimal,
    planned_year: int,
) -> CostItem:
    item = CostItem(
        id=uuid.uuid4(),
        object_id=obj.id,
        bkp_code="D01",
        title="Heizung",
        status=CostItemStatus.PLANNED,
        scope=CostItemScope.SHARED,
        planned_year=planned_year,
        planned_amount_chf=planned,
    )
    session.add(item)
    await session.flush()
    for u in units:
        session.add(
            CostItemUnitAllocation(
                cost_item_id=item.id, unit_id=u.id, share_permille=u.wertquote_permille
            )
        )
    await session.commit()
    return item


def _owner_access() -> ObjectAccess:
    return ObjectAccess(
        membership_id=uuid.uuid4(), role=ObjectRole.OWNER, allowed_unit_ids=None
    )


class TestProjectionBasics:
    async def test_horizon_and_initial_balance(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p_h@example.ch")
        obj, _ = await _mk_object(
            db_session, owner=owner, horizon=5, initial_reserve=Decimal("1000.00")
        )
        proj = await compute_projection(db_session, obj.id, access=_owner_access())
        # Rows span current_year .. current_year + horizon (inclusive).
        years = [r.year for r in proj.rows]
        assert years == [CURRENT_YEAR + i for i in range(0, 6)]
        # With no planned items and no contributions, balance stays at the
        # initial reserve (required_per_year_chf is 0 too).
        for r in proj.rows:
            assert r.balance_chf == Decimal("1000.00")
            assert r.is_underfunded is False
        assert proj.underfunding_years == []

    async def test_planned_spend_dips_balance(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p_s@example.ch")
        obj, units = await _mk_object(
            db_session, owner=owner, horizon=5, initial_reserve=Decimal("0")
        )
        # 5000 planned in Y+3 with horizon 5 -> required_per_year = 1000.
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            planned=Decimal("5000.00"),
            planned_year=CURRENT_YEAR + 3,
        )
        proj = await compute_projection(db_session, obj.id, access=_owner_access())
        assert proj.required_per_year_chf == Decimal("1000.00")
        by_year = {r.year: r for r in proj.rows}
        # Y0: no contribution, no spend -> 0.
        assert by_year[CURRENT_YEAR].balance_chf == Decimal("0.00")
        # Y+1: +1000 contribution -> 1000.
        assert by_year[CURRENT_YEAR + 1].balance_chf == Decimal("1000.00")
        # Y+2: +1000 -> 2000.
        assert by_year[CURRENT_YEAR + 2].balance_chf == Decimal("2000.00")
        # Y+3: +1000 contribution - 5000 spend = -2000 -> underfunded.
        row = by_year[CURRENT_YEAR + 3]
        assert row.balance_chf == Decimal("-2000.00")
        assert row.is_underfunded is True
        # Y+4: -2000 + 1000 = -1000 (still underfunded).
        assert by_year[CURRENT_YEAR + 4].balance_chf == Decimal("-1000.00")
        # Y+5: 0 again.
        assert by_year[CURRENT_YEAR + 5].balance_chf == Decimal("0.00")
        # Underfunding digest reports Y+3 and Y+4.
        bad_years = {u.year for u in proj.underfunding_years}
        assert bad_years == {CURRENT_YEAR + 3, CURRENT_YEAR + 4}

    async def test_actual_contributions_raise_balance(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p_a@example.ch")
        obj, _ = await _mk_object(
            db_session, owner=owner, horizon=5, initial_reserve=Decimal("0")
        )
        await create_contribution(
            db_session,
            obj.id,
            year=CURRENT_YEAR + 1,
            amount_chf=Decimal("2500.00"),
            note="Extraordinary deposit",
        )
        await db_session.commit()
        proj = await compute_projection(db_session, obj.id, access=_owner_access())
        by_year = {r.year: r for r in proj.rows}
        assert by_year[CURRENT_YEAR + 1].actual_contribution_chf == Decimal("2500.00")
        # Y0: 0. Y+1: +0 required + 2500 actual = 2500.
        assert by_year[CURRENT_YEAR + 1].balance_chf == Decimal("2500.00")


class TestContributionsCrud:
    async def test_create_list_delete(self, db_session: AsyncSession) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "c_cl@example.ch")
        obj, _ = await _mk_object(db_session, owner=owner)
        row = await create_contribution(
            db_session, obj.id, year=CURRENT_YEAR, amount_chf=Decimal("100.00"), note=None
        )
        await db_session.commit()
        rows = await list_contributions(db_session, obj.id)
        assert len(rows) == 1
        assert rows[0].amount_chf == Decimal("100.00")
        ok = await delete_contribution(db_session, obj.id, row.id)
        await db_session.commit()
        assert ok is True
        assert await list_contributions(db_session, obj.id) == []


class TestScopedViewerProjection:
    async def test_scoped_viewer_pro_rates_everything(
        self, db_session: AsyncSession
    ) -> None:
        await _seed_bkp(db_session)
        owner = await _mk_user(db_session, "p_v@example.ch")
        viewer = await _mk_user(db_session, "p_vv@example.ch")
        obj, units = await _mk_object(
            db_session,
            owner=owner,
            horizon=5,
            initial_reserve=Decimal("1000.00"),
        )
        # 5000 planned in Y+3 -> 400 ‰ share = 2000.
        await _add_item(
            db_session,
            obj=obj,
            units=units,
            planned=Decimal("5000.00"),
            planned_year=CURRENT_YEAR + 3,
        )
        # Owner-recorded contribution: 1000 in Y+1.
        await create_contribution(
            db_session,
            obj.id,
            year=CURRENT_YEAR + 1,
            amount_chf=Decimal("1000.00"),
            note=None,
        )
        # Viewer scoped to EG (400 ‰).
        m = ObjectMembership(
            user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER
        )
        db_session.add(m)
        await db_session.flush()
        db_session.add(UnitScope(membership_id=m.id, unit_id=units[0].id))
        await db_session.commit()

        access = await get_object_access(db_session, viewer, obj.id)
        assert access is not None
        proj = await compute_projection(db_session, obj.id, access=access)
        assert proj.scope_pro_rated is True
        # Initial reserve pro-rated: 1000 * 0.4 = 400.
        assert proj.initial_reserve_chf == Decimal("400.00")
        by_year = {r.year: r for r in proj.rows}
        # Y+1 contribution pro-rated: 1000 * 0.4 = 400.
        assert by_year[CURRENT_YEAR + 1].actual_contribution_chf == Decimal("400.00")
        # Y+3 planned pro-rated: 5000 * 0.4 = 2000.
        assert by_year[CURRENT_YEAR + 3].planned_spend_chf == Decimal("2000.00")
