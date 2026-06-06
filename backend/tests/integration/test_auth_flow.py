"""End-to-end auth flow tests against a real Postgres."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from app.core.security import hash_password
from app.models.user import User
from app.services import mailer as mailer_module
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

ADMIN_PW = "SuperSicher-9!ABC"


@pytest_asyncio.fixture()
async def superuser(db_session: AsyncSession) -> User:
    user = User(
        id=uuid.uuid4(),
        email="admin@example.ch",
        display_name="Admin",
        password_hash=hash_password(ADMIN_PW),
        is_active=True,
        is_superuser=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


async def _login(client: AsyncClient, email: str, password: str) -> str:
    r = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


class TestLogin:
    async def test_unknown_user_returns_401(self, integration_client: AsyncClient) -> None:
        r = await integration_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.ch", "password": "whatever12!ABC"},
        )
        assert r.status_code == 401

    async def test_login_sets_cookies(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        await _login(integration_client, "admin@example.ch", ADMIN_PW)
        assert "reno_refresh" in integration_client.cookies
        assert "reno_csrf" in integration_client.cookies

    async def test_lockout_after_repeated_failures(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        for _ in range(5):
            await integration_client.post(
                "/api/v1/auth/login",
                json={"email": "admin@example.ch", "password": "wrong"},
            )
        r = await integration_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.ch", "password": ADMIN_PW},
        )
        assert r.status_code == 423


class TestMe:
    async def test_requires_auth(self, integration_client: AsyncClient) -> None:
        r = await integration_client.get("/api/v1/auth/me")
        assert r.status_code == 401

    async def test_returns_current_user(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        access = await _login(integration_client, "admin@example.ch", ADMIN_PW)
        r = await integration_client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {access}"}
        )
        assert r.status_code == 200
        assert r.json()["email"] == "admin@example.ch"


class TestRefreshRotation:
    async def test_refresh_requires_csrf_header(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        await _login(integration_client, "admin@example.ch", ADMIN_PW)
        r = await integration_client.post("/api/v1/auth/refresh")
        assert r.status_code == 403

    async def test_refresh_rotates_cookie(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        await _login(integration_client, "admin@example.ch", ADMIN_PW)
        old = integration_client.cookies.get("reno_refresh")
        csrf = integration_client.cookies.get("reno_csrf") or ""
        r = await integration_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf},
            cookies={"reno_refresh": old or "", "reno_csrf": csrf},
        )
        assert r.status_code == 200, r.text
        new = integration_client.cookies.get("reno_refresh")
        assert new and new != old

    async def test_replay_old_refresh_revokes(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        await _login(integration_client, "admin@example.ch", ADMIN_PW)
        first = integration_client.cookies.get("reno_refresh") or ""
        csrf = integration_client.cookies.get("reno_csrf") or ""
        await integration_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf},
            cookies={"reno_refresh": first, "reno_csrf": csrf},
        )
        r = await integration_client.post(
            "/api/v1/auth/refresh",
            headers={"X-CSRF-Token": csrf},
            cookies={"reno_refresh": first, "reno_csrf": csrf},
        )
        assert r.status_code == 401


class TestInvitation:
    async def test_create_then_accept(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        access = await _login(integration_client, "admin@example.ch", ADMIN_PW)
        r = await integration_client.post(
            "/api/v1/auth/invitations",
            json={"email": "cousin@example.ch"},
            headers={"Authorization": f"Bearer {access}"},
        )
        assert r.status_code == 201, r.text
        token = r.json()["token"]
        assert token
        assert any(e.to == "cousin@example.ch" for e in mailer_module.SENT)

        integration_client.cookies.clear()
        r = await integration_client.post(
            "/api/v1/auth/invitations/accept",
            json={
                "token": token,
                "display_name": "Cousin",
                "password": "Sicher-Cousin-9!XYZ",
            },
        )
        assert r.status_code == 200, r.text

    async def test_accept_bad_token(self, integration_client: AsyncClient) -> None:
        r = await integration_client.post(
            "/api/v1/auth/invitations/accept",
            json={
                "token": "definitely-not-a-real-token-very-long",
                "display_name": "X",
                "password": "Sicher-Cousin-9!XYZ",
            },
        )
        assert r.status_code == 400

    async def test_invitation_requires_superuser(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        access = await _login(integration_client, "admin@example.ch", ADMIN_PW)
        r = await integration_client.post(
            "/api/v1/auth/invitations",
            json={"email": "regular@example.ch"},
            headers={"Authorization": f"Bearer {access}"},
        )
        token = r.json()["token"]
        integration_client.cookies.clear()
        r = await integration_client.post(
            "/api/v1/auth/invitations/accept",
            json={
                "token": token,
                "display_name": "Regular",
                "password": "Sicher-Regular-9!XYZ",
            },
        )
        regular_access = r.json()["access_token"]
        r = await integration_client.post(
            "/api/v1/auth/invitations",
            json={"email": "another@example.ch"},
            headers={"Authorization": f"Bearer {regular_access}"},
        )
        assert r.status_code == 403


class TestPasswordReset:
    async def test_unknown_email_silently_202(self, integration_client: AsyncClient) -> None:
        r = await integration_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "nobody@example.ch"},
        )
        assert r.status_code == 202
        assert not any(e.to == "nobody@example.ch" for e in mailer_module.SENT)

    async def test_full_flow(self, integration_client: AsyncClient, superuser: User) -> None:
        r = await integration_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@example.ch"},
        )
        assert r.status_code == 202
        msg = next(e for e in mailer_module.SENT if e.to == "admin@example.ch")
        token = msg.body.strip().rsplit("/", 1)[-1].split()[0]

        r = await integration_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "Neu-Sicher-9!ABCDEF"},
        )
        assert r.status_code == 204

        r = await integration_client.post(
            "/api/v1/auth/login",
            json={"email": "admin@example.ch", "password": "Neu-Sicher-9!ABCDEF"},
        )
        assert r.status_code == 200

    async def test_token_cannot_be_reused(
        self, integration_client: AsyncClient, superuser: User
    ) -> None:
        await integration_client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "admin@example.ch"},
        )
        msg = next(e for e in mailer_module.SENT if e.to == "admin@example.ch")
        token = msg.body.strip().rsplit("/", 1)[-1].split()[0]
        await integration_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "Neu-Sicher-9!ABCDEF"},
        )
        r = await integration_client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": token, "new_password": "AnotherTry-9!XYZ"},
        )
        assert r.status_code == 400
