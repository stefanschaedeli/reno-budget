"""Integration tests for the AI assistant router + pipeline.

The Anthropic client is replaced via a FastAPI dependency override with a fake
that returns canned structured outputs, so these tests exercise the real router,
RBAC, persistence, validation, and accept→apply paths end-to-end against the
testcontainers Postgres — without any live API call.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from app.api.v1.ai import get_ai_client
from app.core.security import hash_password
from app.models.audit import AuditEvent
from app.models.cost import BkpCode, CostItem
from app.models.object import Object, ObjectMembership, ObjectRole, ObjectType, Unit
from app.models.project import Project
from app.models.user import User
from app.schemas.ai import (
    BkpPosition,
    BkpScope,
    Confidence,
    Estimate,
    EstimateLineItem,
    GeneratedQuestion,
    ProjectClassification,
    QuestionSet,
    QuestionType,
)
from app.services.ai.critic import CriticVerdict
from app.services.ai.skills.describer import DescriptionDraft
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "TestPasswort-9!ABC"


class FakeAiClient:
    """Returns canned structured outputs keyed by the requested schema."""

    configured = True

    async def generate(self, *, system, prompt, schema, thinking=False, model=None):
        if schema is ProjectClassification:
            return ProjectClassification(
                project_type="roof", confidence=Confidence.HIGH, rationale="Dach"
            )
        if schema is QuestionSet:
            return QuestionSet(
                questions=[
                    GeneratedQuestion(
                        key="area_m2", label="Dachfläche?", type=QuestionType.NUMBER,
                        unit="m²",
                    )
                ]
            )
        if schema is DescriptionDraft:
            return DescriptionDraft(description="Neueindeckung des Daches, 120 m².")
        if schema is Estimate:
            return Estimate(
                total_chf=Decimal("30000.00"),
                line_items=[
                    EstimateLineItem(
                        label="Eindeckung",
                        amount_chf=Decimal("30000.00"),
                        assumptions="120 m² Ziegel",
                        confidence=Confidence.MEDIUM,
                    )
                ],
            )
        if schema is BkpScope:
            return BkpScope(
                positions=[
                    BkpPosition(
                        bkp_code="D",
                        title="Dacheindeckung",
                        in_scope=["Ziegel", "Lattung"],
                        out_of_scope=["Gerüst"],
                        estimated_amount_chf=Decimal("30000.00"),
                        assumptions="120 m²",
                        confidence=Confidence.MEDIUM,
                    )
                ]
            )
        if schema is CriticVerdict:
            return CriticVerdict(issues=[])
        raise AssertionError(f"unexpected schema {schema}")


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


def _csrf_cookies(client: AsyncClient) -> dict[str, str]:
    csrf = client.cookies.get("reno_csrf")
    return {"reno_csrf": csrf} if csrf else {}


@pytest_asyncio.fixture()
async def owner(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "owner@example.ch")


@pytest_asyncio.fixture()
async def viewer(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "viewer@example.ch")


@pytest_asyncio.fixture()
async def outsider(db_session: AsyncSession) -> User:
    return await _mk_user(db_session, "outsider@example.ch")


@pytest_asyncio.fixture()
async def sfh(db_session: AsyncSession, owner: User, viewer: User) -> Object:
    """SFH (one unit at 1000‰), owner + viewer membership, one BKP code, one project."""
    obj = Object(
        id=uuid.uuid4(),
        name="Haus am Hang",
        type=ObjectType.SFH,
        planning_horizon_years=30,
    )
    db_session.add(obj)
    await db_session.flush()
    db_session.add(Unit(object_id=obj.id, label="Ganzes Haus", wertquote_permille=1000))
    db_session.add(ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER))
    db_session.add(ObjectMembership(user_id=viewer.id, object_id=obj.id, role=ObjectRole.VIEWER))
    db_session.add(BkpCode(code="D", parent_code=None, level=1, label_de="Dach", is_seed=True))
    db_session.add(
        Project(id=uuid.uuid4(), object_id=obj.id, name="Dach erneuern")
    )
    await db_session.commit()
    return obj


async def _project_id(db_session: AsyncSession, object_id: uuid.UUID) -> uuid.UUID:
    row = (
        await db_session.execute(select(Project).where(Project.object_id == object_id))
    ).scalar_one()
    return row.id


@pytest_asyncio.fixture()
async def with_fake_ai(integration_app):
    integration_app.dependency_overrides[get_ai_client] = lambda: FakeAiClient()
    yield
    integration_app.dependency_overrides.pop(get_ai_client, None)


def _base(object_id: uuid.UUID, project_id: uuid.UUID) -> str:
    return f"/api/v1/objects/{object_id}/projects/{project_id}/ai"


async def _get(client: AsyncClient, token: str, path: str):
    return await client.get(path, headers=_auth(token, client))


async def _post(client: AsyncClient, token: str, path: str, json=None):
    return await client.post(
        path,
        headers=_auth(token, client),
        cookies=_csrf_cookies(client),
        json=json,
    )


class TestPipelineHappyPath:
    async def test_full_flow_writes_real_data_and_audits(
        self,
        integration_client: AsyncClient,
        owner: User,
        sfh: Object,
        db_session: AsyncSession,
        with_fake_ai: None,
    ) -> None:
        c = integration_client
        token = await _login(c, owner.email)
        pid = await _project_id(db_session, sfh.id)
        base = _base(sfh.id, pid)

        # Start session
        r = await _get(c, token, f"{base}/session")
        assert r.status_code == 200, r.text

        # Classify
        r = await _post(c, token, f"{base}/run", {"step": "classify"})
        assert r.status_code == 200, r.text
        assert r.json()["output"]["project_type"] == "roof"

        # Question
        r = await _post(c, token, f"{base}/run", {"step": "question"})
        assert r.status_code == 200, r.text
        assert r.json()["validation"]["ok"] is True

        # Submit answers
        r = await _post(c, token, f"{base}/answers", {"answers": {"area_m2": 120}})
        assert r.status_code == 200, r.text

        # Describe + accept -> writes Project.description
        r = await _post(c, token, f"{base}/run", {"step": "describe"})
        assert r.status_code == 200, r.text
        desc_artifact = r.json()["id"]
        r = await _post(c, token, f"{base}/artifacts/{desc_artifact}/accept")
        assert r.status_code == 200, r.text

        # Estimate + accept -> writes Project.rough_estimate_chf
        r = await _post(c, token, f"{base}/run", {"step": "estimate"})
        assert r.status_code == 200, r.text
        est_artifact = r.json()["id"]
        r = await _post(c, token, f"{base}/artifacts/{est_artifact}/accept")
        assert r.status_code == 200, r.text

        # BKP scope + accept -> creates CostItem
        r = await _post(c, token, f"{base}/run", {"step": "bkp_scope"})
        assert r.status_code == 200, r.text
        bkp_artifact = r.json()["id"]
        r = await _post(c, token, f"{base}/artifacts/{bkp_artifact}/accept")
        assert r.status_code == 200, r.text

        # Assert real data was written.
        project = (
            await db_session.execute(select(Project).where(Project.id == pid))
        ).scalar_one()
        assert project.description == "Neueindeckung des Daches, 120 m²."
        assert project.rough_estimate_chf == Decimal("30000.00")

        items = (
            (await db_session.execute(select(CostItem).where(CostItem.project_id == pid)))
            .scalars()
            .all()
        )
        assert len(items) == 1
        assert items[0].bkp_code == "D"
        assert items[0].planned_amount_chf == Decimal("30000.00")

        # Audit events recorded for the accepts.
        events = (
            (
                await db_session.execute(
                    select(AuditEvent).where(AuditEvent.action.like("ai.%"))
                )
            )
            .scalars()
            .all()
        )
        actions = {e.action for e in events}
        assert "ai.description_accept" in actions
        assert "ai.estimate_accept" in actions
        assert "ai.bkp_accept" in actions


class TestPipelineGuards:
    async def test_estimate_before_classify_conflicts(
        self,
        integration_client: AsyncClient,
        owner: User,
        sfh: Object,
        db_session: AsyncSession,
        with_fake_ai: None,
    ) -> None:
        c = integration_client
        token = await _login(c, owner.email)
        pid = await _project_id(db_session, sfh.id)
        base = _base(sfh.id, pid)
        await _get(c, token, f"{base}/session")
        r = await _post(c, token, f"{base}/run", {"step": "estimate"})
        assert r.status_code == 409, r.text

    async def test_viewer_cannot_run(
        self,
        integration_client: AsyncClient,
        viewer: User,
        sfh: Object,
        db_session: AsyncSession,
        with_fake_ai: None,
    ) -> None:
        c = integration_client
        token = await _login(c, viewer.email)
        pid = await _project_id(db_session, sfh.id)
        base = _base(sfh.id, pid)
        r = await _get(c, token, f"{base}/session")
        assert r.status_code == 403, r.text

    async def test_outsider_gets_404(
        self,
        integration_client: AsyncClient,
        outsider: User,
        sfh: Object,
        db_session: AsyncSession,
        with_fake_ai: None,
    ) -> None:
        c = integration_client
        token = await _login(c, outsider.email)
        pid = await _project_id(db_session, sfh.id)
        base = _base(sfh.id, pid)
        r = await _get(c, token, f"{base}/session")
        assert r.status_code == 404, r.text


class TestUnconfigured:
    async def test_run_returns_503_without_key(
        self,
        integration_client: AsyncClient,
        owner: User,
        sfh: Object,
        db_session: AsyncSession,
    ) -> None:
        # No with_fake_ai override here: the real get_ai_client runs and, with no
        # RENO_ANTHROPIC_API_KEY set in the test env, returns 503.
        c = integration_client
        token = await _login(c, owner.email)
        pid = await _project_id(db_session, sfh.id)
        base = _base(sfh.id, pid)
        await _get(c, token, f"{base}/session")
        r = await _post(c, token, f"{base}/run", {"step": "classify"})
        assert r.status_code == 503, r.text
