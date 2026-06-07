"""Business logic for Suppliers (Phase 11C — API layer).

Pure CRUD around :class:`~app.models.supplier.Supplier` with archive
semantics. RBAC is enforced by the calling router; this service trusts
that the caller has already proven the right to read/write the
underlying object.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.supplier import Supplier
from app.models.user import User
from app.schemas.supplier import SupplierCreate, SupplierUpdate


class SupplierServiceError(Exception):
    """Base class for supplier business errors."""


class SupplierNotFoundError(SupplierServiceError):
    """The supplier does not exist or belongs to another object."""


class SupplierInUseError(SupplierServiceError):
    """The supplier cannot be deleted because quotes reference it."""


async def create_supplier(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    actor: User,
    payload: SupplierCreate,
) -> Supplier:
    """Create a new supplier under ``object_id`` owned by ``actor``."""
    supplier = Supplier(
        object_id=object_id,
        name=payload.name.strip(),
        contact_email=payload.contact_email,
        contact_phone=payload.contact_phone,
        address=payload.address,
        notes=payload.notes,
        created_by=actor.id,
    )
    session.add(supplier)
    await session.flush()
    return supplier


async def list_suppliers(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    include_archived: bool = False,
) -> list[Supplier]:
    """List suppliers of an object. Archived rows are excluded by default."""
    stmt = select(Supplier).where(Supplier.object_id == object_id)
    if not include_archived:
        stmt = stmt.where(Supplier.archived_at.is_(None))
    stmt = stmt.order_by(Supplier.name)
    return list((await session.execute(stmt)).scalars().all())


async def get_supplier(
    session: AsyncSession, *, supplier_id: uuid.UUID
) -> Supplier:
    """Fetch a single supplier. Raises if missing."""
    supplier = await session.get(Supplier, supplier_id)
    if supplier is None:
        raise SupplierNotFoundError("Lieferant nicht gefunden")
    return supplier


async def update_supplier(
    session: AsyncSession,
    *,
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
) -> Supplier:
    """Patch a supplier. Only the fields present in the payload are touched."""
    supplier = await get_supplier(session, supplier_id=supplier_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(supplier, field, value)
    await session.flush()
    return supplier


async def archive_supplier(
    session: AsyncSession, *, supplier_id: uuid.UUID
) -> Supplier:
    """Soft-archive a supplier. Idempotent."""
    supplier = await get_supplier(session, supplier_id=supplier_id)
    if supplier.archived_at is None:
        supplier.archived_at = datetime.now(tz=UTC)
        await session.flush()
    return supplier


async def delete_supplier(
    session: AsyncSession, *, supplier_id: uuid.UUID
) -> None:
    """Hard-delete a supplier. RESTRICTed by FK if any quote references it."""
    supplier = await get_supplier(session, supplier_id=supplier_id)
    try:
        await session.delete(supplier)
        await session.flush()
    except IntegrityError as exc:
        raise SupplierInUseError(
            "Lieferant kann nicht gelöscht werden — Angebote referenzieren ihn"
        ) from exc
