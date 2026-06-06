"""Pydantic schemas for Renofond projections and contribution tracking (Phase 5).

Money is :class:`Decimal` end-to-end and serialised as a string at the API
boundary, matching the budget DTOs. Years are plain integers.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.models.object import ObjectRole

_MONEY_CONFIG = ConfigDict(json_encoders={Decimal: str})


class ContributionCreate(BaseModel):
    """Body for ``POST /objects/{id}/renofond/contributions``."""

    model_config = _MONEY_CONFIG

    year: int = Field(ge=1900, le=2200)
    amount_chf: Decimal = Field(ge=Decimal("0"), max_digits=12, decimal_places=2)
    note: str | None = Field(default=None, max_length=255)


class ContributionRead(BaseModel):
    """One actual deposit row."""

    model_config = ConfigDict(from_attributes=True, json_encoders={Decimal: str})

    id: uuid.UUID
    object_id: uuid.UUID
    year: int
    amount_chf: Decimal
    note: str | None
    created_at: datetime


class ProjectionRow(BaseModel):
    """Per-year row of the Renofond projection."""

    model_config = _MONEY_CONFIG

    year: int
    # Required contribution for this year (target deposit per Phase-4 math).
    required_contribution_chf: Decimal
    # Actual contributions recorded for this year (sum of all deposits).
    actual_contribution_chf: Decimal
    # Inflated planned spend booked against the reserve in this year.
    planned_spend_chf: Decimal
    # Projected reserve balance at the *end* of this year.
    balance_chf: Decimal
    # Cumulative inflated planned spend up to and including this year.
    cumulative_planned_chf: Decimal
    # True iff ``balance_chf < 0`` — the projection shows underfunding.
    is_underfunded: bool


class UnderfundingYear(BaseModel):
    """Convenience record for years where the projection runs into the red."""

    model_config = _MONEY_CONFIG

    year: int
    shortfall_chf: Decimal


class ProjectionResponse(BaseModel):
    """Full projection over the planning horizon."""

    model_config = _MONEY_CONFIG

    object_id: uuid.UUID
    current_year: int
    horizon_until_year: int
    inflation_rate_percent: Decimal
    initial_reserve_chf: Decimal
    required_per_year_chf: Decimal
    rows: list[ProjectionRow]
    underfunding_years: list[UnderfundingYear]
    scope_pro_rated: bool


class ContributionListResponse(BaseModel):
    """Wrapper for ``GET /contributions``.

    ``my_role`` lets the frontend gate the add/delete UI without a
    second round-trip — only OWNER may mutate.
    """

    items: list[ContributionRead]
    my_role: ObjectRole
