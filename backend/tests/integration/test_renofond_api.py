"""Phase 5 — HTTP routes for Renofond projection + contributions.

Covers happy paths, RBAC matrix (owner can mutate, viewer can read,
outsider gets 404), and CSRF enforcement on mutations.
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
    owner = await _mk_user(db_session, "owner@r.ch")
    editor = await _mk_user(db_session, "editor@r.ch")
    viewer = await _mk_user(db_session, "viewer@r.ch")
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.MFH,
        planning_horizon_years=5,
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

    item = CostItem(
        id=uuid.uuid4(),
        object_id=obj.id,
        bkp_code="D01",
        title="Heizung",
        status=CostItemStatus.PLANNED,
        scope=CostItemScope.SHARED,
        planned_year=CURRENT_YEAR + 3,
        planned_amount_chf=Decimal("5000.00"),
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


class TestProjectionEndpoint:
    async def test_owner_sees_projection(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/renofond/projection",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["current_year"] == CURRENT_YEAR
        assert data["horizon_until_year"] == CURRENT_YEAR + 5
        assert data["required_per_year_chf"] == "1000.00"
        # Y+3 should have planned_spend 5000 and balance dipping.
        y3 = next(r for r in data["rows"] if r["year"] == CURRENT_YEAR + 3)
        assert y3["planned_spend_chf"] == "5000.00"
        assert y3["is_underfunded"] is True
        assert data["scope_pro_rated"] is False

    async def test_viewer_sees_pro_rated(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, _, viewer, obj, _ = setup
        token = await _login(integration_client, viewer.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/renofond/projection",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["scope_pro_rated"] is True
        y3 = next(r for r in data["rows"] if r["year"] == CURRENT_YEAR + 3)
        # 5000 * 500/1000 = 2500.
        assert y3["planned_spend_chf"] == "2500.00"

    async def test_outsider_gets_404(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, _, _, obj, _ = setup
        outsider = await _mk_user(db_session, "out@r.ch")
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/renofond/projection",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404


class TestContributionsRbac:
    async def test_owner_can_post_and_delete(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        # POST
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"year": CURRENT_YEAR, "amount_chf": "500.00", "note": "First deposit"},
        )
        assert r.status_code == 201, r.text
        cid = r.json()["id"]
        # GET list
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert len(r.json()["items"]) == 1
        # DELETE
        r = await integration_client.delete(
            f"/api/v1/objects/{obj.id}/renofond/contributions/{cid}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r.status_code == 204

    async def test_viewer_can_read_but_not_mutate(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, _, viewer, obj, _ = setup
        token = await _login(integration_client, viewer.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"year": CURRENT_YEAR, "amount_chf": "100.00"},
        )
        assert r.status_code == 403

    async def test_editor_cannot_mutate(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, editor, _, obj, _ = setup
        token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"year": CURRENT_YEAR, "amount_chf": "100.00"},
        )
        assert r.status_code == 403

    async def test_outsider_gets_404_on_contributions(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        _, _, _, obj, _ = setup
        outsider = await _mk_user(db_session, "out2@r.ch")
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404

    async def test_csrf_required_for_post(
        self,
        integration_client: AsyncClient,
        setup: tuple[User, User, User, Object, list[Unit]],
    ) -> None:
        owner, _, _, obj, _ = setup
        token = await _login(integration_client, owner.email)
        # Send header but strip the cookie -> 403 from require_csrf.
        headers = {"Authorization": f"Bearer {token}", "X-CSRF-Token": "wrong"}
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/renofond/contributions",
            headers=headers,
            cookies={},
            json={"year": CURRENT_YEAR, "amount_chf": "100.00"},
        )
        assert r.status_code == 403
