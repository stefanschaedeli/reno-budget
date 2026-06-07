"""Phase 11C — API integration tests for Suppliers + Quotes + Award.

Covers:

* Supplier CRUD (create, list, get, update, archive, delete).
* Quote create: same-object lot+supplier succeeds; cross-object 422.
* Quote list by lot.
* Award transaction: sets quote.status=awarded, lot.awarded_quote_id and
  lot.status=awarded — all visible after a single commit.
* Award idempotency: awarding the same quote twice is a no-op.
* Award conflict: awarding a second quote on the same lot returns 409
  (partial unique index ``uq_quotes_one_awarded_per_lot``).
* Delete RESTRICT: cannot delete the awarded quote while the lot still
  references it (HTTP 409).
* Supplier RESTRICT: cannot delete a supplier with any referenced quote
  (HTTP 409).
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.models.lot import Lot, LotStatus
from app.models.object import (
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
)
from app.models.quote import Quote, QuoteStatus
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


async def _mk_object(
    session: AsyncSession, owner: User, name: str = "Haus"
) -> Object:
    obj = Object(
        id=uuid.uuid4(),
        name=name,
        type=ObjectType.MFH,
        planning_horizon_years=30,
    )
    session.add(obj)
    await session.flush()
    session.add(Unit(object_id=obj.id, label="EG", wertquote_permille=1000))
    session.add(
        ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER)
    )
    await session.commit()
    return obj


async def _mk_lot(
    client: AsyncClient, token: str, object_id: uuid.UUID, name: str = "Sanitär"
) -> dict:
    r = await client.post(
        f"/api/v1/objects/{object_id}/lots",
        headers=_auth(token, client),
        cookies=_cookies(client),
        json={"name": name, "status": "tendering"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_supplier(
    client: AsyncClient, token: str, object_id: uuid.UUID, name: str = "Acme AG"
) -> dict:
    r = await client.post(
        f"/api/v1/objects/{object_id}/suppliers",
        headers=_auth(token, client),
        cookies=_cookies(client),
        json={"name": name, "contact_email": "info@acme.example"},
    )
    assert r.status_code == 201, r.text
    return r.json()


async def _mk_quote(
    client: AsyncClient,
    token: str,
    lot_id: str,
    supplier_id: str,
    amount: str = "12345.00",
) -> dict:
    r = await client.post(
        f"/api/v1/lots/{lot_id}/quotes",
        headers=_auth(token, client),
        cookies=_cookies(client),
        json={
            "supplier_id": supplier_id,
            "amount_chf": amount,
            "received_at": "2026-06-01",
            "status": "received",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


# ---- Fixtures --------------------------------------------------------------


@pytest_asyncio.fixture()
async def owner(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "owner-proc@example.ch")


@pytest_asyncio.fixture()
async def obj(db_session: AsyncSession, owner: User) -> Object:
    return await _mk_object(db_session, owner)


# ---- Supplier CRUD ---------------------------------------------------------


class TestSupplierCrud:
    async def test_full_lifecycle(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        sup = await _mk_supplier(integration_client, token, obj.id)
        sid = sup["id"]
        assert sup["name"] == "Acme AG"

        # List
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/suppliers",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert any(s["id"] == sid for s in r.json())

        # Get
        r = await integration_client.get(
            f"/api/v1/suppliers/{sid}",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200

        # Update
        r = await integration_client.patch(
            f"/api/v1/suppliers/{sid}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={"contact_phone": "+41 44 555 11 22"},
        )
        assert r.status_code == 200
        assert r.json()["contact_phone"] == "+41 44 555 11 22"

        # Archive
        r = await integration_client.post(
            f"/api/v1/suppliers/{sid}/archive",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 200
        assert r.json()["archived_at"] is not None

        # Not in default list
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/suppliers",
            headers=_auth(token, integration_client),
        )
        assert not any(s["id"] == sid for s in r.json())

        # But visible with include_archived
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/suppliers?include_archived=true",
            headers=_auth(token, integration_client),
        )
        assert any(s["id"] == sid for s in r.json())

        # Delete (no quotes attached)
        r = await integration_client.delete(
            f"/api/v1/suppliers/{sid}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 204


# ---- Quote scope -----------------------------------------------------------


class TestQuoteCreate:
    async def test_same_object_succeeds(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        q = await _mk_quote(integration_client, token, lot["id"], sup["id"])
        assert q["status"] == "received"
        assert q["amount_chf"] == "12345.00"

    async def test_cross_object_rejected(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        obj2 = await _mk_object(db_session, owner, name="Haus 2")
        sup_other = await _mk_supplier(integration_client, token, obj2.id, name="Other")

        r = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/quotes",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
            json={
                "supplier_id": sup_other["id"],
                "amount_chf": "100.00",
                "received_at": "2026-06-01",
            },
        )
        assert r.status_code == 422, r.text

    async def test_list_by_lot(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        await _mk_quote(integration_client, token, lot["id"], sup["id"], "1000.00")
        await _mk_quote(integration_client, token, lot["id"], sup["id"], "2000.00")

        r = await integration_client.get(
            f"/api/v1/lots/{lot['id']}/quotes",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert len(r.json()) == 2


# ---- Award transaction -----------------------------------------------------


class TestAward:
    async def test_award_sets_quote_lot_atomically(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        q = await _mk_quote(integration_client, token, lot["id"], sup["id"])

        r = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/quotes/{q['id']}/award",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "awarded"

        # All three side effects visible.
        db_q = await db_session.get(Quote, uuid.UUID(q["id"]))
        db_lot = await db_session.get(Lot, uuid.UUID(lot["id"]))
        assert db_q is not None and db_lot is not None
        await db_session.refresh(db_q)
        await db_session.refresh(db_lot)
        assert db_q.status == QuoteStatus.AWARDED
        assert db_lot.awarded_quote_id == db_q.id
        assert db_lot.status == LotStatus.AWARDED

    async def test_award_is_idempotent(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        q = await _mk_quote(integration_client, token, lot["id"], sup["id"])

        for _ in range(2):
            r = await integration_client.post(
                f"/api/v1/lots/{lot['id']}/quotes/{q['id']}/award",
                headers=_auth(token, integration_client),
                cookies=_cookies(integration_client),
            )
            assert r.status_code == 200, r.text
            assert r.json()["status"] == "awarded"

    async def test_award_second_quote_conflicts_409(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        q1 = await _mk_quote(integration_client, token, lot["id"], sup["id"], "1000.00")
        q2 = await _mk_quote(integration_client, token, lot["id"], sup["id"], "2000.00")

        r = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/quotes/{q1['id']}/award",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 200

        r = await integration_client.post(
            f"/api/v1/lots/{lot['id']}/quotes/{q2['id']}/award",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 409, r.text


# ---- RESTRICT semantics ----------------------------------------------------


class TestRestrict:
    async def test_cannot_delete_awarded_quote(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        q = await _mk_quote(integration_client, token, lot["id"], sup["id"])
        await integration_client.post(
            f"/api/v1/lots/{lot['id']}/quotes/{q['id']}/award",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )

        r = await integration_client.delete(
            f"/api/v1/quotes/{q['id']}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 409, r.text

    async def test_cannot_delete_supplier_with_quotes(
        self,
        integration_client: AsyncClient,
        owner: User,
        obj: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        lot = await _mk_lot(integration_client, token, obj.id)
        sup = await _mk_supplier(integration_client, token, obj.id)
        await _mk_quote(integration_client, token, lot["id"], sup["id"])

        r = await integration_client.delete(
            f"/api/v1/suppliers/{sup['id']}",
            headers=_auth(token, integration_client),
            cookies=_cookies(integration_client),
        )
        assert r.status_code == 409, r.text
