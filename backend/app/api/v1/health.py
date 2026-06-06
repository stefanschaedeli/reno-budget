"""Liveness / readiness endpoints.

``/healthz`` is intentionally cheap and dependency-free so container
orchestrators can probe it during boot. Deeper readiness checks (DB
connectivity, migrations applied) belong in a separate ``/readyz`` endpoint
added in a later phase.
"""

from __future__ import annotations

from fastapi import APIRouter

from app import __version__

router = APIRouter(tags=["health"])


@router.get("/healthz", summary="Liveness probe")
async def healthz() -> dict[str, str]:
    """Return a static OK response — proves the process is up and serving HTTP."""
    return {"status": "ok", "version": __version__}
