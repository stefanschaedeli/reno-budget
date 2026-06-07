"""Unit tests for :func:`iter_bkp_shares` and ``validate_bkp_allocation_sum``."""

from __future__ import annotations

import pytest
from app.models.cost import CostItem, CostItemBkpAllocation
from app.services.allocations import (
    BKP_ALLOCATION_TOTAL_PERMILLE,
    BkpAllocationError,
    validate_bkp_allocation_sum,
)
from app.services.bkp_shares import iter_bkp_shares


def _bare_cost_item(bkp_code: str | None) -> CostItem:
    """Build an unpersisted CostItem with empty bkp_allocations."""
    item = CostItem(bkp_code=bkp_code, title="x")
    item.bkp_allocations = []
    return item


class TestIterBkpShares:
    def test_uses_multi_bkp_allocations_when_present(self) -> None:
        item = _bare_cost_item(None)
        item.bkp_allocations = [
            CostItemBkpAllocation(bkp_code="D", share_permille=600),
            CostItemBkpAllocation(bkp_code="E", share_permille=400),
        ]
        assert iter_bkp_shares(item) == [("D", 600), ("E", 400)]

    def test_multi_bkp_takes_priority_over_bkp_code_column(self) -> None:
        item = _bare_cost_item("Z")  # legacy column ignored
        item.bkp_allocations = [
            CostItemBkpAllocation(bkp_code="D", share_permille=1000),
        ]
        assert iter_bkp_shares(item) == [("D", 1000)]

    def test_falls_back_to_singleton_bkp_code(self) -> None:
        item = _bare_cost_item("D01")
        assert iter_bkp_shares(item) == [("D01", 1000)]

    def test_uncategorised_when_neither_set(self) -> None:
        item = _bare_cost_item(None)
        assert iter_bkp_shares(item) == [(None, 1000)]


class TestValidateBkpAllocationSum:
    def test_empty_iterable_is_allowed(self) -> None:
        # Empty means "no multi-BKP split", which is a valid configuration.
        validate_bkp_allocation_sum([])

    def test_single_full_share_passes(self) -> None:
        validate_bkp_allocation_sum([BKP_ALLOCATION_TOTAL_PERMILLE])

    def test_balanced_multi_share_passes(self) -> None:
        validate_bkp_allocation_sum([600, 400])

    @pytest.mark.parametrize("values", [[400, 400], [500, 600], [999]])
    def test_sum_not_1000_raises(self, values: list[int]) -> None:
        with pytest.raises(BkpAllocationError, match="1000"):
            validate_bkp_allocation_sum(values)

    @pytest.mark.parametrize("bad", [-1, 1001])
    def test_out_of_range_value_raises(self, bad: int) -> None:
        with pytest.raises(BkpAllocationError, match="ausserhalb"):
            validate_bkp_allocation_sum(
                [bad, BKP_ALLOCATION_TOTAL_PERMILLE - bad]
            )
