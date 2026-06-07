"""Helper for iterating BKP shares on a cost item (Phase 11A).

A cost item can carry BKP attribution in three shapes (in priority order):

1. **Multi-BKP**: one or more :class:`CostItemBkpAllocation` rows whose
   ``share_permille`` values sum to 1000 — the source of truth when set.
2. **Single-BKP**: the legacy ``CostItem.bkp_code`` column carries the full
   1000‰ share.
3. **Uncategorised**: neither shape is set (``bkp_code`` is NULL and no
   allocations) — the item lives in a synthetic ``_uncat`` bucket so it
   still appears in roll-ups.

Aggregation code uses :func:`iter_bkp_shares` to apportion amounts uniformly
regardless of which shape the underlying item uses.
"""

from __future__ import annotations

from app.models.cost import CostItem


def iter_bkp_shares(item: CostItem) -> list[tuple[str | None, int]]:
    """Return ``(bkp_code, share_permille)`` tuples summing to 1000.

    Priority:

    1. If ``item.bkp_allocations`` is non-empty → return its rows.
    2. Else if ``item.bkp_code`` is set → ``[(bkp_code, 1000)]``.
    3. Else → ``[(None, 1000)]`` (uncategorised sentinel).
    """
    if item.bkp_allocations:
        return [(a.bkp_code, a.share_permille) for a in item.bkp_allocations]
    if item.bkp_code:
        return [(item.bkp_code, 1000)]
    return [(None, 1000)]


__all__ = ["iter_bkp_shares"]
