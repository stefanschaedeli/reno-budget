"""Data-access helpers for the eBKP-H code catalogue.

Pure SQL layer — no validation, no business rules. As elsewhere in the
codebase, these helpers never commit; the service / router layer owns the
transaction boundary.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import BkpCode


async def list_bkp_codes(session: AsyncSession) -> Sequence[BkpCode]:
    """All catalogue rows sorted by code (stable, lexicographically grouped)."""
    stmt = select(BkpCode).order_by(BkpCode.code)
    return (await session.execute(stmt)).scalars().all()


async def get_bkp_code(session: AsyncSession, code: str) -> BkpCode | None:
    return await session.get(BkpCode, code)
