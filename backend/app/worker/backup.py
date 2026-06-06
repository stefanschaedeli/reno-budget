"""Nightly Postgres backups for the Reno-Budget worker.

The job runs ``pg_dump`` as a subprocess, gzipping the output on the fly and
writing the result to ``<settings.backups_dir>/reno-budget_<timestamp>.sql.gz``.
Connection details are parsed from :attr:`Settings.database_url` — host, port,
database, user become CLI args; the password is exported via ``PGPASSWORD``
in the subprocess environment so it never appears in argv (which would be
visible to other processes via ``/proc``).

Retention
---------
After each successful dump we walk the backups directory and prune older
files. We keep:

* the most recent ``worker_backup_retention_daily`` daily files (default 30);
* the most recent ``worker_backup_retention_monthly`` *monthly* files
  (default 12) — the first dump found in each ``YYYY-MM`` window survives.

Anything matching the ``reno-budget_*.sql.gz`` glob but outside both sets is
unlinked. Files that don't match the pattern are left alone.

Audit
-----
A successful run writes a single ``worker.backup`` audit event with a German
summary including the human-readable file size. A failure does **not** write
an audit row — it re-raises so APScheduler logs the failure with a stack
trace.
"""

from __future__ import annotations

import asyncio
import contextlib
import gzip
import logging
import os
import re
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

from sqlalchemy.ext.asyncio import async_sessionmaker

import app.core.db as db_module
from app.core.config import Settings, get_settings
from app.services import audit as audit_svc

logger = logging.getLogger(__name__)

# Matches the timestamped backup filenames we write.
_BACKUP_RE = re.compile(r"^reno-budget_(\d{4})-(\d{2})-(\d{2})-(\d{2})(\d{2})(\d{2})\.sql\.gz$")


def _parse_database_url(url: str) -> dict[str, str | int | None]:
    """Extract host/port/db/user/password from a SQLAlchemy DB URL.

    Strips driver prefixes like ``+asyncpg`` so the result is a plain
    libpq-friendly set of params.
    """
    # SQLAlchemy URLs look like postgresql+asyncpg://user:pass@host:port/db
    # urllib can parse those if we strip the driver part.
    scheme, _, rest = url.partition("://")
    base_scheme = scheme.split("+", 1)[0]
    parsed = urlparse(f"{base_scheme}://{rest}")
    return {
        "host": parsed.hostname,
        "port": parsed.port or 5432,
        "user": unquote(parsed.username) if parsed.username else None,
        "password": unquote(parsed.password) if parsed.password else None,
        "database": parsed.path.lstrip("/") or None,
    }


def _human_size(num_bytes: int) -> str:
    """Render a byte count as a short German-style string (KB/MB/GB)."""
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}".replace(".", ",")
        size /= 1024
    return f"{num_bytes} B"


def _backup_filename(now: datetime) -> str:
    return f"reno-budget_{now.strftime('%Y-%m-%d-%H%M%S')}.sql.gz"


def _build_pg_dump_argv(conn: dict[str, str | int | None]) -> list[str]:
    """Construct the pg_dump argument vector from parsed connection params."""
    argv: list[str] = ["pg_dump", "--no-owner", "--no-privileges", "--format=plain"]
    if conn["host"]:
        argv += ["-h", str(conn["host"])]
    if conn["port"]:
        argv += ["-p", str(conn["port"])]
    if conn["user"]:
        argv += ["-U", str(conn["user"])]
    if conn["database"]:
        argv += ["-d", str(conn["database"])]
    return argv


