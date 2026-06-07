"""Validators for Wertquoten and per-cost-item allocations.

Both checks share the same mathematical shape: a set of integer-permille
values that MUST sum to exactly 1000. Using permille (rather than e.g. a
Decimal fraction) keeps the invariant exact and trivial to check.

These helpers are intentionally pure functions on iterables so they can be
re-used from API request validators, repository pre-save hooks, and tests
without dragging in the database session.
"""

from __future__ import annotations

from collections.abc import Iterable

WERTQUOTE_TOTAL_PERMILLE = 1000
ALLOCATION_TOTAL_PERMILLE = 1000
BKP_ALLOCATION_TOTAL_PERMILLE = 1000


class WertquoteError(ValueError):
    """Raised when the Wertquoten of an object do not sum to 1000."""


class AllocationError(ValueError):
    """Raised when per-cost-item allocations do not sum to 1000.

    Distinct from :class:`WertquoteError` so callers (and tests) can target
    cost-item misconfiguration without conflating it with object-level
    Wertquote invariants — the user-facing German messages differ too.
    """


class BkpAllocationError(ValueError):
    """Raised when per-cost-item BKP allocations do not sum to 1000."""


def validate_wertquoten_sum(permille_values: Iterable[int]) -> None:
    """Raise :class:`WertquoteError` unless the values sum to exactly 1000.

    Each value must also be in ``0..1000`` (a single unit may not exceed the
    whole). Empty iterables fail loudly — an object with zero units is not
    representable in the domain.
    """
    values = list(permille_values)
    if not values:
        raise WertquoteError("Mindestens eine Einheit ist erforderlich")
    for v in values:
        if not 0 <= v <= WERTQUOTE_TOTAL_PERMILLE:
            raise WertquoteError(
                f"Wertquote {v}‰ liegt ausserhalb des erlaubten Bereichs (0-1000‰)"
            )
    total = sum(values)
    if total != WERTQUOTE_TOTAL_PERMILLE:
        raise WertquoteError(f"Summe der Wertquoten muss 1000‰ ergeben, aktuell {total}‰")


def validate_allocation_sum(permille_values: Iterable[int]) -> None:
    """Raise :class:`AllocationError` unless the allocations sum to exactly 1000.

    Mirrors :func:`validate_wertquoten_sum` but uses the cost-item-specific
    error class and German wording. Empty iterables fail loudly — a cost item
    with no allocations cannot be attributed to any unit and would silently
    fall out of every report.
    """
    values = list(permille_values)
    if not values:
        raise AllocationError("Mindestens eine Einheit-Aufteilung ist erforderlich")
    for v in values:
        if not 0 <= v <= ALLOCATION_TOTAL_PERMILLE:
            raise AllocationError(
                f"Aufteilung {v}‰ liegt ausserhalb des erlaubten Bereichs (0-1000‰)"
            )
    total = sum(values)
    if total != ALLOCATION_TOTAL_PERMILLE:
        raise AllocationError(f"Summe der Aufteilungen muss 1000‰ ergeben, aktuell {total}‰")


def validate_bkp_allocation_sum(permille_values: Iterable[int]) -> None:
    """Raise :class:`BkpAllocationError` unless the BKP shares sum to 1000.

    Mirrors :func:`validate_allocation_sum` but for the per-cost-item BKP
    split (Phase 11A). An **empty** iterable is allowed — it represents the
    "no multi-BKP split, use the singleton ``CostItem.bkp_code`` instead"
    case. When at least one row is present, the sum MUST be exactly 1000‰
    and every value MUST be in 0..1000.
    """
    values = list(permille_values)
    if not values:
        # Empty means "no multi-BKP split"; callers fall back to the legacy
        # single-column ``bkp_code``. That is a valid configuration.
        return
    for v in values:
        if not 0 <= v <= BKP_ALLOCATION_TOTAL_PERMILLE:
            raise BkpAllocationError(
                f"BKP-Aufteilung {v}‰ liegt ausserhalb des erlaubten Bereichs (0-1000‰)"
            )
    total = sum(values)
    if total != BKP_ALLOCATION_TOTAL_PERMILLE:
        raise BkpAllocationError(
            f"Summe der BKP-Aufteilungen muss 1000‰ ergeben, aktuell {total}‰"
        )
