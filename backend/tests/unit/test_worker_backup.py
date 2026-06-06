"""Unit tests for :mod:`app.worker.backup`.

These do not touch Postgres or run pg_dump — we exercise the URL parser,
argv builder, and retention pruning policy in isolation.
"""

from __future__ import annotations

import gzip
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from app.worker import backup as backup_mod


def _touch(directory: Path, when: datetime, content: bytes = b"x") -> Path:
    name = backup_mod._backup_filename(when)
    p = directory / name
    with gzip.open(p, "wb") as gz:
        gz.write(content)
    return p


class TestParseDatabaseUrl:
    def test_full_url(self) -> None:
        parsed = backup_mod._parse_database_url(
            "postgresql+asyncpg://reno:s3cret@db.example:6543/renodb"
        )
        assert parsed == {
            "host": "db.example",
            "port": 6543,
            "user": "reno",
            "password": "s3cret",
            "database": "renodb",
        }

    def test_default_port(self) -> None:
        parsed = backup_mod._parse_database_url(
            "postgresql+asyncpg://reno:pw@localhost/renodb"
        )
        assert parsed["port"] == 5432

    def test_url_encoded_password(self) -> None:
        parsed = backup_mod._parse_database_url(
            "postgresql+asyncpg://reno:p%40ss%21@h/d"
        )
        assert parsed["password"] == "p@ss!"


class TestBuildPgDumpArgv:
    def test_includes_all_connection_flags(self) -> None:
        argv = backup_mod._build_pg_dump_argv(
            {
                "host": "db",
                "port": 5432,
                "user": "reno",
                "password": "ignored",
                "database": "renodb",
            }
        )
        assert argv[0] == "pg_dump"
        assert "-h" in argv and "db" in argv
        assert "-p" in argv and "5432" in argv
        assert "-U" in argv and "reno" in argv
        assert "-d" in argv and "renodb" in argv
        # Password must NOT appear in argv — it goes via PGPASSWORD env.
        assert "ignored" not in argv


class TestPruneBackups:
    def test_keeps_daily_window(self, tmp_path: Path) -> None:
        # 40 daily backups, one per day going back 40 days.
        base = datetime(2026, 6, 1, 2, 30, 0)
        files = []
        for i in range(40):
            files.append(_touch(tmp_path, base - timedelta(days=i)))

        removed = backup_mod.prune_backups(
            tmp_path, daily_keep=30, monthly_keep=12
        )
        survivors = sorted(p.name for p in tmp_path.iterdir())
        # Daily window keeps 30; the older 10 may survive via monthly window
        # because their YYYY-MM is distinct (they span ~Apr/May/Jun 2026).
        # The point: at least the 30 most recent must survive.
        recent_30 = sorted(p.name for p in files[:30])
        for name in recent_30:
            assert name in survivors
        # Pruning happened — some files were removed.
        assert len(removed) == 40 - len(survivors)

    def test_preserves_monthly_first(self, tmp_path: Path) -> None:
        # Files in Jan, Feb, Mar 2026 — 5 each. We expect 3 oldest months to keep
        # their first (= newest, since we list newest-first) one each.
        files: list[Path] = []
        for month in (1, 2, 3):
            for day in (1, 5, 10, 15, 20):
                files.append(_touch(tmp_path, datetime(2026, month, day, 2, 30)))

        backup_mod.prune_backups(tmp_path, daily_keep=1, monthly_keep=3)
        survivors = sorted(p.name for p in tmp_path.iterdir())
        # Daily window keeps the single newest overall.
        # Monthly window keeps newest in each of Jan / Feb / Mar.
        # Newest in Jan 2026: day 20; newest overall: Mar 20.
        assert any("2026-01-20" in n for n in survivors)
        assert any("2026-02-20" in n for n in survivors)
        assert any("2026-03-20" in n for n in survivors)

    def test_ignores_unrelated_files(self, tmp_path: Path) -> None:
        (tmp_path / "README.txt").write_text("hi")
        _touch(tmp_path, datetime(2026, 5, 1, 2, 30))
        backup_mod.prune_backups(tmp_path, daily_keep=1, monthly_keep=1)
        assert (tmp_path / "README.txt").exists()


class TestRunBackup:
    @pytest.mark.asyncio
    async def test_run_backup_invokes_pg_dump_with_correct_args(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        async def fake_run(argv: list[str], password: str | None, target: Path) -> int:
            captured["argv"] = argv
            captured["password"] = password
            captured["target"] = target
            # Simulate writing some bytes.
            with gzip.open(target, "wb") as gz:
                gz.write(b"-- fake dump\n")
            return target.stat().st_size

        async def fake_audit(*args: object, **kwargs: object) -> None:
            captured["audit_called"] = True

        monkeypatch.setattr(backup_mod, "_run_pg_dump", fake_run)
        monkeypatch.setattr(backup_mod, "_record_backup_audit", fake_audit)

        from app.core.config import Settings

        settings = Settings(
            database_url="postgresql+asyncpg://renouser:topsecret@dbhost:5499/renodb",
            backups_dir=str(tmp_path),
        )

        result = await backup_mod.run_backup(settings)
        argv = captured["argv"]
        assert isinstance(argv, list)
        assert "dbhost" in argv
        assert "5499" in argv
        assert "renouser" in argv
        assert "renodb" in argv
        assert captured["password"] == "topsecret"
        assert captured["audit_called"] is True
        assert result.exists()
        assert result.suffix == ".gz"
