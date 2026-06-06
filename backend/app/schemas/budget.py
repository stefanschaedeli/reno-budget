"""Pydantic response schemas for the budget aggregation API (Phase 4).

Money is :class:`Decimal` end-to-end. Years are plain integers (Gregorian
calendar). All aggregate values are server-rounded to two decimals at the
API boundary; internal math runs at full Decimal precision.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.cost import CostItemPriority, CostItemStatus
from app.models.object import ContributionMode, ObjectRole

_MONEY_CONFIG = ConfigDict(json_encoders={Decimal: str})


class TimelineBucket(BaseModel):
    """Planned/actual sums for a single (year, breakdown-key) pair."""

    model_config = _MONEY_CONFIG

    planned_chf: Decimal
    actual_chf: Decimal


class TimelineRow(BaseModel):
    """Aggregated planned/actual sums for a single calendar year."""

    model_config = _MONEY_CONFIG

    year: int
    planned_chf: Decimal
    planned_inflated_chf: Decimal
    actual_chf: Decimal
    by_bkp_group: dict[str, TimelineBucket] = Field(default_factory=dict)
    by_unit: dict[uuid.UUID, TimelineBucket] = Field(default_factory=dict)
    by_status: dict[CostItemStatus, TimelineBucket] = Field(default_factory=dict)
    by_priority: dict[CostItemPriority, TimelineBucket] = Field(default_factory=dict)


class TimelineResponse(BaseModel):
    """Per-year planning timeline for an object."""

    model_config = _MONEY_CONFIG

    object_id: uuid.UUID
    inflated: bool
    inflation_rate_percent: Decimal
    current_year: int
    horizon_until_year: int
    scope_pro_rated: bool
    rows: list[TimelineRow]


class ReserveLumpSum(BaseModel):
    """One inflated lump-sum the OWNER must have ready by ``year``."""

    model_config = _MONEY_CONFIG

    year: int
    amount_chf: Decimal


class ReserveResponse(BaseModel):
    """Required-contribution plan derived from the timeline."""

    model_config = _MONEY_CONFIG

    object_id: uuid.UUID
    contribution_mode: ContributionMode
    horizon_years: int
    inflation_rate_percent: Decimal
    initial_reserve_chf: Decimal
    total_planned_inflated_chf: Decimal
    required_total_chf: Decimal
    required_per_year_chf: Decimal
    required_per_month_chf: Decimal
    required_lump_sums: list[ReserveLumpSum]
    scope_pro_rated: bool


class FinanceOverviewItem(BaseModel):
    """One per-object roll-up row in the cross-object finance overview."""

    model_config = _MONEY_CONFIG

    object_id: uuid.UUID
    name: str
    role: ObjectRole
    total_planned_inflated_chf: Decimal
    total_actual_chf: Decimal
    required_per_year_chf: Decimal
    scope_pro_rated: bool


class FinanceOverviewResponse(BaseModel):
    """Wrapper around the list of objects the user belongs to."""

    items: list[FinanceOverviewItem]
