"""Pydantic request/response schemas for the cost-item / eBKP-H API (Phase 3).

Validation rules enforced here (so the service layer can trust its inputs):

* Money fields are :class:`Decimal` and serialised as strings to avoid float
  drift in transport (CHF is two decimals).
* Per-item allocations sum to exactly ``1000‰`` (delegated to
  :func:`app.services.allocations.validate_allocation_sum`).
* ``scope == UNIT`` REQUIRES explicit allocations; ``scope == SHARED`` may
  omit them (the service materialises from the object's Wertquoten).
* At least one amount (planned or actual) is required — a cost item with no
  monetary impact is a note, not a budget line.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.cost import CostItemPriority, CostItemScope, CostItemStatus
from app.services.allocations import (
    AllocationError,
    BkpAllocationError,
    validate_allocation_sum,
    validate_bkp_allocation_sum,
)

# ---- eBKP-H catalogue -------------------------------------------------------


class BkpCodeRead(BaseModel):
    """Flat read DTO for a single eBKP-H code."""

    model_config = ConfigDict(from_attributes=True)

    code: str
    parent_code: str | None
    level: int
    label_de: str
    description: str | None
    is_seed: bool


class BkpCodeTree(BaseModel):
    """Nested read DTO mirroring the eBKP-H parent/child hierarchy."""

    code: str
    parent_code: str | None
    level: int
    label_de: str
    description: str | None
    is_seed: bool
    children: list[BkpCodeTree] = Field(default_factory=list)


class BkpCodeCreate(BaseModel):
    """Payload for superuser-created custom codes (``is_seed = False``)."""

    code: str = Field(min_length=1, max_length=16)
    parent_code: str | None = Field(default=None, max_length=16)
    level: int = Field(ge=1, le=4)
    label_de: str = Field(min_length=1, max_length=255)
    description: str | None = None


# ---- Cost-item allocations --------------------------------------------------


class CostItemAllocationIn(BaseModel):
    """Inbound allocation row (unit + permille share)."""

    unit_id: uuid.UUID
    share_permille: int = Field(ge=0, le=1000)


class CostItemAllocationOut(BaseModel):
    """Outbound allocation row."""

    model_config = ConfigDict(from_attributes=True)

    unit_id: uuid.UUID
    share_permille: int


# ---- Multi-BKP allocations (Phase 11A) -------------------------------------


class BkpAllocationItem(BaseModel):
    """One BKP share on a cost item.

    A cost item may carry several of these to apportion its amount across
    multiple eBKP-H codes. Shares are integer permille and MUST sum to 1000
    across the item. See :class:`~app.models.cost.CostItemBkpAllocation`.
    """

    model_config = ConfigDict(from_attributes=True)

    bkp_code: str = Field(min_length=1, max_length=16)
    share_permille: int = Field(ge=0, le=1000)


# ---- Cost items -------------------------------------------------------------


_MONEY_FIELD = Field(default=None, ge=Decimal("0"), max_digits=12, decimal_places=2)


class _CostItemBase(BaseModel):
    """Common fields shared by create / update payloads."""

    model_config = ConfigDict(
        # Serialise Decimal as string in JSON output to preserve precision
        # across JS/JSON clients (which lack a native decimal type).
        json_encoders={Decimal: str},
    )

    # Nullable since Phase 11A — items may instead carry multi-BKP shares
    # via ``CostItemBkpAllocation``, or stay uncategorised entirely.
    bkp_code: str | None = Field(default=None, min_length=1, max_length=16)
    project_id: uuid.UUID | None = None
    npk_code: str | None = Field(default=None, max_length=32)
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: CostItemStatus = CostItemStatus.IDEA
    priority: CostItemPriority = CostItemPriority.MED
    planned_year: int | None = Field(default=None, ge=1900, le=2200)
    planned_amount_chf: Decimal | None = _MONEY_FIELD
    actual_amount_chf: Decimal | None = _MONEY_FIELD
    actual_date: date | None = None
    lifespan_years: int | None = Field(default=None, ge=0, le=200)
    warranty_until: date | None = None
    scope: CostItemScope = CostItemScope.SHARED


class CostItemCreate(_CostItemBase):
    """Create payload. Allocations optional only for ``SHARED`` scope.

    XOR rule (Phase 11A): a cost item may carry **either** a singleton
    ``bkp_code`` (legacy / single-BKP shape) **or** a non-empty
    ``bkp_allocations`` list (multi-BKP shape) — never both. Submitting
    both is a 422 because the data model has no defensible interpretation
    of "single BKP=D *and* split 60/40 across D and E". An empty list is
    equivalent to "no multi-BKP shares", which IS compatible with a
    singleton ``bkp_code``.
    """

    allocations: list[CostItemAllocationIn] | None = None
    bkp_allocations: list[BkpAllocationItem] | None = None

    @model_validator(mode="after")
    def _check_invariants(self) -> CostItemCreate:
        _validate_amounts(self.planned_amount_chf, self.actual_amount_chf)
        _validate_allocations_for_scope(self.scope, self.allocations)
        _validate_bkp_xor(self.bkp_code, self.bkp_allocations)
        return self


class CostItemUpdate(BaseModel):
    """Patch payload. Any field may be omitted; allocations replace wholesale.

    Note: we do NOT re-validate "at least one amount" here because the merged
    record (existing + patch) is what matters; the service layer re-checks
    after merging. Allocation sum, however, IS checked: if the caller
    submits an allocation list it must be valid in isolation.
    """

    model_config = ConfigDict(json_encoders={Decimal: str})

    bkp_code: str | None = Field(default=None, min_length=1, max_length=16)
    project_id: uuid.UUID | None = None
    npk_code: str | None = Field(default=None, max_length=32)
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    status: CostItemStatus | None = None
    priority: CostItemPriority | None = None
    planned_year: int | None = Field(default=None, ge=1900, le=2200)
    planned_amount_chf: Decimal | None = _MONEY_FIELD
    actual_amount_chf: Decimal | None = _MONEY_FIELD
    actual_date: date | None = None
    lifespan_years: int | None = Field(default=None, ge=0, le=200)
    warranty_until: date | None = None
    scope: CostItemScope | None = None
    allocations: list[CostItemAllocationIn] | None = None
    bkp_allocations: list[BkpAllocationItem] | None = None

    @model_validator(mode="after")
    def _check_allocations(self) -> CostItemUpdate:
        """Validate allocation sums + the singleton-vs-multi BKP XOR rule.

        XOR rule: when the caller submits a non-empty ``bkp_allocations`` list
        AND also a non-NULL ``bkp_code`` in the same patch, we reject (422).
        Sending ``bkp_code: null`` alongside a non-empty list is the legitimate
        "switch from single→multi" flow. Sending an empty list together with a
        new singleton is the legitimate "switch from multi→single" flow.
        """
        if self.allocations is not None:
            try:
                validate_allocation_sum(a.share_permille for a in self.allocations)
            except AllocationError as exc:
                raise ValueError(str(exc)) from exc
        if self.bkp_allocations is not None:
            try:
                validate_bkp_allocation_sum(a.share_permille for a in self.bkp_allocations)
            except BkpAllocationError as exc:
                raise ValueError(str(exc)) from exc
            if self.bkp_code is not None and self.bkp_allocations:
                raise ValueError(
                    "bkp_code und bkp_allocations dürfen nicht gleichzeitig gesetzt sein"
                )
        return self


class CostItemRead(_CostItemBase):
    """Outbound DTO including server-assigned fields and allocations."""

    model_config = ConfigDict(
        from_attributes=True,
        json_encoders={Decimal: str},
    )

    id: uuid.UUID
    object_id: uuid.UUID
    project_id: uuid.UUID | None = None
    created_by: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
    allocations: list[CostItemAllocationOut]
    bkp_allocations: list[BkpAllocationItem] = Field(default_factory=list)
    # Phase 11A list-view optimisation: populated only when the list endpoint
    # is called with ``?include_tag_ids=true``; ``None`` otherwise (NOT an
    # empty list — distinguishes "not requested" from "no tags assigned").
    tag_ids: list[uuid.UUID] | None = None
    # Phase 11B: same pattern for lot membership ids — ``None`` means
    # "not requested", ``[]`` means "no lot membership".
    lot_ids: list[uuid.UUID] | None = None


# ---- Filters / list query ---------------------------------------------------


class CostItemFilter(BaseModel):
    """Query-string filter set for the list endpoint.

    All fields are optional; combining them is AND-ed. ``bkp_code`` is a
    *prefix* match so callers can request "everything under D" with a single
    character; this matches the way the eBKP-H tree is browsed in the UI.
    """

    status: CostItemStatus | None = None
    priority: CostItemPriority | None = None
    planned_year: int | None = Field(default=None, ge=1900, le=2200)
    bkp_code: str | None = Field(default=None, min_length=1, max_length=16)
    unit_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    # Phase 12: surface items that haven't been assigned to any project yet.
    # Mutually exclusive with ``project_id``.
    project_id_is_null: bool = False
    # Multi-value: pass ``?tag_id=<a>&tag_id=<b>`` for OR semantics.
    tag_id: list[uuid.UUID] | None = Field(default=None)
    # Phase 11B: scope to a single lot (any-of would be over-engineering for
    # the UI which only ever filters by one lot at a time).
    lot_id: uuid.UUID | None = None
    q: str | None = Field(default=None, max_length=200)
    sort: str | None = Field(default=None, max_length=64)
    # Phase 11A: when true, the list endpoint includes the per-item ``tag_ids``
    # in each response row (batched, single extra query). Disabled by default
    # so list payloads stay small for callers that don't render chips.
    include_tag_ids: bool = False
    # Phase 11B: same pattern for lot membership ids.
    include_lot_ids: bool = False

    @model_validator(mode="after")
    def _project_filters_mutually_exclusive(self) -> "CostItemFilter":
        if self.project_id is not None and self.project_id_is_null:
            raise ValueError(
                "project_id and project_id_is_null are mutually exclusive",
            )
        return self


# ---- Internal helpers -------------------------------------------------------


def _validate_amounts(planned: Decimal | None, actual: Decimal | None) -> None:
    """Reject cost items with no monetary value (planned AND actual null)."""
    if planned is None and actual is None:
        raise ValueError("Mindestens ein Betrag (geplant oder effektiv) ist erforderlich")


def _validate_bkp_xor(
    bkp_code: str | None, bkp_allocations: list[BkpAllocationItem] | None
) -> None:
    """Enforce the singleton vs. multi-BKP XOR rule on create payloads.

    A non-empty multi-BKP list combined with a non-NULL singleton code is
    ambiguous — reject it (422). An empty list is equivalent to "no
    multi-BKP shares" and is silently dropped (treated as ``None``).
    """
    if bkp_allocations is not None and bkp_allocations:
        try:
            validate_bkp_allocation_sum(a.share_permille for a in bkp_allocations)
        except BkpAllocationError as exc:
            raise ValueError(str(exc)) from exc
        if bkp_code is not None:
            raise ValueError("bkp_code und bkp_allocations dürfen nicht gleichzeitig gesetzt sein")


def _validate_allocations_for_scope(
    scope: CostItemScope, allocations: list[CostItemAllocationIn] | None
) -> None:
    """Per-scope allocation requirements.

    UNIT scope MUST list explicit allocations; SHARED MAY omit them (service
    materialises from Wertquoten). When present in either case, allocations
    must sum to exactly 1000‰.
    """
    if scope == CostItemScope.UNIT and not allocations:
        raise ValueError("Einheit-spezifische Position erfordert explizite Aufteilung(en)")
    if allocations is not None:
        try:
            validate_allocation_sum(a.share_permille for a in allocations)
        except AllocationError as exc:
            raise ValueError(str(exc)) from exc
