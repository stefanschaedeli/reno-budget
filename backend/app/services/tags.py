"""Business logic for Tags + polymorphic TagAssignment (Phase 11A — API layer).

The assignment-side invariant we enforce here: a :class:`~app.models.tag.Tag`
and its target (Project or CostItem) MUST belong to the same Object.
Cross-object assignment is rejected (translated to 422 by the route).
"""

from __future__ import annotations

import uuid

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cost import CostItem
from app.models.project import Project
from app.models.tag import Tag, TagAssignment, TagTargetType
from app.schemas.tag import TagCreate, TagUpdate


class TagServiceError(Exception):
    """Base class for tag business errors."""


class TagNotFoundError(TagServiceError):
    """The tag does not exist or belongs to another object."""


class TagConflictError(TagServiceError):
    """A tag with the same ``(object_id, key, value)`` already exists."""


class TagAssignmentScopeError(TagServiceError):
    """The tag and the assignment target do not share the same object."""


class TagAssignmentTargetMissingError(TagServiceError):
    """The assignment target row could not be found."""


# ---- Tags -------------------------------------------------------------------


async def create_tag(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
    payload: TagCreate,
) -> Tag:
    """Create a new tag. Raises :class:`TagConflictError` on duplicate."""
    tag = Tag(
        object_id=object_id,
        key=payload.key.strip(),
        value=payload.value.strip(),
        color=payload.color,
    )
    session.add(tag)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise TagConflictError(f"Tag '{payload.key}={payload.value}' existiert bereits") from exc
    return tag


async def list_tags(
    session: AsyncSession,
    *,
    object_id: uuid.UUID,
) -> list[Tag]:
    """All tags of an object, ordered by (key, value) for stable display."""
    stmt = select(Tag).where(Tag.object_id == object_id).order_by(Tag.key, Tag.value)
    return list((await session.execute(stmt)).scalars().all())


async def get_tag(session: AsyncSession, *, tag_id: uuid.UUID) -> Tag:
    """Fetch a single tag. Raises :class:`TagNotFoundError` if missing."""
    tag = await session.get(Tag, tag_id)
    if tag is None:
        raise TagNotFoundError("Tag nicht gefunden")
    return tag


async def update_tag(
    session: AsyncSession,
    *,
    tag_id: uuid.UUID,
    payload: TagUpdate,
) -> Tag:
    """Patch a tag. The uniqueness constraint still applies post-update."""
    tag = await get_tag(session, tag_id=tag_id)
    changes = payload.model_dump(exclude_unset=True)
    for field, value in changes.items():
        setattr(tag, field, value)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise TagConflictError(
            "Tag mit dieser Schlüssel/Wert-Kombination existiert bereits"
        ) from exc
    return tag


async def delete_tag(session: AsyncSession, *, tag_id: uuid.UUID) -> None:
    """Hard-delete a tag. Assignments cascade via FK ON DELETE CASCADE."""
    tag = await get_tag(session, tag_id=tag_id)
    await session.delete(tag)


# ---- Tag assignments --------------------------------------------------------


async def _target_object_id(
    session: AsyncSession,
    target_type: TagTargetType,
    target_id: uuid.UUID,
) -> uuid.UUID | None:
    """Return the ``object_id`` of the assignment target row, or ``None`` if absent."""
    if target_type == TagTargetType.PROJECT:
        row = await session.get(Project, target_id)
        return row.object_id if row is not None else None
    if target_type == TagTargetType.COST_ITEM:
        row = await session.get(CostItem, target_id)
        return row.object_id if row is not None else None
    return None


async def assign_tag(
    session: AsyncSession,
    *,
    tag_id: uuid.UUID,
    target_type: TagTargetType,
    target_id: uuid.UUID,
) -> TagAssignment:
    """Create a :class:`TagAssignment`. Cross-object assignments are rejected.

    Idempotent: re-assigning the same triple returns the existing row.
    """
    tag = await get_tag(session, tag_id=tag_id)
    target_object_id = await _target_object_id(session, target_type, target_id)
    if target_object_id is None:
        raise TagAssignmentTargetMissingError(
            f"Ziel ({target_type.value} {target_id}) nicht gefunden"
        )
    if target_object_id != tag.object_id:
        raise TagAssignmentScopeError("Tag und Ziel gehören zu unterschiedlichen Objekten")

    existing = await session.get(
        TagAssignment, {"tag_id": tag_id, "target_type": target_type, "target_id": target_id}
    )
    if existing is not None:
        return existing

    assignment = TagAssignment(tag_id=tag_id, target_type=target_type, target_id=target_id)
    session.add(assignment)
    await session.flush()
    return assignment


async def unassign_tag(
    session: AsyncSession,
    *,
    tag_id: uuid.UUID,
    target_type: TagTargetType,
    target_id: uuid.UUID,
) -> bool:
    """Remove a :class:`TagAssignment`. Returns ``True`` iff a row was deleted."""
    result = await session.execute(
        delete(TagAssignment).where(
            TagAssignment.tag_id == tag_id,
            TagAssignment.target_type == target_type,
            TagAssignment.target_id == target_id,
        )
    )
    return (result.rowcount or 0) > 0


async def list_tags_for_target(
    session: AsyncSession,
    *,
    target_type: TagTargetType,
    target_id: uuid.UUID,
) -> list[Tag]:
    """All tags assigned to ``(target_type, target_id)``."""
    stmt = (
        select(Tag)
        .join(TagAssignment, TagAssignment.tag_id == Tag.id)
        .where(
            TagAssignment.target_type == target_type,
            TagAssignment.target_id == target_id,
        )
        .order_by(Tag.key, Tag.value)
    )
    return list((await session.execute(stmt)).scalars().all())
