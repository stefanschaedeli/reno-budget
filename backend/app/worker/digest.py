"""Weekly reminder-digest emails for the Reno-Budget worker.

For each active user we collect three signal types and, if at least one
fires, send a single German digest e-mail. The mailer is the same Phase-1
:mod:`app.services.mailer` used elsewhere (so test mode captures messages
in memory).

Signals (per user, aggregated across all objects they can see):

1. **Urgent / high cost items** with a ``planned_year`` of the current
   year or earlier whose ``status`` is not ``COMPLETED`` / ``CANCELLED``.
2. **Renofond underfunding** within the next 5 years. Computed via
   :func:`app.services.renofond.compute_projection` per object the user
   is an OWNER of.
3. **Attachments uploaded in the last 7 days by other users** on objects
   where this user is OWNER.

Audit
-----
One ``worker.digest_sent`` event per recipient, scoped per user. Users with
nothing to report receive no e-mail (and no audit row).
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.core.db as db_module
from app.models.attachment import Attachment, AttachmentTargetType
from app.models.cost import CostItem, CostItemPriority, CostItemStatus
from app.models.object import Object, ObjectMembership, ObjectRole
from app.models.user import User
from app.services import audit as audit_svc
from app.services.mailer import send_email
from app.services.rbac import ObjectAccess
from app.services.renofond import compute_projection

logger = logging.getLogger(__name__)

_UNDERFUNDING_HORIZON_YEARS = 5
_ATTACHMENT_LOOKBACK_DAYS = 7
_PRIORITIES = (CostItemPriority.HIGH, CostItemPriority.URGENT)
_OPEN_STATUSES = (
    CostItemStatus.IDEA,
    CostItemStatus.PLANNED,
    CostItemStatus.IN_PROGRESS,
)


@dataclass(slots=True)
class _DigestPayload:
    """Per-user collected signals; emptiness check via :meth:`is_empty`."""

    urgent_items: list[tuple[str, CostItem]] = field(default_factory=list)
    underfunding: list[tuple[str, int, Decimal]] = field(default_factory=list)
    new_attachments: list[tuple[str, Attachment, str]] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not (self.urgent_items or self.underfunding or self.new_attachments)


async def _user_memberships(
    session: AsyncSession, user_id: uuid.UUID
) -> list[ObjectMembership]:
    rows = (
        await session.execute(
            select(ObjectMembership).where(ObjectMembership.user_id == user_id)
        )
    ).scalars().all()
    return list(rows)


async def _object_name(session: AsyncSession, object_id: uuid.UUID) -> str:
    obj = (
        await session.execute(select(Object).where(Object.id == object_id))
    ).scalar_one_or_none()
    return obj.name if obj is not None else str(object_id)


async def _collect_urgent_items(
    session: AsyncSession, object_id: uuid.UUID, object_name: str
) -> list[tuple[str, CostItem]]:
    current_year = date.today().year
    rows = (
        await session.execute(
            select(CostItem).where(
                CostItem.object_id == object_id,
                CostItem.priority.in_(_PRIORITIES),
                CostItem.status.in_(_OPEN_STATUSES),
                CostItem.planned_year.is_not(None),
                CostItem.planned_year <= current_year,
            )
        )
    ).scalars().all()
    return [(object_name, item) for item in rows]


async def _collect_underfunding(
    session: AsyncSession,
    object_id: uuid.UUID,
    object_name: str,
    *,
    membership_id: uuid.UUID,
) -> list[tuple[str, int, Decimal]]:
    current_year = date.today().year
    cutoff = current_year + _UNDERFUNDING_HORIZON_YEARS
    projection = await compute_projection(
        session,
        object_id,
        access=ObjectAccess(
            membership_id=membership_id,
            role=ObjectRole.OWNER,
            allowed_unit_ids=None,
        ),
    )
    return [
        (object_name, u.year, u.shortfall_chf)
        for u in projection.underfunding_years
        if u.year <= cutoff
    ]


async def _collect_new_attachments(
    session: AsyncSession,
    object_id: uuid.UUID,
    object_name: str,
    *,
    user_id: uuid.UUID,
) -> list[tuple[str, Attachment, str]]:
    since = datetime.now(tz=UTC) - timedelta(days=_ATTACHMENT_LOOKBACK_DAYS)
    # Object-target attachments are scoped directly by target_id; cost-item
    # attachments need a join through cost_items. We collect both.
    object_atts = (
        await session.execute(
            select(Attachment).where(
                Attachment.target_type == AttachmentTargetType.OBJECT,
                Attachment.target_id == object_id,
                Attachment.created_at >= since,
                Attachment.uploaded_by.is_not(None),
                Attachment.uploaded_by != user_id,
            )
        )
    ).scalars().all()

    cost_atts = (
        await session.execute(
            select(Attachment, CostItem)
            .join(CostItem, CostItem.id == Attachment.target_id)
            .where(
                Attachment.target_type == AttachmentTargetType.COST_ITEM,
                CostItem.object_id == object_id,
                Attachment.created_at >= since,
                Attachment.uploaded_by.is_not(None),
                Attachment.uploaded_by != user_id,
            )
        )
    ).all()

    result: list[tuple[str, Attachment, str]] = []
    for att in object_atts:
        result.append((object_name, att, "Objekt"))
    for att, ci in cost_atts:
        result.append((object_name, att, f"Position „{ci.title}“"))
    return result


def _render_digest(user: User, payload: _DigestPayload) -> tuple[str, str]:
    """Render the German digest e-mail body and subject."""
    today = date.today().isoformat()
    subject = f"[Reno-Budget] Wöchentliche Übersicht — {today}"
    lines: list[str] = [
        f"Hallo {user.display_name}",
        "",
        "Ihre wöchentliche Reno-Budget-Übersicht:",
        "",
    ]

    if payload.urgent_items:
        lines.append("Dringende und hochpriorisierte Positionen:")
        for object_name, item in payload.urgent_items:
            year = item.planned_year if item.planned_year is not None else "—"
            lines.append(
                f"  - [{object_name}] {item.title} (Priorität: "
                f"{item.priority.value}, geplant {year}, Status: {item.status.value})"
            )
        lines.append("")

    if payload.underfunding:
        lines.append("Renofond-Unterdeckung in den nächsten 5 Jahren:")
        by_object: dict[str, list[tuple[int, Decimal]]] = defaultdict(list)
        for object_name, year, shortfall in payload.underfunding:
            by_object[object_name].append((year, shortfall))
        for object_name, entries in by_object.items():
            lines.append(f"  Objekt: {object_name}")
            for year, shortfall in entries:
                lines.append(f"    - {year}: Fehlbetrag CHF {shortfall:.2f}")
        lines.append("")

    if payload.new_attachments:
        lines.append("Neue Anhänge der letzten 7 Tage (von anderen Mitwirkenden):")
        for object_name, att, scope_label in payload.new_attachments:
            lines.append(
                f"  - [{object_name}] {scope_label}: {att.filename} "
                f"(hochgeladen {att.created_at.date().isoformat()})"
            )
        lines.append("")

    lines.append("Diese E-Mail wird wöchentlich automatisch versendet.")
    lines.append("Mit freundlichen Grüssen")
    lines.append("Reno-Budget")
    return subject, "\n".join(lines)


async def _build_payload(
    session: AsyncSession, user: User
) -> _DigestPayload:
    payload = _DigestPayload()
    memberships = await _user_memberships(session, user.id)
    for m in memberships:
        object_name = await _object_name(session, m.object_id)
        # Urgent items are visible to any member (owner/editor/viewer).
        payload.urgent_items.extend(
            await _collect_urgent_items(session, m.object_id, object_name)
        )
        if m.role == ObjectRole.OWNER:
            payload.underfunding.extend(
                await _collect_underfunding(
                    session, m.object_id, object_name, membership_id=m.id
                )
            )
            payload.new_attachments.extend(
                await _collect_new_attachments(
                    session, m.object_id, object_name, user_id=user.id
                )
            )
    return payload


async def _record_digest_audit(
    session: AsyncSession, user: User
) -> None:
    await audit_svc.record(
        session,
        actor=None,
        actor_email=audit_svc.WORKER_ACTOR_EMAIL,
        action=audit_svc.ACTION_WORKER_DIGEST_SENT,
        target_type="user",
        target_id=user.id,
        summary=f"Wöchentliche Übersicht gesendet an {user.email}",
    )


async def run_digests() -> int:
    """Build and send digest e-mails to all active users with at least one signal.

    Returns the number of e-mails actually sent (skipped recipients are not
    counted).
    """
    SessionLocal: async_sessionmaker = db_module.SessionLocal  # type: ignore[type-arg]
    sent = 0
    async with SessionLocal() as session:
        users = (
            await session.execute(select(User).where(User.is_active.is_(True)))
        ).scalars().all()
        for user in users:
            try:
                payload = await _build_payload(session, user)
            except Exception:  # pragma: no cover — defensive
                logger.exception("worker.digest.build_failed user=%s", user.email)
                continue
            if payload.is_empty():
                logger.debug("worker.digest.skip empty user=%s", user.email)
                continue
            subject, body = _render_digest(user, payload)
            await send_email(user.email, subject, body)
            await _record_digest_audit(session, user)
            sent += 1
        await session.commit()
    logger.info("worker.digest.done sent=%d", sent)
    return sent


__all__ = ["run_digests"]
