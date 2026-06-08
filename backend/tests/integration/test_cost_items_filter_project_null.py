"""Tests for the ``project_id_is_null`` filter on the cost-items list endpoint."""

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


async def _mk_object(session: AsyncSession, owner: User) -> Object:
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.MFH,
        planning_horizon_years=30,
    )
    session.add(obj)
    await session.flush()
    session.add(Unit(object_id=obj.id, label="EG", wertquote_permille=600))
    session.add(Unit(object_id=obj.id, label="OG", wertquote_permille=400))
    session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    await session.commit()
    return obj


@pytest_asyncio.fixture()
async def owner(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "owner-pinull@example.ch")


@pytest_asyncio.fixture()
async def seed_bkp(db_session: AsyncSession) -> None:
    await _seed_bkp(db_session)


@pytest_asyncio.fixture()
async def obj(db_session: AsyncSession, owner: User) -> Object:
    return await _mk_object(db_session, owner)


async def _seed_items(
    client: AsyncClient, token: str, object_id: uuid.UUID
) -> tuple[str, str, str]:
    """Create a project and three cost items: one linked, two unlinked."""
    p_resp = await client.post(
        f"/api/v1/objects/{object_id}/projects",
        headers=_auth(token, client),
        cookies=_cookies(client),
        json={"name": "Bad-Sanierung", "status": "idea"},
    )
    assert p_resp.status_code == 201, p_resp.text
    project_id = p_resp.json()["id"]

    async def _mk(title: str, project: str | None) -> str:
        r = await client.post(
            f"/api/v1/objects/{object_id}/cost-items",
            headers=_auth(token, client),
            cookies=_cookies(client),
            json={
                "bkp_code": "D01",
                "title": title,
                "planned_amount_chf": "100.00",
                "scope": "shared",
                "project_id": project,
            },
        )
        assert r.status_code == 201, r.text
        return r.json()["id"]

    assigned = await _mk("Linked item", project_id)
    free_a = await _mk("Free A", None)
    free_b = await _mk("Free B", None)
    return assigned, free_a, free_b


async def test_filter_only_unassigned_returns_null_project_items(
    integration_client: AsyncClient,
    owner: User,
    obj: Object,
    seed_bkp: None,
) -> None:
    token = await _login(integration_client, owner.email)
    assigned, free_a, free_b = await _seed_items(integration_client, token, obj.id)
    r = await integration_client.get(
        f"/api/v1/objects/{obj.id}/cost-items",
        headers=_auth(token, integration_client),
        params={"project_id_is_null": "true"},
    )
    assert r.status_code == 200, r.text
    ids = {row["id"] for row in r.json()}
    assert assigned not in ids
    assert {free_a, free_b}.issubset(ids)


async def test_filter_rejects_both_project_id_and_null_flag(
    integration_client: AsyncClient,
    owner: User,
    obj: Object,
    seed_bkp: None,
) -> None:
    token = await _login(integration_client, owner.email)
    r = await integration_client.get(
        f"/api/v1/objects/{obj.id}/cost-items",
        headers=_auth(token, integration_client),
        params={
            "project_id": str(uuid.uuid4()),
            "project_id_is_null": "true",
        },
    )
    assert r.status_code == 422, r.text
