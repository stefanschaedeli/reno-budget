"""Integration tests for the eBKP-H catalogue API.

Exercises read access (flat + tree) for any authenticated user and the
superuser-only custom-code creation path. The catalogue itself is seeded by
the SQLAlchemy ``create_all`` path used in the testcontainers fixture only
indirectly — we insert a minimal seed set per test to keep tests fast and
independent of the migration file's data step.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.models.cost import BkpCode
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


@pytest_asyncio.fixture()
async def _seed_codes(db_session: AsyncSession) -> None:
    """Insert a minimal eBKP-H seed (one root + two children)."""
    rows = [
        BkpCode(code="A", parent_code=None, level=1, label_de="Grundstück", is_seed=True),
        BkpCode(code="A01", parent_code="A", level=2, label_de="Erwerb", is_seed=True),
        BkpCode(code="A02", parent_code="A", level=2, label_de="Rechte", is_seed=True),
    ]
    for r in rows:
        db_session.add(r)
    await db_session.commit()


class TestCatalogueRead:
    async def test_flat_list_requires_auth(
        self, integration_client: AsyncClient, _seed_codes: None
    ) -> None:
        r = await integration_client.get("/api/v1/bkp-codes")
        assert r.status_code == 401

    async def test_flat_list_returns_seeds(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        _seed_codes: None,
    ) -> None:
        user = await _mk_user(db_session, "reader@example.ch")
        token = await _login(integration_client, user.email)
        r = await integration_client.get(
            "/api/v1/bkp-codes", headers=_auth(token, integration_client)
        )
        assert r.status_code == 200, r.text
        codes = [row["code"] for row in r.json()]
        assert codes == ["A", "A01", "A02"]

    async def test_tree_groups_children(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        _seed_codes: None,
    ) -> None:
        user = await _mk_user(db_session, "tree@example.ch")
        token = await _login(integration_client, user.email)
        r = await integration_client.get(
            "/api/v1/bkp-codes/tree", headers=_auth(token, integration_client)
        )
        assert r.status_code == 200, r.text
        roots = r.json()
        assert len(roots) == 1
        assert roots[0]["code"] == "A"
        child_codes = sorted(c["code"] for c in roots[0]["children"])
        assert child_codes == ["A01", "A02"]


class TestCustomCodeCreation:
    async def test_non_superuser_forbidden(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        _seed_codes: None,
    ) -> None:
        user = await _mk_user(db_session, "plain@example.ch")
        token = await _login(integration_client, user.email)
        r = await integration_client.post(
            "/api/v1/bkp-codes",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "code": "Z01",
                "parent_code": None,
                "level": 1,
                "label_de": "Sondergruppe",
            },
        )
        assert r.status_code == 403

    async def test_superuser_can_create(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        _seed_codes: None,
    ) -> None:
        admin = await _mk_user(db_session, "admin@example.ch", super_=True)
        token = await _login(integration_client, admin.email)
        r = await integration_client.post(
            "/api/v1/bkp-codes",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "code": "A99",
                "parent_code": "A",
                "level": 2,
                "label_de": "Sonstiges",
            },
        )
        assert r.status_code == 201, r.text
        assert r.json()["is_seed"] is False

    async def test_duplicate_code_conflict(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        _seed_codes: None,
    ) -> None:
        admin = await _mk_user(db_session, "admin2@example.ch", super_=True)
        token = await _login(integration_client, admin.email)
        r = await integration_client.post(
            "/api/v1/bkp-codes",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "code": "A",
                "parent_code": None,
                "level": 1,
                "label_de": "Dup",
            },
        )
        assert r.status_code == 409

    async def test_unknown_parent_rejected(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        _seed_codes: None,
    ) -> None:
        admin = await _mk_user(db_session, "admin3@example.ch", super_=True)
        token = await _login(integration_client, admin.email)
        r = await integration_client.post(
            "/api/v1/bkp-codes",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "code": "ZZ",
                "parent_code": "NOPE",
                "level": 2,
                "label_de": "Bad",
            },
        )
        assert r.status_code == 400
