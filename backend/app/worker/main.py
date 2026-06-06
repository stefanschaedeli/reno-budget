"""Worker entrypoint — APScheduler wiring + CLI.

Run as ``python -m app.worker`` to start the long-lived scheduler. Both jobs
are registered with stable string IDs (``backup``, ``digest``) so operators
can target them by name. Graceful shutdown is wired to SIGTERM / SIGINT.

Single-run mode (``--run-once backup`` / ``--run-once digest``) executes one
pass and exits — useful for first-deploy smoke tests and manual reruns from
inside the worker container.

Logging is JSON-line structured to stdout via ``structlog`` so the host's
log aggregator can ingest it without custom parsing.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys
from typing import Literal

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.config import Settings, get_settings
from app.worker.backup import run_backup
from app.worker.digest import run_digests

JOB_BACKUP_ID = "backup"
JOB_DIGEST_ID = "digest"

logger = structlog.get_logger("app.worker")


def _configure_logging(settings: Settings) -> None:
    """Configure stdlib + structlog for JSON-line output."""
    level = getattr(logging, settings.log_level, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(message)s",
        stream=sys.stdout,
    )
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        cache_logger_on_first_use=True,
    )


def build_scheduler(settings: Settings | None = None) -> AsyncIOScheduler:
    """Construct an :class:`AsyncIOScheduler` with both jobs registered.

    Factored out so tests can introspect ``scheduler.get_jobs()`` without
    starting the scheduler.
    """
    settings = settings or get_settings()
    scheduler = AsyncIOScheduler(timezone="UTC")
    scheduler.add_job(
        _run_backup_job,
        CronTrigger.from_crontab(settings.worker_backup_cron),
        id=JOB_BACKUP_ID,
        name="Nightly DB backup",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        _run_digest_job,
        CronTrigger.from_crontab(settings.worker_digest_cron),
        id=JOB_DIGEST_ID,
        name="Weekly reminder digest",
        coalesce=True,
        max_instances=1,
        misfire_grace_time=3600,
    )
    return scheduler


async def _run_backup_job() -> None:
    """APScheduler-callable wrapper around :func:`run_backup` with logging."""
    try:
        target = await run_backup()
        logger.info("worker.backup.completed", filename=target.name)
    except Exception as exc:
        logger.error("worker.backup.failed", error=str(exc))
        raise


async def _run_digest_job() -> None:
    """APScheduler-callable wrapper around :func:`run_digests` with logging."""
    try:
        sent = await run_digests()
        logger.info("worker.digest.completed", sent=sent)
    except Exception as exc:
        logger.error("worker.digest.failed", error=str(exc))
        raise


async def _serve_forever(settings: Settings) -> None:
    """Start the scheduler and block until SIGTERM / SIGINT."""
    scheduler = build_scheduler(settings)
    scheduler.start()
    logger.info(
        "worker.started",
        backup_cron=settings.worker_backup_cron,
        digest_cron=settings.worker_digest_cron,
    )

    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        # Windows / restricted envs raise NotImplementedError; that's fine —
        # the scheduler will simply not be signal-driven there.
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, stop_event.set)

    try:
        await stop_event.wait()
    finally:
        logger.info("worker.stopping")
        scheduler.shutdown(wait=False)
        logger.info("worker.stopped")


async def _run_once(job: Literal["backup", "digest"]) -> int:
    if job == "backup":
        await run_backup()
    elif job == "digest":
        await run_digests()
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="app.worker", description=__doc__)
    parser.add_argument(
        "--run-once",
        choices=("backup", "digest"),
        help="Execute a single pass of the named job and exit.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    settings = get_settings()
    _configure_logging(settings)
    args = _parse_args(argv)
    if args.run_once:
        return asyncio.run(_run_once(args.run_once))
    asyncio.run(_serve_forever(settings))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
