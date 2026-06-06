"""Unit tests for Wertquoten validation."""

from __future__ import annotations

import pytest
from app.services.allocations import (
    WERTQUOTE_TOTAL_PERMILLE,
    WertquoteError,
    validate_wertquoten_sum,
)


class TestValidateWertquotenSum:
    def test_single_unit_at_1000_passes(self) -> None:
        validate_wertquoten_sum([WERTQUOTE_TOTAL_PERMILLE])

    def test_balanced_multi_unit_passes(self) -> None:
        validate_wertquoten_sum([250, 250, 250, 250])

    def test_uneven_balanced_passes(self) -> None:
        validate_wertquoten_sum([333, 333, 334])

    def test_empty_iterable_raises(self) -> None:
        with pytest.raises(WertquoteError, match="Mindestens eine Einheit"):
            validate_wertquoten_sum([])

    @pytest.mark.parametrize("values", [[400, 400], [500, 600], [1, 1, 1]])
    def test_sum_not_1000_raises(self, values: list[int]) -> None:
        with pytest.raises(WertquoteError, match="1000"):
            validate_wertquoten_sum(values)

    @pytest.mark.parametrize("bad", [-1, 1001, 2000])
    def test_out_of_range_value_raises(self, bad: int) -> None:
        with pytest.raises(WertquoteError, match="ausserhalb"):
            validate_wertquoten_sum([bad, WERTQUOTE_TOTAL_PERMILLE - bad])
