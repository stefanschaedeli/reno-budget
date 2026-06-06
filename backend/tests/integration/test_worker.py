"""Integration tests for the Phase-9 worker (backup + digest + scheduler)."""

from __future__ import annotations

import gzip
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

import app.core.db as db_module
import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.core.security import hash_password
from app.models.attachment import Attachment, AttachmentTargetType
from app.models.audit import AuditEvent
from app.models.cost import (
    BkpCode,
    CostItem,
    CostItemPriority,
    CostItemStatus,
)
from app.models.object import (
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
)
from app.models.user import User
from app.services import mailer as mailer_module
from app.worker import backup as backup_mod
from app.worker import digest as digest_mod
from app.worker.main import JOB_BACKUP_ID, JOB_DIGEST_ID, build_scheduler
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

PW = "TestPasswort-9!ABC"


@pytest.fixture(autouse=True)
def _isolate_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setenv("RENO_ENVIRONMENT", "test")
    monkeypatch.setenv("RENO_BACKUPS_DIR", str(tmp_path / "backups"))
    monkeypatch.delenv("RENO_SMTP_HOST", raising=False)
    get_settings.cache_clear()
    mailer_module.SENT.clear()
    yield
    get_settings.cache_clear()


@pytest_asyncio.fixture()
async def _wire_session_local(_engine, monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[None]:
    """Point :mod:`app.core.db` at the testcontainers engine for worker code."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    SessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False)
    monkeypatch.setattr(db_module, "engine", _engine)
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)
    yield


# ------------------------------------------------------------------ Backup --


class TestBackupIntegration:
    async def test_run_backup_writes_audit_event(
        self,
        db_session: AsyncSession,
        _wire_session_local: None,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # Avoid actually calling pg_dump — synthesise a gzipped file.
        async def fake_run(argv: list[str], password: str | None, target: Path) -> int:
            with gzip.open(target, "wb") as gz:
                gz.write(b"-- fake dump\n")
            return target.stat().st_size

        monkeypatch.setattr(backup_mod, "_run_pg_dump", fake_run)

        target = await backup_mod.run_backup()
        assert target.exists()
        assert target.name.startswith("reno-budget_")
        assert target.suffix == ".gz"

        rows = (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "worker.backup")
            )
        ).scalars().all()
        assert len(rows) == 1
        evt = rows[0]
        assert evt.actor_user_id is None
        assert evt.actor_email == "worker@reno-budget.local"
        assert evt.target_type == "system"
        assert evt.target_id is None
        assert target.name in evt.summary

    async def test_run_backup_failure_no_audit(
        self,
        db_session: AsyncSession,
        _wire_session_local: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def boom(argv: list[str], password: str | None, target: Path) -> int:
            raise RuntimeError("pg_dump exited with 1: connection refused")

        monkeypatch.setattr(backup_mod, "_run_pg_dump", boom)

        with pytest.raises(RuntimeError):
            await backup_mod.run_backup()

        rows = (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "worker.backup")
            )
        ).scalars().all()
        assert rows == []


# ------------------------------------------------------------------ Digest --


@pytest_asyncio.fixture()
async def _seeded(db_session: AsyncSession) -> tuple[User, User, Object]:
    """Owner + a second user, one SFH, with a BKP code for cost items."""
    owner = User(
        id=uuid.uuid4(),
        email="owner@digest.ch",
        display_name="Eigentümer",
        password_hash=hash_password(PW),
        is_active=True,
    )
    quiet_user = User(
        id=uuid.uuid4(),
        email="quiet@digest.ch",
        display_name="Stiller Benutzer",
        password_hash=hash_password(PW),
        is_active=True,
    )
    db_session.add_all([owner, quiet_user])
    db_session.add(
        BkpCode(code="D", parent_code=None, level=1, label_de="Technik", is_seed=True)
    )
    db_session.add(
        BkpCode(code="D01", parent_code="D", level=2, label_de="Heizung", is_seed=True)
    )
    obj = Object(
        id=uuid.uuid4(),
        name="Haus Digest",
        type=ObjectType.SFH,
        planning_horizon_years=30,
    )
    db_session.add(obj)
    await db_session.flush()
    db_session.add(Unit(object_id=obj.id, label="Ganzes Haus", wertquote_permille=1000))
    db_session.add(
        ObjectMembership(user_id=owner.id, object_id=obj.id, role=ObjectRole.OWNER)
    )
    await db_session.commit()
    return owner, quiet_user, obj


class TestDigestIntegration:
    async def test_digest_sent_when_signals_present(
        self,
        db_session: AsyncSession,
        _wire_session_local: None,
        _seeded: tuple[User, User, Object],
    ) -> None:
        owner, _quiet, obj = _seeded
        current_year = datetime.now(tz=UTC).year
        db_session.add(
            CostItem(
                object_id=obj.id,
                bkp_code="D01",
                title="Heizung dringend ersetzen",
                priority=CostItemPriority.URGENT,
                status=CostItemStatus.PLANNED,
                planned_year=current_year,
                planned_amount_chf=Decimal("12000.00"),
            )
        )
        await db_session.commit()

        sent_count = await digest_mod.run_digests()
        assert sent_count == 1

        # Mailer captured exactly one message addressed to the owner.
        assert len(mailer_module.SENT) == 1
        msg = mailer_module.SENT[0]
        assert msg.to == owner.email
        assert "Wöchentliche Übersicht" in msg.subject
        assert "Heizung dringend ersetzen" in msg.body

        # Audit row written for the recipient.
        rows = (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "worker.digest_sent")
            )
        ).scalars().all()
        assert len(rows) == 1
        assert rows[0].target_id == owner.id
        assert rows[0].target_type == "user"

    async def test_digest_skipped_when_nothing_to_report(
        self,
        db_session: AsyncSession,
        _wire_session_local: None,
        _seeded: tuple[User, User, Object],
    ) -> None:
        # No cost items, no attachments — quiet_user has no memberships at all.
        sent_count = await digest_mod.run_digests()
        assert sent_count == 0
        assert mailer_module.SENT == []

        rows = (
            await db_session.execute(
                select(AuditEvent).where(AuditEvent.action == "worker.digest_sent")
            )
        ).scalars().all()
        assert rows == []

    async def test_digest_lists_recent_attachment_from_other_user(
        self,
        db_session: AsyncSession,
        _wire_session_local: None,
        _seeded: tuple[User, User, Object],
    ) -> None:
        _owner, other, obj = _seeded
        att = Attachment(
            target_type=AttachmentTargetType.OBJECT,
            target_id=obj.id,
            sha256="a" * 64,
            filename="vertrag.pdf",
            mime="application/pdf",
            size_bytes=12,
            uploaded_by=other.id,
            created_at=datetime.now(tz=UTC) - timedelta(days=2),
        )
        db_session.add(att)
        await db_session.commit()

        sent = await digest_mod.run_digests()
        assert sent == 1
        assert "vertrag.pdf" in mailer_module.SENT[0].body


# --------------------------------------------------------------- Scheduler --


def test_scheduler_registers_both_jobs() -> None:
    scheduler = build_scheduler()
    try:
        job_ids = {job.id for job in scheduler.get_jobs()}
        assert job_ids == {JOB_BACKUP_ID, JOB_DIGEST_ID}
    finally:
        # Scheduler hasn't been started; just drop the reference.
        del scheduler
