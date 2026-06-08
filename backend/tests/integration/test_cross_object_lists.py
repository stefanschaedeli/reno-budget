"""Cross-object list endpoints (PR 2).

Covers ``GET /api/v1/projects``, ``GET /api/v1/lots``, ``GET /api/v1/suppliers`` —
one row per resource across every object the calling user has access to.
"""

from __future__ import annotations

import datetime as _dt
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
)
from app.models.project import Project, ProjectStatus
from app.models.supplier import Supplier
from app.models.user import User
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "horse-battery-staple-correct-9"  # nosec B105


async def _mk_user(session: AsyncSession, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        password_hash=hash_password(PW),
        display_name=email.split("@")[0],
        is_active=True,
    )
    session.add(u)
    await session.commit()
    return u


async def _mk_object_with_owner(
    session: AsyncSession, owner: User, name: str
) -> Object:
    obj = Object(
        id=uuid.uuid4(),
        name=name,
        type=ObjectType.MFH,
        planning_horizon_years=30,
    )
    session.add(obj)
    session.add(
        ObjectMembership(
            user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER
        )
    )
    await session.commit()
    return obj


async def _login(client: AsyncClient, email: str) -> str:
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PW},
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest_asyncio.fixture
async def two_users_two_objects(db_session: AsyncSession):
    """Owner-Alice with Object-A; Owner-Bob with Object-B."""
    alice = await _mk_user(db_session, "alice@example.com")
    bob = await _mk_user(db_session, "bob@example.com")
    obj_a = await _mk_object_with_owner(db_session, alice, "Haus A")
    obj_b = await _mk_object_with_owner(db_session, bob, "Haus B")
    return alice, bob, obj_a, obj_b


@pytest.mark.asyncio
async def test_projects_cross_list_only_my_objects(
    two_users_two_objects, db_session: AsyncSession, integration_client: AsyncClient
):
    alice, bob, obj_a, obj_b = two_users_two_objects
    p_a = Project(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Dach A",
        status=ProjectStatus.PLANNED,
        created_by=alice.id,
    )
    p_b = Project(
        id=uuid.uuid4(),
        object_id=obj_b.id,
        name="Dach B",
        status=ProjectStatus.PLANNED,
        created_by=bob.id,
    )
    db_session.add_all([p_a, p_b])
    await db_session.commit()

    token = await _login(integration_client, alice.email)
    r = await integration_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(p_a.id)
    assert rows[0]["object_id"] == str(obj_a.id)
    assert rows[0]["object_name"] == "Haus A"


@pytest.mark.asyncio
async def test_projects_cross_list_excludes_archived(
    two_users_two_objects, db_session: AsyncSession, integration_client: AsyncClient
):
    alice, _, obj_a, _ = two_users_two_objects
    active = Project(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Aktiv",
        status=ProjectStatus.PLANNED,
        created_by=alice.id,
    )
    archived = Project(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Archiviert",
        status=ProjectStatus.PLANNED,
        created_by=alice.id,
        archived_at=_dt.datetime.now(_dt.timezone.utc),
    )
    db_session.add_all([active, archived])
    await db_session.commit()

    token = await _login(integration_client, alice.email)
    r = await integration_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    names = [row["name"] for row in r.json()]
    assert names == ["Aktiv"]


@pytest.mark.asyncio
async def test_projects_cross_list_empty(
    two_users_two_objects, integration_client: AsyncClient
):
    alice, _, _, _ = two_users_two_objects
    token = await _login(integration_client, alice.email)
    r = await integration_client.get(
        "/api/v1/projects", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_lots_cross_list_only_my_objects(
    two_users_two_objects, db_session: AsyncSession, integration_client: AsyncClient
):
    alice, bob, obj_a, obj_b = two_users_two_objects
    l_a = Lot(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Los A",
        status=LotStatus.DRAFT,
        created_by=alice.id,
    )
    l_b = Lot(
        id=uuid.uuid4(),
        object_id=obj_b.id,
        name="Los B",
        status=LotStatus.DRAFT,
        created_by=bob.id,
    )
    db_session.add_all([l_a, l_b])
    await db_session.commit()

    token = await _login(integration_client, alice.email)
    r = await integration_client.get(
        "/api/v1/lots", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(l_a.id)
    assert rows[0]["object_name"] == "Haus A"


@pytest.mark.asyncio
async def test_suppliers_cross_list_only_my_objects(
    two_users_two_objects, db_session: AsyncSession, integration_client: AsyncClient
):
    alice, bob, obj_a, obj_b = two_users_two_objects
    s_a = Supplier(
        id=uuid.uuid4(),
        object_id=obj_a.id,
        name="Firma A",
        created_by=alice.id,
    )
    s_b = Supplier(
        id=uuid.uuid4(),
        object_id=obj_b.id,
        name="Firma B",
        created_by=bob.id,
    )
    db_session.add_all([s_a, s_b])
    await db_session.commit()

    token = await _login(integration_client, alice.email)
    r = await integration_client.get(
        "/api/v1/suppliers", headers={"Authorization": f"Bearer {token}"}
    )
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["id"] == str(s_a.id)
    assert rows[0]["object_name"] == "Haus A"
