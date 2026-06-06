"""End-to-end RBAC matrix for attachments (Phase 6).

Covers the upload / list / download / delete endpoints across the standard
RBAC bands (owner / editor / viewer / outsider) for both target types
(cost item, object). The storage root is redirected to a per-test tmpdir so
blobs don't leak between tests.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.cost import BkpCode, CostItem, CostItemPriority, CostItemScope, CostItemStatus
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
PDF_BODY = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"
PNG_BODY = (
    # Minimal valid 1x1 PNG.
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


# ---- helpers (mirroring test_cost_items_rbac.py) ---------------------------


async def _mk_user(session: AsyncSession, email: str) -> User:
    u = User(
        id=uuid.uuid4(),
        email=email,
        display_name=email.split("@")[0],
        password_hash=hash_password(PW),
        is_active=True,
        is_superuser=False,
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
async def setup(
    db_session: AsyncSession, owner: User, editor: User, viewer: User
) -> tuple[Object, CostItem]:
    obj = Object(
        id=uuid.uuid4(),
        name="Haus",
        type=ObjectType.SFH,
        planning_horizon_years=30,
    )
    db_session.add(obj)
    await db_session.flush()
    db_session.add(Unit(object_id=obj.id, label="Ganzes Haus", wertquote_permille=1000))
    db_session.add(BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True))
    db_session.add(BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True))
    db_session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    db_session.add(ObjectMembership(user_id=editor.id, object_id=obj.id, role=ObjectRole.EDITOR))
    db_session.add(ObjectMembership(user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER))
    ci = CostItem(
        object_id=obj.id,
        bkp_code="D01",
        title="Heizung",
        planned_amount_chf=10000,  # type: ignore[arg-type]
        status=CostItemStatus.PLANNED,
        priority=CostItemPriority.MED,
        scope=CostItemScope.SHARED,
    )
    db_session.add(ci)
    await db_session.commit()
    return obj, ci


def _pdf_file() -> dict[str, tuple[str, bytes, str]]:
    # Note: the second tuple element is what FastAPI surfaces as the
    # Content-Type. We deliberately mis-set it to "text/plain" in the
    # mime-spoof test below to prove server-side sniffing rejects it.
    return {"file": ("offer.pdf", PDF_BODY, "application/pdf")}


# ---- Cost-item attachments --------------------------------------------------


class TestCostItemAttachments:
    async def test_editor_upload_and_viewer_list_and_download(
        self,
        integration_client: AsyncClient,
        owner: User,
        editor: User,
        viewer: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        _, ci = setup
        # Editor uploads.
        ed_token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(ed_token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files=_pdf_file(),
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["mime"] == "application/pdf"
        assert body["filename"] == "offer.pdf"
        assert body["size_bytes"] == len(PDF_BODY)
        att_id = body["id"]

        # Viewer lists + downloads.
        integration_client.cookies.clear()
        v_token = await _login(integration_client, viewer.email)
        r2 = await integration_client.get(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(v_token, integration_client),
        )
        assert r2.status_code == 200
        assert [a["id"] for a in r2.json()] == [att_id]

        r3 = await integration_client.get(
            f"/api/v1/attachments/{att_id}/download",
            headers=_auth(v_token, integration_client),
        )
        assert r3.status_code == 200
        assert r3.content == PDF_BODY
        assert r3.headers["content-security-policy"] == "default-src 'none'"
        assert r3.headers["x-content-type-options"] == "nosniff"
        assert "attachment" in r3.headers["content-disposition"].lower()

    async def test_viewer_cannot_upload(
        self,
        integration_client: AsyncClient,
        viewer: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        _, ci = setup
        token = await _login(integration_client, viewer.email)
        r = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files=_pdf_file(),
        )
        assert r.status_code == 403, r.text

    async def test_outsider_blocked_everywhere(
        self,
        integration_client: AsyncClient,
        outsider: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        _, ci = setup
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404
        r2 = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files=_pdf_file(),
        )
        assert r2.status_code == 404

    async def test_uploader_can_delete_own(
        self,
        integration_client: AsyncClient,
        editor: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        _, ci = setup
        token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files=_pdf_file(),
        )
        att_id = r.json()["id"]
        r2 = await integration_client.delete(
            f"/api/v1/attachments/{att_id}",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r2.status_code == 204

    async def test_viewer_cannot_delete_others_attachment(
        self,
        integration_client: AsyncClient,
        editor: User,
        viewer: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        _, ci = setup
        # Editor uploads.
        ed_token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(ed_token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files=_pdf_file(),
        )
        att_id = r.json()["id"]
        # Viewer tries to delete.
        integration_client.cookies.clear()
        v_token = await _login(integration_client, viewer.email)
        r2 = await integration_client.delete(
            f"/api/v1/attachments/{att_id}",
            headers=_auth(v_token, integration_client),
            cookies=_csrf_cookies(integration_client),
        )
        assert r2.status_code == 403


# ---- Object attachments -----------------------------------------------------


class TestObjectAttachments:
    async def test_editor_uploads_object_attachment(
        self,
        integration_client: AsyncClient,
        editor: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        obj, _ = setup
        token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/objects/{obj.id}/attachments",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files={"file": ("photo.png", PNG_BODY, "image/png")},
        )
        assert r.status_code == 201, r.text
        assert r.json()["mime"] == "image/png"

    async def test_outsider_cannot_list_object_attachments(
        self,
        integration_client: AsyncClient,
        outsider: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        obj, _ = setup
        token = await _login(integration_client, outsider.email)
        r = await integration_client.get(
            f"/api/v1/objects/{obj.id}/attachments",
            headers=_auth(token, integration_client),
        )
        assert r.status_code == 404


# ---- Validation -------------------------------------------------------------


class TestValidation:
    async def test_mime_spoof_rejected(
        self,
        integration_client: AsyncClient,
        editor: User,
        setup: tuple[Object, CostItem],
    ) -> None:
        _, ci = setup
        token = await _login(integration_client, editor.email)
        # Plain text body with a PDF filename and a PDF Content-Type — must fail
        # because we sniff the *bytes*, not the client header.
        r = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files={"file": ("evil.pdf", b"plain text not pdf", "application/pdf")},
        )
        assert r.status_code == 415, r.text

    async def test_oversize_rejected(
        self,
        integration_client: AsyncClient,
        editor: User,
        setup: tuple[Object, CostItem],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        _, ci = setup
        monkeypatch.setenv("RENO_UPLOAD_MAX_BYTES", "10")
        get_settings.cache_clear()
        token = await _login(integration_client, editor.email)
        r = await integration_client.post(
            f"/api/v1/cost-items/{ci.id}/attachments",
            headers=_auth(token, integration_client),
            cookies=_csrf_cookies(integration_client),
            files=_pdf_file(),
        )
        assert r.status_code == 413, r.text
