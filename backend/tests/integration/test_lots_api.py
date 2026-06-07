"""Phase 11B — API integration tests for Lots + Lot membership.

Covers:

* Lot CRUD (create, list with/without archived, get, update, archive, delete).
* ``add_cost_item_to_lot`` same-object succeeds; cross-object 422; idempotent.
* Delete lot keeps cost items intact.
* Delete cost item removes its ``lot_cost_items`` row (cascade).
* Tag assignment to lot: succeeds same-object; 422 cross-object.
* Cost-item filter ``?lot_id=X`` returns items in that lot.
* Cost-item list ``?include_lot_ids=true`` returns ``lot_ids`` populated.
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
)
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "TestPasswort-9!ABC"


# ---- Helpers ---------------------------------------------------------------


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


def _cookies(client: AsyncClient) -> dict[str, str]:
    csrf = client.cookies.get("reno_csrf")
    return {"reno_csrf": csrf} if csrf else {}


async def _seed_bkp(session: AsyncSession) -> None:
    session.add_all(
        [
            BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True),
            BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True),
        ]
    )
    await session.commit()


async def _mk_object(
    session: AsyncSession, owner: User, name: str = "Haus"
) -> tuple[Object, list[Unit]]:
    obj = Object(
        id=uuid.uuid4(),
        name=name,
        type=ObjectType.MFH,
        planning_horizon_years=30,
    )
    session.add(obj)
    await session.flush()
    units = [
        Unit(object_id=obj.id, label="EG", wertquote_permille=600),
        Unit(object_id=obj.id, label="OG", wertquote_permille=400),
    ]
    for u in units:
        session.add(u)
    session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    await session.commit()
    return obj, units


# ---- Fixtures --------------------------------------------------------------


@pytest_asyncio.fixture()
async def owner(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "owner-lot@example.ch")


@pytest_asyncio.fixture()
async def seed_bkp(db_session: AsyncSession) -> None:
    await _seed_bkp(db_session)


@pytest_asyncio.fixture()
async def obj_with_units(db_session: AsyncSession, owner: User) -> tuple[Object, list[Unit]]:
    return await _mk_object(db_session, owner)


async def _mk_cost_item(
    client: AsyncClient, token: str, object_id: uuid.UUID, title: str = "Item"
) -> dict:
    r = await client.post(
        f"/api/v1/objects/{object_id}/cost-items",
        headers=_auth(token, client),
        cookies=_cookies(client),
        json={
            "bkp_code": "D01",
            "title": title,
            "planned_amount_chf": "100.00",
            "scope": "shared",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---- Lot CRUD --------------------------------------------------------------


class TestLotCrud:
    async def test_full_lifecycle(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        # Create
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/lots",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"name": "Sanitär-Paket", "status": "draft"},
        )
        assert r.status_code == 201, r.text
        lot_id = r.json()["id"]
        assert r.json()["name"] == "Sanitär-Paket"
        assert r.json()["cost_item_count"] == 0

        # List (no archived)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/lots",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert any(p["id"] == lot_id for p in r.json())

        # Get
        r = await integration_client.get(
            f"/api/v1/lots/{lot_id}",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200

        # Update
        r = await integration_client.patch(
            f"/api/v1/lots/{lot_id}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"status": "tendering", "description": "Test"},
        )
        assert r.status_code == 200
        assert r.json()["status"] == "tendering"
        assert r.json()["description"] == "Test"

        # Archive
        r = await integration_client.post(
            f"/api/v1/lots/{lot_id}/archive",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 200
        assert r.json()["archived_at"] is not None

        # Not in default list
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/lots",
            headers=_auth(token, integration_client),
        )
        assert not any(p["id"] == lot_id for p in r.json())

        # In archived list
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/lots?include_archived=true",
            headers=_auth(token, integration_client),
        )
        assert any(p["id"] == lot_id for p in r.json())

        # Delete
        r = await integration_client.delete(
            f"/api/v1/lots/{lot_id}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 204


# ---- Membership ------------------------------------------------------------


class TestLotMembership:
    async def test_add_same_object_succeeds_and_is_idempotent(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L"},
            )
        ).json()
        item = await _mk_cost_item(integration_client, token, obj.id)

        r = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"cost_item_id": item["id"]},
        )
        assert r.status_code == 201, r.text

        # Idempotent: second call also succeeds (201, no error).
        r2 = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"cost_item_id": item["id"]},
        )
        assert r2.status_code == 201, r2.text

        # Get lot returns count = 1 and cost_item_ids contains it.
        r = await integration_client.get(
            f"/api/v1/lots/{lot['id']}",
            headers=_auth(token, integration_client),
        )
        assert r.json()["cost_item_count"] == 1
        assert item["id"] in r.json()["cost_item_ids"]

        # List members.
        r = await integration_client.get(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert any(i["id"] == item["id"] for i in r.json())

        # Remove member.
        r = await integration_client.delete(
            f"/api/v1/lots/{lot['id']}/cost-items/{item['id']}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 204

    async def test_add_cross_object_rejected(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj1, _ = obj_with_units
        obj2, _ = await _mk_object(db_session, owner, name="Haus 2")
        token = await _login(integration_client, owner.email)

        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj1.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L1"},
            )
        ).json()
        item_obj2 = await _mk_cost_item(integration_client, token, obj2.id, title="ItemObj2")

        r = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"cost_item_id": item_obj2["id"]},
        )
        assert r.status_code == 422, r.text

    async def test_delete_lot_keeps_cost_items(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L"},
            )
        ).json()
        item = await _mk_cost_item(integration_client, token, obj.id)
        await integration_client.post(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"cost_item_id": item["id"]},
        )
        # Delete lot
        r = await integration_client.delete(
            f"/api/v1/lots/{lot['id']}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 204

        # Cost item still exists
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items/{item['id']}",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200

    async def test_delete_cost_item_cascades_membership(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L"},
            )
        ).json()
        item = await _mk_cost_item(integration_client, token, obj.id)
        await integration_client.post(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"cost_item_id": item["id"]},
        )

        # Delete the cost item
        r = await integration_client.delete(
            f"/api/v1/objects/{obj.id}/cost-items/{item['id']}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 204

        # Lot now has 0 members
        r = await integration_client.get(
            f"/api/v1/lots/{lot['id']}",
            headers=_auth(token, integration_client),
        )
        assert r.json()["cost_item_count"] == 0


# ---- Tag-on-lot ------------------------------------------------------------


class TestTagOnLot:
    async def test_assign_tag_to_lot(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        tag = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/tags",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"key": "trade", "value": "sanitär"},
            )
        ).json()
        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "Sanitär"},
            )
        ).json()

        r = await integration_client.post(
            f"/api/v1/tags/{tag['id']}/assignments",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"target_type": "lot", "target_id": lot["id"]},
        )
        assert r.status_code == 201, r.text

        # List tags for lot
        r = await integration_client.get(
            f"/api/v1/lot/{lot['id']}/tags",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert len(r.json()) == 1

    async def test_cross_object_tag_on_lot_rejected(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
    ) -> None:
        obj1, _ = obj_with_units
        obj2, _ = await _mk_object(db_session, owner, name="Haus 2")
        token = await _login(integration_client, owner.email)

        tag = (
            await integration_client.post(
                f"/api/v1/objects/{obj1.id}/tags",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"key": "k", "value": "v"},
            )
        ).json()
        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj2.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L"},
            )
        ).json()

        r = await integration_client.post(
            f"/api/v1/tags/{tag['id']}/assignments",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"target_type": "lot", "target_id": lot["id"]},
        )
        assert r.status_code == 422


# ---- Cost-item filter + include flag ---------------------------------------


class TestCostItemLotFilter:
    async def test_filter_by_lot_id(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        lot = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L"},
            )
        ).json()
        in_lot = await _mk_cost_item(integration_client, token, obj.id, title="InLot")
        not_in_lot = await _mk_cost_item(integration_client, token, obj.id, title="NotInLot")
        await integration_client.post(
            f"/api/v1/lots/{lot['id']}/cost-items",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"cost_item_id": in_lot["id"]},
        )

        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items?lot_id={lot['id']}",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        ids = {i["id"] for i in r.json()}
        assert in_lot["id"] in ids
        assert not_in_lot["id"] not in ids

    async def test_include_lot_ids_returns_lot_ids(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj_with_units: tuple[Object, list[Unit]],
        seed_bkp: None,
    ) -> None:
        obj, _ = obj_with_units
        token = await _login(integration_client, owner.email)

        lot1 = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L1"},
            )
        ).json()
        lot2 = (
            await integration_client.post(
                f"/api/v1/objects/{obj.id}/lots",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"name": "L2"},
            )
        ).json()
        item = await _mk_cost_item(integration_client, token, obj.id, title="Multi")
        other = await _mk_cost_item(integration_client, token, obj.id, title="Other")
        for lot in (lot1, lot2):
            await integration_client.post(
                f"/api/v1/lots/{lot['id']}/cost-items",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
                json={"cost_item_id": item["id"]},
            )

        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/cost-items?include_lot_ids=true",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        by_id = {i["id"]: i for i in r.json()}
        assert set(by_id[item["id"]]["lot_ids"]) == {lot1["id"], lot2["id"]}
        assert by_id[other["id"]]["lot_ids"] == []
