"""Business logic for the eBKP-H code catalogue.

The catalogue is read-mostly: every authenticated user can browse the seeded
codes (flat or as a tree). Only superusers may extend it with custom codes
— enforced by the router via :func:`app.core.deps.require_superuser`. The
service helpers below do NOT re-check superuser status; they trust the
router gate but still validate parent existence and uniqueness.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import BkpCode
from app.repositories.bkp import get_bkp_code, list_bkp_codes
from app.schemas.cost import BkpCodeCreate, BkpCodeRead, BkpCodeTree


class BkpCodeServiceError(Exception):
    """Base class for catalogue business errors."""


class DuplicateBkpCodeError(BkpCodeServiceError):
    """Refused to create a code whose primary key already exists."""


class UnknownParentBkpCodeError(BkpCodeServiceError):
    """The provided ``parent_code`` does not exist in the catalogue."""


async def get_flat_catalogue(session: AsyncSession) -> list[BkpCodeRead]:
    """Return every code as a flat, code-sorted list."""
    rows = await list_bkp_codes(session)
    return [BkpCodeRead.model_validate(r) for r in rows]


async def get_catalogue_tree(session: AsyncSession) -> list[BkpCodeTree]:
    """Return the catalogue as a nested forest (one tree per root code).

    Built in two passes for clarity and O(n) cost: index by code, then attach
    each non-root to its parent's ``children`` list. We never recurse into
    the DB layer — the seed catalogue is small (~75 codes) and we cache
    nothing here on purpose, leaving caching to the HTTP layer if needed.
    """
    rows = await list_bkp_codes(session)
    return _build_tree(rows)


async def create_custom_code(session: AsyncSession, payload: BkpCodeCreate) -> BkpCode:
    """Insert a custom (non-seed) catalogue row. Superuser-only at the router.

    Raises :class:`DuplicateBkpCodeError` if the code exists, or
    :class:`UnknownParentBkpCodeError` if ``parent_code`` is set but does not
    refer to an existing row. We deliberately allow custom codes to nest
    under seeded ones; the migration uses RESTRICT FKs so seeds can never
    silently disappear from underneath them.
    """
    existing = await get_bkp_code(session, payload.code)
    if existing is not None:
        raise DuplicateBkpCodeError(f"eBKP-H Code '{payload.code}' existiert bereits")
    if payload.parent_code is not None:
        parent = await get_bkp_code(session, payload.parent_code)
        if parent is None:
            raise UnknownParentBkpCodeError(
                f"Übergeordneter eBKP-H Code '{payload.parent_code}' existiert nicht"
            )

    row = BkpCode(
        code=payload.code,
        parent_code=payload.parent_code,
        level=payload.level,
        label_de=payload.label_de,
        description=payload.description,
        is_seed=False,
    )
    session.add(row)
    await session.flush()
    return row


# ---- Internals --------------------------------------------------------------


def _build_tree(rows: Sequence[BkpCode]) -> list[BkpCodeTree]:
    """Materialise the parent/child forest from a flat row list."""
    nodes: dict[str, BkpCodeTree] = {
        r.code: BkpCodeTree(
            code=r.code,
            parent_code=r.parent_code,
            level=r.level,
            label_de=r.label_de,
            description=r.description,
            is_seed=r.is_seed,
            children=[],
        )
        for r in rows
    }
    roots: list[BkpCodeTree] = []
    for r in rows:
        node = nodes[r.code]
        if r.parent_code is None:
            roots.append(node)
        else:
            parent = nodes.get(r.parent_code)
            if parent is not None:
                parent.children.append(node)
            else:
                # Orphan (parent missing): treat as a root so it stays
                # browsable rather than silently disappearing. Should never
                # happen with the seeded data, but defence in depth.
                roots.append(node)
    return roots
