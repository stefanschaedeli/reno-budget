"""Minimal performance smoke for the Reno-Budget API.

Hits each representative endpoint ``ITERATIONS`` times at concurrency
``CONCURRENCY`` and prints p50/p95/p99 in milliseconds. Requires the dev
stack to be up (``docker compose -f deploy/docker-compose.yml up -d``) and
the dev seed loaded.

Authentication is performed once at the start with credentials taken from
the ``RENO_PERF_USER`` / ``RENO_PERF_PASS`` environment variables; defaults
are the dev-seed owner.

Run:

    python scripts/perf_smoke.py

This script is intentionally tiny — it produces a baseline number, not a
benchmark suite.
"""

from __future__ import annotations

import asyncio
import os
import statistics
import time
from collections.abc import Callable, Coroutine
from typing import Any

import httpx

BASE = os.environ.get("RENO_PERF_BASE", "http://localhost:8080")
USER = os.environ.get("RENO_PERF_USER", "owner@example.com")
PASS = os.environ.get("RENO_PERF_PASS", "owner-passwort-12!")  # noqa: S105 — dev seed
ITERATIONS = 200
CONCURRENCY = 10


async def _login(client: httpx.AsyncClient) -> dict[str, str]:
    r = await client.post("/api/v1/auth/login", json={"email": USER, "password": PASS})
    r.raise_for_status()
    access = r.json()["access_token"]
    csrf = r.cookies.get("reno_csrf", "")
    return {"Authorization": f"Bearer {access}", "X-CSRF-Token": csrf}


async def _measure(
    name: str,
    op: Callable[[httpx.AsyncClient], Coroutine[Any, Any, httpx.Response]],
    client: httpx.AsyncClient,
) -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    samples: list[float] = []

    async def one() -> None:
        async with sem:
            t0 = time.perf_counter()
            r = await op(client)
            samples.append((time.perf_counter() - t0) * 1000)
            r.raise_for_status()

    await asyncio.gather(*(one() for _ in range(ITERATIONS)))

    samples.sort()
    p50 = samples[int(len(samples) * 0.50)]
    p95 = samples[int(len(samples) * 0.95)]
    p99 = samples[int(len(samples) * 0.99)]
    print(f"{name:<55} n={ITERATIONS} p50={p50:6.1f}ms p95={p95:6.1f}ms p99={p99:6.1f}ms")
    if p95 > 500:
        print(f"  ! p95 above 500ms threshold — investigate {name}")


async def main() -> None:
    async with httpx.AsyncClient(base_url=BASE, timeout=30) as client:
        headers = await _login(client)
        client.headers.update(headers)

        objs = (await client.get("/api/v1/objects")).json()
        if not objs:
            raise SystemExit("No objects — run dev_seed first.")
        obj_id = objs[0]["id"]

        bkp = (await client.get("/api/v1/bkp-codes?limit=1")).json()[0]

        await _measure("GET /api/v1/objects", lambda c: c.get("/api/v1/objects"), client)
        await _measure(
            f"GET /api/v1/objects/{obj_id}/budget/timeline",
            lambda c: c.get(f"/api/v1/objects/{obj_id}/budget/timeline"),
            client,
        )
        await _measure(
            f"GET /api/v1/objects/{obj_id}/audit?limit=50",
            lambda c: c.get(f"/api/v1/objects/{obj_id}/audit?limit=50"),
            client,
        )

        async def create_one(c: httpx.AsyncClient) -> httpx.Response:
            return await c.post(
                f"/api/v1/objects/{obj_id}/cost-items",
                json={
                    "title": f"Perf {time.time_ns()}",
                    "bkp_code_id": bkp["id"],
                    "planned_amount_chf": "100.00",
                    "status": "idee",
                    "priority": "mittel",
                    "year": 2026,
                },
            )

        await _measure("POST /api/v1/cost-items", create_one, client)


if __name__ == "__main__":
    asyncio.run(main())
