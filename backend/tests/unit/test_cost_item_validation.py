"""Unit tests for cost-item Pydantic validators.

Covers scope-vs-allocations rules, money invariants, and decimal handling.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from app.models.cost import CostItemScope
from app.schemas.cost import (
    CostItemAllocationIn,
    CostItemCreate,
    CostItemUpdate,
)


def _unit_id() -> uuid.UUID:
    return uuid.uuid4()


def _valid_alloc(unit_id: uuid.UUID, share: int = 1000) -> CostItemAllocationIn:
    return CostItemAllocationIn(unit_id=unit_id, share_permille=share)


class TestCostItemCreate:
    def test_shared_without_allocations_ok(self) -> None:
        item = CostItemCreate(
            bkp_code="D",
            title="Heizung",
            planned_amount_chf=Decimal("12345.67"),
            scope=CostItemScope.SHARED,
        )
        assert item.allocations is None

    def test_shared_with_valid_allocations_ok(self) -> None:
        u1, u2 = _unit_id(), _unit_id()
        CostItemCreate(
            bkp_code="D",
            title="Heizung",
            planned_amount_chf=Decimal("100.00"),
            scope=CostItemScope.SHARED,
            allocations=[_valid_alloc(u1, 600), _valid_alloc(u2, 400)],
        )

    def test_unit_scope_requires_allocations(self) -> None:
        with pytest.raises(ValueError, match="explizite Aufteilung"):
            CostItemCreate(
                bkp_code="D",
                title="Bad",
                planned_amount_chf=Decimal("1.00"),
                scope=CostItemScope.UNIT,
            )

    def test_allocations_must_sum_to_1000(self) -> None:
        u1 = _unit_id()
        with pytest.raises(ValueError, match="1000"):
            CostItemCreate(
                bkp_code="D",
                title="Bad",
                planned_amount_chf=Decimal("1.00"),
                scope=CostItemScope.UNIT,
                allocations=[_valid_alloc(u1, 999)],
            )

    def test_requires_at_least_one_amount(self) -> None:
        with pytest.raises(ValueError, match="Betrag"):
            CostItemCreate(
                bkp_code="D",
                title="Empty",
                scope=CostItemScope.SHARED,
            )

    def test_negative_amount_rejected(self) -> None:
        with pytest.raises(ValueError):
            CostItemCreate(
                bkp_code="D",
                title="Negative",
                planned_amount_chf=Decimal("-1.00"),
                scope=CostItemScope.SHARED,
            )

    def test_decimal_round_trip_preserves_precision(self) -> None:
        item = CostItemCreate(
            bkp_code="D",
            title="Cents",
            planned_amount_chf=Decimal("12.34"),
            actual_amount_chf=Decimal("0.01"),
            scope=CostItemScope.SHARED,
        )
        assert item.planned_amount_chf == Decimal("12.34")
        assert item.actual_amount_chf == Decimal("0.01")


class TestCostItemUpdate:
    def test_empty_patch_is_valid(self) -> None:
        # No fields set: pure no-op patch. The service re-validates merged
        # invariants — the schema must not reject an empty update.
        CostItemUpdate()

    def test_allocations_alone_still_validated(self) -> None:
        u1 = _unit_id()
        with pytest.raises(ValueError, match="1000"):
            CostItemUpdate(allocations=[_valid_alloc(u1, 500)])

    def test_valid_allocations_pass(self) -> None:
        u1, u2 = _unit_id(), _unit_id()
        CostItemUpdate(
            allocations=[_valid_alloc(u1, 700), _valid_alloc(u2, 300)],
        )
