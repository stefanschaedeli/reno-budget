"""Smoke test for the developer fixture seed.

Verifies that :func:`app.seeds.dev_seed.seed_dev` runs cleanly against the
testcontainers Postgres fixture, produces the documented row counts, and is
idempotent on a second invocation.

The dev seed references the eBKP-H catalogue via FK; this test loads the
catalogue from the JSON shipping fixture first to mirror what a real dev DB
looks like after Alembic ``upgrade head``.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from app.models.cost import BkpCode, CostItem, CostItemStatus
from app.models.object import Object, ObjectMembership, Unit
from app.models.user import User
from app.seeds.dev_seed import (
    CURRENT_YEAR,
    DEMO_EDITOR_EMAIL,
    DEMO_OWNER_EMAIL,
    seed_dev,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.integration

_EBKP_JSON = Path(__file__).resolve().parents[2] / "app" / "seeds" / "ebkp_h.json"


async def _load_bkp_catalogue(session: AsyncSession) -> None:
    """Insert the eBKP-H catalogue rows so the cost items have a valid FK target."""
    rows = json.loads(_EBKP_JSON.read_text(encoding="utf-8"))
    for row in rows:
        if row.get("_meta"):
            continue
        session.add(
            BkpCode(
                code=row["code"],
                parent_code=row["parent_code"],
                level=row["level"],
                label_de=row["label_de"],
                description=row.get("description"),
                is_seed=True,
            )
        )
    await session.flush()


async def test_seed_dev_creates_expected_dataset(db_session: AsyncSession) -> None:
    """seed_dev populates 2 users, 2 objects, 4 units, 3 memberships, ~18 items."""
    await _load_bkp_catalogue(db_session)

    summary = await seed_dev(db_session)

    assert summary["skipped"] is False
    assert summary["users"] == 2
    assert summary["objects"] == 2
    assert summary["units"] == 4  # 1 (SFH) + 3 (MFH)
    assert summary["memberships"] == 3
    assert summary["cost_items"] >= 15

    # Status mix covers every lifecycle bucket.
    sc = summary["status_counts"]
    assert sc.get(CostItemStatus.IDEA.value, 0) >= 2
    assert sc.get(CostItemStatus.PLANNED.value, 0) >= 5
    assert sc.get(CostItemStatus.IN_PROGRESS.value, 0) >= 2
    assert sc.get(CostItemStatus.COMPLETED.value, 0) >= 2
    assert sc.get(CostItemStatus.CANCELLED.value, 0) >= 1

    # Year horizon covers ``current_year`` through ``current_year + 10``.
    years = (await db_session.execute(select(CostItem.planned_year))).scalars().all()
    assert min(y for y in years if y is not None) <= CURRENT_YEAR - 1
    assert max(y for y in years if y is not None) >= CURRENT_YEAR + 8

    # Both demo users exist and are active.
    users = (await db_session.execute(select(User))).scalars().all()
    emails = {u.email for u in users}
    assert DEMO_OWNER_EMAIL in emails
    assert DEMO_EDITOR_EMAIL in emails

    # Both demo objects + their units survived the flush.
    objects = (await db_session.execute(select(Object))).scalars().all()
    assert len(objects) == 2
    units = (await db_session.execute(select(Unit))).scalars().all()
    assert len(units) == 4

    # 3 memberships: 2x OWNER + 1 EDITOR.
    memberships = (await db_session.execute(select(ObjectMembership))).scalars().all()
    assert len(memberships) == 3


async def test_seed_dev_is_idempotent(db_session: AsyncSession) -> None:
    """A second invocation must skip cleanly without raising or duplicating rows."""
    await _load_bkp_catalogue(db_session)

    first = await seed_dev(db_session)
    assert first["skipped"] is False

    second = await seed_dev(db_session)
    assert second["skipped"] is True
    assert "exists" in second["reason"]

    # No duplicate users created.
    users = (await db_session.execute(select(User))).scalars().all()
    assert len(users) == 2
