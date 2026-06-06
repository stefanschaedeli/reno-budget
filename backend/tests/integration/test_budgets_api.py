"""Phase 4 — HTTP routes for budget timeline and reserve plan.

Covers 200/403/404 paths, OWNER vs EDITOR vs scoped VIEWER, and validation
of the new Object PATCH fields (rate range, reserve non-negative, mode enum).
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
    headers = {"Authorization": f"Bearer {token}"}
    csrf = client.cookies.get("reno_csrf")
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return headers


def _csrf_cookies(client: AsyncClient) -> dict[str, str]:
    csrf = client.cookies.get("reno_csrf")
    return {"reno_csrf": csrf} if csrf else {}


@pytest_asyncio.fixture()
async def seed_bkp(db_session: AsyncSession) -> None:
    db_session.add_all(
        [
            BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True),
            BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True),
        ]
    )
    await db_session.commit()


@pytest_asyncio.fixture()
async def setup(
    db_session: AsyncSession, seed_bkp: None
) -> tuple[User, User, User, Object, list[Unit]]:
    owner = await _mk_user(db_session, "owner@b.ch")
    editor = await _mk_user(db_session, "editor@b.ch")
    viewer = await _mk_user(db_session, "viewer@b.ch")
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.MFH,
        planning_horizon_years=20,
        contribution_mode=ContributionMode.YEARLY,
        inflation_rate_percent=Decimal("0"),
        initial_reserve_chf=Decimal("0"),
    )
    db_session.add(obj)
    await db_session.flush()
    units = [
        Unit(object_id=obj.id, label="EG", wertquote_permille=500),
        Unit(object_id=obj.id, label="OG", wertquote_permille=500),
    ]
    for u in units:
        db_session.add(u)
    db_session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    db_session.add(ObjectMembership(user_id=editor.id, object_id=obj.id, role=ObjectRole.EDITOR))
    m_viewer = ObjectMembership(user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER)
    db_session.add(m_viewer)
    await db_session.flush()
    db_session.add(UnitScope(membership_id=m_viewer.id, unit_id=units[0].id))

    # One planned item.
    item = CostItem(
        id=uuid.uuid4(),
        object_id=obj.id,
        bkp_code="D01",
        title="Heizung",
        status=CostItemStatus.PLANNED,
        scope=CostItemScope.SHARED,
        planned_year=CURRENT_YEAR + 3,
        planned_amount_chf=Decimal("10000.00"),
    )
    db_session.add(item)
    await db_session.flush()
    for u in units:
        db_session.add(
            CostItemUnitAllocation(
                cost_item_id=item.id, unit_id=u.id, share_permille=u.wertquote_permille
            )
        )
    await db_session.commit()
    return owner, editor, viewer, obj, units


class TestTimelineEndpoint:
    async def test_owner_sees_full_numbers(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/budget/timeline?inflated=false",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        row = next(x for x in data["rows"] if x["year"] == CURRENT_YEAR + 3)
        assert row["planned_chf"] == "10000.00"
        assert data["scope_pro_rated"] is False

    async def test_scoped_viewer_sees_pro_rated(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, _, viewer, obj, _ = setup
        token = await _login(integration_client, viewer.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/budget/timeline",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        row = next(x for x in data["rows"] if x["year"] == CURRENT_YEAR + 3)
        # 10000 * 500/1000 = 5000.
        assert row["planned_chf"] == "5000.00"
        assert data["scope_pro_rated"] is True

    async def test_outsider_gets_404(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, _, _, obj, _ = setup
        outsider = await _mk_user(db_session, "out@b.ch")
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/budget/timeline",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404


class TestReserveEndpoint:
    async def test_owner_gets_reserve_plan(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/budget/reserve",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["horizon_years"] == 20
        assert data["total_planned_inflated_chf"] == "10000.00"
        # 10000/20 = 500.
        assert data["required_per_year_chf"] == "500.00"


class TestObjectPatchNewFields:
    async def test_owner_can_patch_finance_fields(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.patch(
            f"/api/v1/objects/{obj.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "contribution_mode": "monthly",
                "inflation_rate_percent": "1.500",
                "initial_reserve_chf": "1234.56",
            },
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["contribution_mode"] == "monthly"
        assert body["inflation_rate_percent"] == "1.500"
        assert body["initial_reserve_chf"] == "1234.56"

    async def test_editor_cannot_patch(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, editor, _, obj, _ = setup
        token = await _login(integration_client, editor.email)
        r = await integration_client.patch(
            f"/api/v1/objects/{obj.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"inflation_rate_percent": "1.000"},
        )
        assert r.status_code == 403

    async def test_inflation_rate_capped(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.patch(
            f"/api/v1/objects/{obj.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"inflation_rate_percent": "25.000"},
        )
        assert r.status_code == 422

    async def test_negative_reserve_rejected(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.patch(
            f"/api/v1/objects/{obj.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"initial_reserve_chf": "-1.00"},
        )
        assert r.status_code == 422

    async def test_invalid_mode_rejected(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.patch(
            f"/api/v1/objects/{obj.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"contribution_mode": "weekly"},
        )
        assert r.status_code == 422
