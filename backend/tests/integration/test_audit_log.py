"""Audit log integration tests (Phase 7).

Covers two concerns:

1. **Write-hooks.** Performing real mutations (login, create cost item,
   upload attachment, grant membership) writes an ``AuditEvent`` row with
   the expected ``action``, ``actor_email`` and (when applicable)
   ``object_id``.
2. **Read API.** Owner / editor / viewer / outsider / superuser see the
   correct subsets; keyset pagination returns stable, distinct pages.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.audit import AuditEvent
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
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "TestPasswort-9!ABC"

# Minimal valid 1x1 PNG body (matches the constant used in
# test_attachments_rbac.py so libmagic accepts it via the allowlist).
PNG_BODY = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


@pytest.fixture(autouse=True)
def _uploads_tmp(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[Path]:
    monkeypatch.setenv("RENO_UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


# ---- Helpers (mirror style of test_cost_items_rbac.py) ----------------------


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


# ---- Fixtures ---------------------------------------------------------------


@pytest_asyncio.fixture()
async def owner(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "owner@audit.ch")


@pytest_asyncio.fixture()
async def editor(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "editor@audit.ch")


@pytest_asyncio.fixture()
async def viewer(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "viewer@audit.ch")


@pytest_asyncio.fixture()
async def outsider(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "outsider@audit.ch")


@pytest_asyncio.fixture()
async def admin(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "admin@audit.ch", super_=True)


@pytest_asyncio.fixture()
async def seed_bkp(db_session: AsyncSession) -> None:
    db_session.add(BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True))
    db_session.add(BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True))
    await db_session.commit()


@pytest_asyncio.fixture()
async def sfh(
    db_session: AsyncSession, owner: User, editor: User, viewer: User
) -> tuple[Object, Unit]:
    """SFH with one implicit unit and an OWNER + EDITOR + VIEWER membership."""
    obj = Object(
        id=uuid.uuid4(),
        name="Haus Audit",
        type=ObjectType.SFH,
        planning_horizon_years=30,
    )
    db_session.add(obj)
    await db_session.flush()
    unit = Unit(object_id=obj.id, label="Ganzes Haus", wertquote_permille=1000)
    db_session.add(unit)
    db_session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    db_session.add(ObjectMembership(user_id=editor.id, object_id=obj.id, role=ObjectRole.EDITOR))
    db_session.add(ObjectMembership(user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER))
    await db_session.commit()
    return obj, unit


# ---- 1. Write-hooks ---------------------------------------------------------


class TestWriteHooks:
    async def test_login_writes_event(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
    ) -> None:
        r = await integration_client.post(
            "/api/v1/auth/login", json={"email": owner.email, "password": PW}
        )
        assert r.status_code == 200, r.text

        rows = (
            (
                await db_session.execute(
                    select(AuditEvent).where(AuditEvent.action == "auth.login")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].actor_user_id == owner.id
        assert rows[0].actor_email == owner.email
        assert rows[0].target_id == owner.id

    async def test_create_cost_item_writes_event(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        sfh: tuple[Object, Unit],
        seed_bkp: None,
    ) -> None:
        obj, _unit = sfh
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/cost-items",
            json={
                "bkp_code": "D01",
                "title": "Heizung erneuern",
                "scope": "shared",
                "planned_amount_chf": "5000.00",
            },
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r.status_code == 201, r.text

        rows = (
            (
                await db_session.execute(
                    select(AuditEvent).where(AuditEvent.action == "cost_item.create")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].object_id == obj.id
        assert rows[0].actor_user_id == owner.id
        assert rows[0].target_type == "cost_item"
        assert "Heizung erneuern" in rows[0].summary

    async def test_upload_attachment_writes_event(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        token = await _login(integration_client, owner.email)
        files = {"file": ("pic.png", io.BytesIO(PNG_BODY), "image/png")}
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/attachments",
            files=files,
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r.status_code == 201, r.text
        rows = (
            (
                await db_session.execute(
                    select(AuditEvent).where(AuditEvent.action == "attachment.upload")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].object_id == obj.id
        assert rows[0].actor_user_id == owner.id
        assert "pic.png" in rows[0].summary

    async def test_membership_grant_via_invitation_writes_event(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        token = await _login(integration_client, owner.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/invitations",
            json={"email": "newmember@audit.ch", "role": "editor"},
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r.status_code == 201, r.text

        rows = (
            (
                await db_session.execute(
                    select(AuditEvent).where(AuditEvent.action == "membership.grant")
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].object_id == obj.id
        assert "newmember@audit.ch" in rows[0].summary


# ---- 2. Read API ------------------------------------------------------------


async def _seed_events(
    session: AsyncSession,
    actor: User,
    object_id: uuid.UUID | None,
    n: int,
    base_action: str = "cost_item.create",
) -> list[AuditEvent]:
    """Insert ``n`` events with strictly increasing ``created_at``."""
    base = datetime.now(tz=UTC) - timedelta(minutes=n)
    rows: list[AuditEvent] = []
    for i in range(n):
        ev = AuditEvent(
            actor_user_id=actor.id,
            actor_email=actor.email,
            action=base_action,
            object_id=object_id,
            target_type="cost_item",
            target_id=uuid.uuid4(),
            summary=f"event #{i}",
            created_at=base + timedelta(seconds=i),
        )
        session.add(ev)
        rows.append(ev)
    await session.commit()
    return rows


class TestReadApi:
    async def test_owner_sees_object_events(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        await _seed_events(db_session, owner, obj.id, n=3)
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/audit",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # auth.login has object_id=None and so is NOT in the object feed.
        actions = [e["action"] for e in body["items"]]
        assert actions.count("cost_item.create") == 3
        for ev in body["items"]:
            assert ev["object_id"] == str(obj.id)

    async def test_editor_gets_403(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        editor: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        token = await _login(integration_client, editor.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/audit",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 403, r.text

    async def test_viewer_gets_403(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        viewer: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        token = await _login(integration_client, viewer.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/audit",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 403, r.text

    async def test_outsider_gets_404(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        outsider: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/audit",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404, r.text

    async def test_global_feed_requires_superuser(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        admin: User,
    ) -> None:
        await _seed_events(db_session, owner, None, n=2, base_action="auth.login")

        # Non-admin → 403.
        token = await _login(integration_client, owner.email)
        r = await integration_client.get(
            "/api/v1/audit",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 403, r.text

        # Admin → 200, sees seeded events.
        admin_tok = await _login(integration_client, admin.email)
        r = await integration_client.get(
            "/api/v1/audit",
            headers=_auth(admin_tok, integration_client),
        )
        assert r.status_code == 200, r.text
        assert len(r.json()["items"]) >= 2

    async def test_pagination_returns_distinct_pages(
        self,
        integration_client: AsyncClient,
        db_session: AsyncSession,
        owner: User,
        sfh: tuple[Object, Unit],
    ) -> None:
        obj, _ = sfh
        await _seed_events(db_session, owner, obj.id, n=8)
        token = await _login(integration_client, owner.email)

        r1 = await integration_client.get(
            f"/api/v1/objects/{obj.id}/audit",
            params={"limit": 3},
            headers=_auth(token, integration_client),
        )
        assert r1.status_code == 200, r1.text
        page1 = r1.json()
        assert len(page1["items"]) == 3
        assert page1["next_before"] is not None

        r2 = await integration_client.get(
            f"/api/v1/objects/{obj.id}/audit",
            params={"limit": 3, "before": page1["next_before"]},
            headers=_auth(token, integration_client),
        )
        assert r2.status_code == 200, r2.text
        page2 = r2.json()
        assert len(page2["items"]) == 3

        ids1 = {e["id"] for e in page1["items"]}
        ids2 = {e["id"] for e in page2["items"]}
        assert ids1.isdisjoint(ids2), "pages must not overlap"

    async def test_global_feed_invalid_cursor_400(
        self,
        integration_client: AsyncClient,
        admin: User,
    ) -> None:
        admin_tok = await _login(integration_client, admin.email)
        r = await integration_client.get(
            "/api/v1/audit?before=not-a-date",
            headers=_auth(admin_tok, integration_client),
        )
        assert r.status_code == 400, r.text
