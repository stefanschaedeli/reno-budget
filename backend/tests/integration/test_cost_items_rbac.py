"""Full RBAC matrix for cost items (Phase 3).

Covers OWNER / EDITOR / VIEWER x unscoped / scoped x list / create / update
/ delete x SHARED / UNIT scope visibility. Uses the same testcontainers
Postgres fixture as Phase 2; mirrors the style of ``test_objects_rbac.py``.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.models.cost import BkpCode
from app.models.object import (
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


async def _mk_user(session: AsyncSession, email: str, *, super_: bool = False) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password(PW),
        is_active=True,
        is_superuser=super_,
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


async def _grant(
    session: AsyncSession,
    *,
    user: User,
    obj: Object,
    role: ObjectRole,
    scope_units: list[Unit] | None = None,
) -> ObjectMembership:
    m = ObjectMembership(user_id=user.id, object_id=obj.id, role=role)
    session.add(m)
    await session.flush()
    for u in scope_units or []:
        session.add(UnitScope(membership_id=m.id, unit_id=u.id))
    await session.commit()
    return m


# ---- Fixtures ---------------------------------------------------------------


@pytest_asyncio.fixture()
async def owner(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "owner@example.ch")


@pytest_asyncio.fixture()
async def editor(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "editor@example.ch")


@pytest_asyncio.fixture()
async def viewer(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "viewer@example.ch")


@pytest_asyncio.fixture()
async def outsider(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "outsider@example.ch")


@pytest_asyncio.fixture()
async def seed_bkp(db_session: AsyncSession) -> None:
    """Insert a minimal eBKP-H seed used by cost items in the tests."""
    db_session.add(BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True))
    db_session.add(BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True))
    await db_session.commit()


@pytest_asyncio.fixture()
async def mfh(db_session: AsyncSession, owner: User) -> tuple[Object, list[Unit]]:
    """MFH with three units (400/300/300) and an OWNER membership."""
    obj = Object(
        id=uuid.uuid4(),
        name="Haus Bahnhofstrasse 1",
        type=ObjectType.MFH,
        planning_horizon_years=30,
    )
    db_session.add(obj)
    await db_session.flush()
    units = [
        Unit(object_id=obj.id, label="EG", wertquote_permille=400),
        Unit(object_id=obj.id, label="1.OG", wertquote_permille=300),
        Unit(object_id=obj.id, label="DG", wertquote_permille=300),
    ]
    for u in units:
        db_session.add(u)
    db_session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    await db_session.commit()
    # Reload units to get persisted IDs.
    from sqlalchemy import select

    persisted = (
        (
            await db_session.execute(
                select(Unit).where(Unit.object_id == obj.id).order_by(Unit.label)
            )
        )
        .scalars()
        .all()
    )
    return obj, list(persisted)


async def _create_shared_item(
    client: AsyncClient,
    *,
    token: str,
    object_id: uuid.UUID,
    title: str = "Heizungsersatz",
    amount: str = "20000.00",
) -> dict[str, object]:
    r = await client.post(
        f"/api/v1/objects/{object_id}/cost-items",
        headers=_auth(token, client),
        cookies=_csrf_cookies(client),
        json={
            "bkp_code": "D01",
            "title": title,
            "planned_amount_chf": amount,
            "scope": "shared",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---- Tests ------------------------------------------------------------------


class TestOwnerHappyPath:
    async def test_owner_can_create_shared_with_auto_allocations(
        self,
        integration_client: AsyncClient,
        owner: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _units = mfh
        token = await _login(integration_client, owner.email)
        body = await _create_shared_item(integration_client, token=token, object_id=obj.id)
        # Auto-materialised from Wertquoten: three rows summing to 1000.
        allocs = body["allocations"]
        assert len(allocs) == 3
        assert sum(a["share_permille"] for a in allocs) == 1000

    async def test_owner_can_list_and_get(
        self,
        integration_client: AsyncClient,
        owner: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = mfh
        token = await _login(integration_client, owner.email)
        created = await _create_shared_item(integration_client, token=token, object_id=obj.id)

        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert any(i["id"] == created["id"] for i in r.json())

        r2 = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items/{created['id']}",
            headers=_auth(token, integration_client),
        )
        assert r2.status_code == 200

    async def test_owner_can_patch_and_delete(
        self,
        integration_client: AsyncClient,
        owner: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = mfh
        token = await _login(integration_client, owner.email)
        created = await _create_shared_item(integration_client, token=token, object_id=obj.id)

        r = await integration_client.patch(
            f"/api/v1/objects/{obj.id}/cost-items/{created['id']}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"title": "Heizung neu", "status": "planned"},
        )
        assert r.status_code == 200, r.text
        assert r.json()["title"] == "Heizung neu"

        r2 = await integration_client.delete(
            f"/api/v1/objects/{obj.id}/cost-items/{created['id']}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r2.status_code == 204


class TestViewer:
    async def test_unscoped_viewer_can_list_but_not_create(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        viewer: User,
        owner: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = mfh
        # Owner seeds an item.
        owner_token = await _login(integration_client, owner.email)
        await _create_shared_item(integration_client, token=owner_token, object_id=obj.id)

        # Now grant viewer + log them in (fresh cookie jar).
        await _grant(db_session, user=viewer, obj=obj, role=ObjectRole.VIEWER)
        integration_client.cookies.clear()
        token = await _login(integration_client, viewer.email)

        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

        r2 = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "bkp_code": "D01",
                "title": "Hack",
                "planned_amount_chf": "1.00",
                "scope": "shared",
            },
        )
        assert r2.status_code == 403


class TestOutsiderAndScope:
    async def test_outsider_gets_404_on_list(
        self,
        integration_client: AsyncClient,
        outsider: User,
        mfh: tuple[Object, list[Unit]],
    ) -> None:
        obj, _ = mfh
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404

    async def test_scoped_editor_sees_only_intersecting_items(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        editor: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, units = mfh
        # Owner creates one SHARED item (auto-split across all units) and one
        # UNIT-scope item attributed entirely to units[1] (1.OG).
        owner_token = await _login(integration_client, owner.email)
        shared = await _create_shared_item(
            integration_client, token=owner_token, object_id=obj.id, title="Dach"
        )

        unit_only = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(owner_token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "bkp_code": "D01",
                "title": "Bad OG",
                "planned_amount_chf": "5000.00",
                "scope": "unit",
                "allocations": [{"unit_id": str(units[1].id), "share_permille": 1000}],
            },
        )
        assert unit_only.status_code == 201, unit_only.text

        # Editor scoped to EG (units[0]) only.
        await _grant(
            db_session,
            user=editor,
            obj=obj,
            role=ObjectRole.EDITOR,
            scope_units=[units[0]],
        )
        integration_client.cookies.clear()
        ed_token = await _login(integration_client, editor.email)

        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(ed_token, integration_client),
        )
        assert r.status_code == 200
        ids = {i["id"] for i in r.json()}
        # SHARED auto-allocates across all units → editor (scoped EG) sees it.
        assert shared["id"] in ids
        # UNIT-scoped to 1.OG → editor (scoped EG) must NOT see it.
        assert unit_only.json()["id"] not in ids

    async def test_scoped_editor_blocked_from_out_of_scope_create(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        editor: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, units = mfh
        # Scope editor to EG.
        await _grant(
            db_session,
            user=editor,
            obj=obj,
            role=ObjectRole.EDITOR,
            scope_units=[units[0]],
        )
        token = await _login(integration_client, editor.email)

        # Try to attribute 100 % of a unit-scope item to 1.OG (out of scope).
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "bkp_code": "D01",
                "title": "Out of scope",
                "planned_amount_chf": "100.00",
                "scope": "unit",
                "allocations": [{"unit_id": str(units[1].id), "share_permille": 1000}],
            },
        )
        assert r.status_code == 403, r.text

    async def test_scoped_editor_allowed_when_intersecting(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        editor: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, units = mfh
        await _grant(
            db_session,
            user=editor,
            obj=obj,
            role=ObjectRole.EDITOR,
            scope_units=[units[0]],
        )
        token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "bkp_code": "D01",
                "title": "EG-Bad",
                "planned_amount_chf": "3000.00",
                "scope": "unit",
                "allocations": [{"unit_id": str(units[0].id), "share_permille": 1000}],
            },
        )
        assert r.status_code == 201, r.text


class TestValidation:
    async def test_unknown_bkp_code_rejected(
        self,
        integration_client: AsyncClient,
        owner: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = mfh
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "bkp_code": "ZZZ",
                "title": "Bad code",
                "planned_amount_chf": "1.00",
                "scope": "shared",
            },
        )
        assert r.status_code == 400

    async def test_allocation_not_summing_to_1000_rejected(
        self,
        integration_client: AsyncClient,
        owner: User,
        mfh: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, units = mfh
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "bkp_code": "D01",
                "title": "Bad split",
                "planned_amount_chf": "1.00",
                "scope": "unit",
                "allocations": [{"unit_id": str(units[0].id), "share_permille": 500}],
            },
        )
        assert r.status_code == 422
