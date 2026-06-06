"""Phase 4 — cross-object finance roll-up at ``GET /api/v1/finances/overview``.

Covers:

* roll-up returns correct totals across multiple objects,
* hides objects the user isn't a member of,
* pro-rates per-object numbers for scoped memberships.
"""

from __future__ import annotations

import datetime as _dt
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from app.core.security import hash_password
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
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "TestPasswort-9!ABC"
CURRENT_YEAR = _dt.date.today().year


async def _mk_user(session: AsyncSession, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password(PW),
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u


async def _login(client: AsyncClient, email: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": PW})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _auth(token: str, client: AsyncClient) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def _mk_object_with_item(
    session: AsyncSession,
    *,
    name: str,
    owner: User,
    planned: Decimal,
    horizon: int = 10,
) -> tuple[Object, list[Unit]]:
    obj = Object(
        id=uuid.uuid4(),
        name=name,
        type=ObjectType.MFH,
        planning_horizon_years=horizon,
        contribution_mode=ContributionMode.YEARLY,
        inflation_rate_percent=Decimal("0"),
        initial_reserve_chf=Decimal("0"),
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
    item = CostItem(
        id=uuid.uuid4(),
        object_id=obj.id,
        bkp_code="D01",
        title="Plan",
        status=CostItemStatus.PLANNED,
        scope=CostItemScope.SHARED,
        planned_year=CURRENT_YEAR + 2,
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
    return obj, units


@pytest_asyncio.fixture()
async def seed_bkp(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True),
            BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True),
        ]
    )
    await db_session.commit()


class TestOverview:
    async def test_returns_both_objects_for_owner(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        seed_bkp: None,
    ) -> None:
        owner = await _mk_user(db_session, "fa1@x.ch")
        await _mk_object_with_item(
            db_session, name="Haus A", owner=owner, planned=Decimal("10000.00")
        )
        await _mk_object_with_item(
            db_session, name="Haus B", owner=owner, planned=Decimal("5000.00")
        )
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            "/api/v1/finances/overview", headers=_auth(token, integration_client)
        )
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        assert len(items) == 2
        by_name = {it["name"]: it for it in items}
        assert by_name["Haus A"]["total_planned_inflated_chf"] == "10000.00"
        assert by_name["Haus A"]["required_per_year_chf"] == "1000.00"
        assert by_name["Haus B"]["required_per_year_chf"] == "500.00"
        assert by_name["Haus A"]["scope_pro_rated"] is False
        assert by_name["Haus A"]["role"] == "owner"

    async def test_hides_objects_user_is_not_member_of(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        seed_bkp: None,
    ) -> None:
        owner = await _mk_user(db_session, "fa2-o@x.ch")
        other = await _mk_user(db_session, "fa2-x@x.ch")
        await _mk_object_with_item(
            db_session, name="Foreign", owner=owner, planned=Decimal("1000.00")
        )
        token = await _login(integration_client, other.email)
        r = await integration_client.get(
            "/api/v1/finances/overview", headers=_auth(token, integration_client)
        )
        assert r.status_code == 200
        assert r.json()["items"] == []

    async def test_pro_rates_for_scoped_viewer(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        seed_bkp: None,
    ) -> None:
        owner = await _mk_user(db_session, "fa3-o@x.ch")
        viewer = await _mk_user(db_session, "fa3-v@x.ch")
        obj, units = await _mk_object_with_item(
            db_session, name="Geteilt", owner=owner, planned=Decimal("10000.00")
        )
        m = ObjectMembership(user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER)
        db_session.add(m)
        await db_session.flush()
        db_session.add(UnitScope(membership_id=m.id, unit_id=units[0].id))
        await db_session.commit()

        token = await _login(integration_client, viewer.email)
        r = await integration_client.get(
            "/api/v1/finances/overview", headers=_auth(token, integration_client)
        )
        assert r.status_code == 200
        items = r.json()["items"]
        assert len(items) == 1
        row = items[0]
        # 10000 * 400/1000 = 4000.
        assert row["total_planned_inflated_chf"] == "4000.00"
        assert row["scope_pro_rated"] is True
        assert row["role"] == "viewer"