async def _run_pg_dump(argv: list[str], password: str | None, target: Path) -> int:
    """Run ``pg_dump`` and gzip its stdout into ``target``.

    Returns the file size in bytes on success; raises ``RuntimeError`` on
    non-zero exit.
    """
    env = os.environ.copy()
    if password:
        env["PGPASSWORD"] = password

    proc = await asyncio.create_subprocess_exec(
        *argv,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    bytes_written = 0
    with gzip.open(target, "wb") as gz:
        assert proc.stdout is not None
        while True:
            chunk = await proc.stdout.read(64 * 1024)
            if not chunk:
                break
            gz.write(chunk)
            bytes_written += len(chunk)

    stderr_bytes = await proc.stderr.read() if proc.stderr else b""
    returncode = await proc.wait()
    if returncode != 0:
        # Drop partial file — leaves the directory in a clean state.
        with contextlib.suppress(FileNotFoundError):
            target.unlink()
        raise RuntimeError(
            f"pg_dump exited with {returncode}: {stderr_bytes.decode('utf-8', 'replace').strip()}"
        )
    return target.stat().st_size


def _existing_backups(directory: Path) -> list[Path]:
    """Return existing backup files sorted newest-first by filename timestamp."""
    if not directory.exists():
        return []
    matched: list[Path] = []
    for entry in directory.iterdir():
        if not entry.is_file():
            continue
        if _BACKUP_RE.match(entry.name):
            matched.append(entry)
    # Filename embeds an ISO-ish timestamp, so lexicographic sort = chronological.
    matched.sort(key=lambda p: p.name, reverse=True)
    return matched


def _select_keepers(
    files: Iterable[Path], *, daily_keep: int, monthly_keep: int
) -> set[Path]:
    """Return the set of files to keep under the daily+monthly policy.

    ``files`` MUST be ordered newest-first; we walk it once.
    """
    files = list(files)
    keep: set[Path] = set()
    # Daily window: the N most recent files unconditionally.
    for f in files[:daily_keep]:
        keep.add(f)
    # Monthly window: the first (newest) file per YYYY-MM, up to M months.
    seen_months: dict[str, Path] = {}
    for f in files:
        match = _BACKUP_RE.match(f.name)
        if not match:
            continue
        ym = f"{match.group(1)}-{match.group(2)}"
        if ym not in seen_months:
            seen_months[ym] = f
    # Months come in newest-first order because files were sorted that way.
    for _ym, f in list(seen_months.items())[:monthly_keep]:
        keep.add(f)
    return keep


def prune_backups(
    directory: Path, *, daily_keep: int, monthly_keep: int
) -> list[Path]:
    """Apply the retention policy in ``directory``.

    Returns the list of files that were unlinked. Files not matching the
    backup glob are left alone.
    """
    files = _existing_backups(directory)
    keepers = _select_keepers(files, daily_keep=daily_keep, monthly_keep=monthly_keep)
    removed: list[Path] = []
    for f in files:
        if f not in keepers:
            try:
                f.unlink()
                removed.append(f)
            except FileNotFoundError:
                pass
    return removed


async def _record_backup_audit(
    target: Path, size_bytes: int, settings: Settings | None = None
) -> None:
    """Open a short-lived session and append the ``worker.backup`` audit row."""
    _ = settings  # currently unused; kept for future per-tenant routing
    SessionLocal: async_sessionmaker = db_module.SessionLocal  # type: ignore[type-arg]
    async with SessionLocal() as session:
        await audit_svc.record(
            session,
            actor=None,
            actor_email=audit_svc.WORKER_ACTOR_EMAIL,
            action=audit_svc.ACTION_WORKER_BACKUP,
            target_type="system",
            target_id=None,
            summary=f"Backup erstellt: {target.name} ({_human_size(size_bytes)})",
            payload={"filename": target.name, "size_bytes": size_bytes},
        )
        await session.commit()


async def run_backup(settings: Settings | None = None) -> Path:
    """Execute a single backup pass.

    Returns the path of the gzipped dump on success. On failure the
    exception is re-raised after logging so APScheduler records it.
    """
    settings = settings or get_settings()
    backups_dir = Path(settings.backups_dir)
    backups_dir.mkdir(parents=True, exist_ok=True)

    conn = _parse_database_url(settings.database_url)
    argv = _build_pg_dump_argv(conn)
    now = datetime.now(tz=UTC)
    target = backups_dir / _backup_filename(now)
    password = conn["password"] if isinstance(conn["password"], str) else None

    logger.info(
        "worker.backup.start file=%s host=%s db=%s",
        target.name,
        conn.get("host"),
        conn.get("database"),
    )
    size_bytes = await _run_pg_dump(argv, password, target)
    removed = prune_backups(
        backups_dir,
        daily_keep=settings.worker_backup_retention_daily,
        monthly_keep=settings.worker_backup_retention_monthly,
    )
    logger.info(
        "worker.backup.ok file=%s size=%d pruned=%d",
        target.name,
        size_bytes,
        len(removed),
    )
    await _record_backup_audit(target, size_bytes, settings)
    return target


__all__ = [
    "_BACKUP_RE",
    "_build_pg_dump_argv",
    "_parse_database_url",
    "prune_backups",
    "run_backup",
]
