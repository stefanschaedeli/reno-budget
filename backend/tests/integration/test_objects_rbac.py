"""End-to-end tests for Phase 2: objects, units, memberships, RBAC matrix.

The matrix we exercise:

    role x scope x action
    -----   -----   -------
    owner   N/A     create / update / delete object, units, members
    editor  unscoped read all units; write blocked by Phase 3 (no cost items yet)
    editor  scoped  reads only scoped units
    viewer  scoped  reads only scoped units; cannot create objects? (can)
    none    —       404 on object detail (no membership leak)

Phase 3 will extend this matrix to cost items (read/write per scope). For
Phase 2 the asserts focus on visibility, role enforcement on owner-only
mutations, and the "last-owner" guard.
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.core.security import hash_password
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


# ---- Fixtures ---------------------------------------------------------------


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
    """Return ``Authorization`` + ``X-CSRF-Token`` headers from the client jar."""
    headers = {"Authorization": f"Bearer {token}"}
    csrf = client.cookies.get("reno_csrf")
    if csrf:
        headers["X-CSRF-Token"] = csrf
    return headers


def _csrf_cookies(client: AsyncClient) -> dict[str, str]:
    """Reflect the CSRF cookie back on requests.

    Cookies set with ``Secure=True`` by the API are stored in the httpx jar
    but not auto-sent over the ``http://test`` base URL the ASGI transport
    uses. We forward the CSRF cookie explicitly on state-changing requests so
    the double-submit check has both halves.
    """
    csrf = client.cookies.get("reno_csrf")
    return {"reno_csrf": csrf} if csrf else {}


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
async def mfh_object(db_session: AsyncSession, owner: User) -> Object:
    """A pre-seeded MFH with three units and one OWNER membership."""
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
    return obj


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


# ---- Test classes -----------------------------------------------------------


class TestObjectCreation:
    async def test_create_sfh_requires_single_1000_unit(
        self, integration_client: AsyncClient, owner: User
    ) -> None:
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            "/api/v1/objects",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "name": "Mein Haus",
                "type": "sfh",
                "units": [
                    {"label": "EG", "wertquote_permille": 600},
                    {"label": "OG", "wertquote_permille": 400},
                ],
            },
        )
        assert r.status_code == 422, r.text

    async def test_create_mfh_makes_caller_owner(
        self, integration_client: AsyncClient, owner: User
    ) -> None:
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            "/api/v1/objects",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "name": "Haus Linde",
                "type": "mfh",
                "units": [
                    {"label": "A", "wertquote_permille": 500},
                    {"label": "B", "wertquote_permille": 500},
                ],
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["type"] == "mfh"
        assert len(body["units"]) == 2
        # Owner can see it in list
        r2 = await integration_client.get(
            "/api/v1/objects", headers=_auth(token, integration_client)
        )
        assert any(o["id"] == body["id"] for o in r2.json())

    async def test_wertquoten_must_sum_to_1000(
        self, integration_client: AsyncClient, owner: User
    ) -> None:
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            "/api/v1/objects",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "name": "Schiefes Haus",
                "type": "mfh",
                "units": [
                    {"label": "A", "wertquote_permille": 400},
                    {"label": "B", "wertquote_permille": 400},
                ],
            },
        )
        assert r.status_code == 422, r.text


class TestAccessControl:
    async def test_outsider_gets_404_on_detail(
        self,
        integration_client: AsyncClient,
        outsider: User,
        mfh_object: Object,
    ) -> None:
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{mfh_object.id}",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404

    async def test_viewer_cannot_mutate(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        viewer: User,
        mfh_object: Object,
    ) -> None:
        await _grant(db_session, user=viewer, obj=mfh_object, role=ObjectRole.VIEWER)
        token = await _login(integration_client, viewer.email)
        r = await integration_client.patch(
            f"/api/v1/objects/{mfh_object.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={"name": "Hacked"},
        )
        assert r.status_code == 403

    async def test_editor_cannot_delete_object(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        editor: User,
        mfh_object: Object,
    ) -> None:
        await _grant(db_session, user=editor, obj=mfh_object, role=ObjectRole.EDITOR)
        token = await _login(integration_client, editor.email)
        r = await integration_client.delete(
            f"/api/v1/objects/{mfh_object.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r.status_code == 403


class TestUnitScopeVisibility:
    async def test_scoped_viewer_sees_only_their_units(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        viewer: User,
        mfh_object: Object,
    ) -> None:
        # Scope viewer to the first unit only.
        from sqlalchemy import select

        units = (
            (await db_session.execute(select(Unit).where(Unit.object_id == mfh_object.id)))
            .scalars()
            .all()
        )
        scoped_unit = units[0]
        await _grant(
            db_session,
            user=viewer,
            obj=mfh_object,
            role=ObjectRole.VIEWER,
            scope_units=[scoped_unit],
        )
        token = await _login(integration_client, viewer.email)
        r = await integration_client.get(
            f"/api/v1/objects/{mfh_object.id}/units",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        ids = [u["id"] for u in r.json()]
        assert ids == [str(scoped_unit.id)]

    async def test_owner_sees_all_units_regardless_of_scope_rows(
        self,
        integration_client: AsyncClient,
        owner: User,
        mfh_object: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            f"/api/v1/objects/{mfh_object.id}/units",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200
        assert len(r.json()) == 3


class TestMembershipMutations:
    async def test_owner_can_invite_editor_and_invitee_joins(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        mfh_object: Object,
    ) -> None:
        from app.services import mailer as mailer_module

        mailer_module.SENT.clear()

        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            f"/api/v1/objects/{mfh_object.id}/invitations",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            json={
                "email": "neuer@example.ch",
                "role": "editor",
                "scope_unit_ids": [],
            },
        )
        assert r.status_code == 201, r.text
        invite_token = r.json()["token"]
        assert invite_token

        # Accept invitation
        r2 = await integration_client.post(
            "/api/v1/auth/invitations/accept",
            json={
                "token": invite_token,
                "display_name": "Neuer Editor",
                "password": PW,
            },
        )
        assert r2.status_code == 200, r2.text

        # Logout owner, log in as new editor, list objects
        integration_client.cookies.clear()
        editor_token = await _login(integration_client, "neuer@example.ch")
        r3 = await integration_client.get(
            "/api/v1/objects", headers=_auth(editor_token, integration_client)
        )
        assert any(o["id"] == str(mfh_object.id) for o in r3.json())

    async def test_cannot_remove_last_owner(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        mfh_object: Object,
    ) -> None:
        token = await _login(integration_client, owner.email)
        r = await integration_client.delete(
            f"/api/v1/objects/{mfh_object.id}/members/{owner.id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r.status_code == 409
