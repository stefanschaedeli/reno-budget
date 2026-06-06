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


class WertquoteError(ValueError):
    """Raised when the Wertquoten of an object do not sum to 1000."""


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
        raise WertquoteError(
            f"Summe der Wertquoten muss 1000‰ ergeben, aktuell {total}‰"
        )
