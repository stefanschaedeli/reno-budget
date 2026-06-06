"""NPK 2025 schema export *stub* (Phase 8).

Produces a JSON document loosely shaped like the SIA Normpositionen-Katalog
(NPK 2025) so downstream consumers can already wire their pipelines today
and replace the stub once the official NPK feed lands in a later phase.

.. warning::
   This is a **stub**. We do not validate ``npk_code`` against the SIA
   master catalogue; we round-trip what users typed (or leave it blank).
   The schema fields below are placeholders modelled on the public NPK
   structure (Kapitel / Position / Variante / Menge / Einheit) but the
   actual values are best-effort approximations.

   TODO(phase-future): replace this stub once the SIA NPK feed is
   integrated. Track in ``docs/architecture/`` and bump the
   ``schema_version`` so consumers can switch behaviour by version.
"""

from __future__ import annotations

import datetime as _dt
import json
import uuid
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.cost_item import list_cost_items as repo_list_cost_items
from app.repositories.object import get_object
from app.services.export_xlsx import build_export_filename
from app.services.rbac import ObjectAccess

# Bump this when the payload shape changes — consumers can branch on it.
SCHEMA_VERSION = "npk-2025-stub-v1"


def _scope_factor(item: object, allowed: frozenset[uuid.UUID] | None) -> Decimal:
    """Pro-rate factor for a cost item under the caller's unit scope.

    Re-implemented here (instead of importing from the budgets service) so
    the NPK exporter can remain a single self-contained file. The math
    matches ``app.services.budgets._scope_factor`` exactly.
    """
    if allowed is None:
        return Decimal("1")
    share = Decimal("0")
    # ``item`` is a CostItem with an ``allocations`` collection. Using
    # ``getattr`` keeps mypy happy without an import cycle.
    for a in getattr(item, "allocations", []):
        if a.unit_id in allowed:
            share += Decimal(a.share_permille)
    return share / Decimal("1000")


async def build_npk(
    session: AsyncSession,
    object_id: uuid.UUID,
    *,
    access: ObjectAccess,
) -> tuple[bytes, str]:
    """Build the NPK-stub JSON document; return ``(bytes, filename)``."""
    obj = await get_object(session, object_id)
    assert obj is not None
    items = list(await repo_list_cost_items(session, object_id))
    allowed = access.allowed_unit_ids

    positions: list[dict[str, Any]] = []
    for item in items:
        factor = _scope_factor(item, allowed)
        if factor == 0:
            continue
        planned = (
            float(item.planned_amount_chf * factor)
            if item.planned_amount_chf is not None
            else None
        )
        actual = (
            float(item.actual_amount_chf * factor)
            if item.actual_amount_chf is not None
            else None
        )
        positions.append(
            {
                "kapitel": item.bkp_code[:1] if item.bkp_code else None,
                "bkp_code": item.bkp_code,
                "npk_code": item.npk_code or None,
                "position_titel": item.title,
                # Variante / Menge / Einheit are placeholders until the
                # SIA feed lands; we surface ``null`` so consumers don't
                # mistake "" for "no data".
                "variante": None,
                "menge": None,
                "einheit": None,
                "planung": {
                    "jahr": item.planned_year,
                    "betrag_chf": planned,
                    "status": str(item.status),
                    "prioritaet": str(item.priority),
                },
                "ausfuehrung": {
                    "datum": item.actual_date.isoformat() if item.actual_date else None,
                    "betrag_chf": actual,
                },
            }
        )

    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": _dt.datetime.now(tz=_dt.UTC).isoformat(),
        "stub": True,
        "stub_note": (
            "Dieses Dokument ist ein Schema-Stub. Die Felder folgen lose dem"
            " SIA NPK 2025, werden aber noch nicht gegen den offiziellen"
            " Katalog validiert. Konsumenten sollen ``schema_version``"
            " prüfen, sobald die echte NPK-Integration live ist."
        ),
        "objekt": {
            "id": str(obj.id),
            "name": obj.name,
            "adresse": obj.address,
        },
        "scope_pro_rated": allowed is not None,
        "positionen": positions,
    }

    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False).encode("utf-8")
    return body, build_export_filename(obj.name, "json")


__all__ = ["SCHEMA_VERSION", "build_npk"]
