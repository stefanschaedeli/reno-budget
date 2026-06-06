"""Pydantic request/response schemas for the object/unit/membership API.

Validation rules baked in here (so they're enforced before the service layer
sees them):

* Unit labels are 1..64 characters.
* Wertquoten are integer permille in ``0..1000``.
* Membership roles are restricted to the :class:`ObjectRole` enum values.
* On object creation, the ``units`` list MUST sum to 1000‰ (cross-row check
  delegated to :func:`app.services.allocations.validate_wertquoten_sum`).
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, model_validator

from app.models.object import ObjectRole, ObjectType
from app.services.allocations import WertquoteError, validate_wertquoten_sum

# ---- Units ------------------------------------------------------------------


class UnitCreate(BaseModel):
    label: str = Field(min_length=1, max_length=64)
    wertquote_permille: int = Field(ge=0, le=1000)
    area_m2: int | None = Field(default=None, ge=0)


class UnitUpdate(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=64)
    wertquote_permille: int | None = Field(default=None, ge=0, le=1000)
    area_m2: int | None = Field(default=None, ge=0)


class UnitPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    object_id: uuid.UUID
    label: str
    wertquote_permille: int
    area_m2: int | None


# ---- Objects ----------------------------------------------------------------


class ObjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    year_built: int | None = Field(default=None, ge=1500, le=2100)
    type: ObjectType
    planning_horizon_years: int = Field(default=30, ge=1, le=100)
    units: list[UnitCreate] = Field(min_length=1)

    @model_validator(mode="after")
    def _check_wertquoten(self) -> ObjectCreate:
        try:
            validate_wertquoten_sum(u.wertquote_permille for u in self.units)
        except WertquoteError as exc:
            raise ValueError(str(exc)) from exc
        # SFH must have exactly one 1000‰ unit; this catches user input mistakes early.
        if self.type == ObjectType.SFH and (
            len(self.units) != 1 or self.units[0].wertquote_permille != 1000
        ):
            raise ValueError(
                "Einfamilienhaus muss genau eine Einheit mit 1000‰ enthalten"
            )
        return self


class ObjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = Field(default=None, max_length=255)
    year_built: int | None = Field(default=None, ge=1500, le=2100)
    planning_horizon_years: int | None = Field(default=None, ge=1, le=100)


class ObjectPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    address: str | None
    year_built: int | None
    type: ObjectType
    planning_horizon_years: int
    created_at: datetime


class ObjectDetail(ObjectPublic):
    units: list[UnitPublic]


# ---- Memberships ------------------------------------------------------------


class MembershipPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    object_id: uuid.UUID
    role: ObjectRole
    scope_unit_ids: list[uuid.UUID]


class MembershipUpdate(BaseModel):
    role: ObjectRole | None = None
    scope_unit_ids: list[uuid.UUID] | None = None


class InviteToObjectRequest(BaseModel):
    email: EmailStr
    role: ObjectRole
    scope_unit_ids: list[uuid.UUID] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_owner_unscoped(self) -> InviteToObjectRequest:
        if self.role == ObjectRole.OWNER and self.scope_unit_ids:
            raise ValueError("OWNER-Mitgliedschaft darf nicht unit-eingeschränkt sein")
        return self
