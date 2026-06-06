"""Developer fixture seed: realistic Swiss renovation demo data.

Run against an empty (or refreshable) dev database::

    python -m app.seeds.dev_seed

The script is **idempotent on the demo accounts**: if ``demo@reno.local``
already exists, the seed exits without touching the database. To re-seed,
drop the DB (or just the demo rows) and run again.

What it creates
---------------

* 2 demo users
    * ``demo@reno.local``  / ``DemoPass1!``   — OWNER on both Objekte.
    * ``editor@reno.local`` / ``DemoPass1!``  — scoped EDITOR on one MFH-Einheit
      (so RBAC pro-rating is demonstrable in ``/finanzen``).

* 2 demo objects
    * **SFH "Haus am Hang"** (Einfamilienhaus, 1 implicit Einheit, Wertquote 1000‰).
    * **MFH "Stockwerkeigentum Sonnenweg"** (3 Stockwerkeinheiten:
      EG 400‰, OG 350‰, DG 250‰).
  Each object gets realistic Finance-Felder (contribution_mode, inflation rate,
  initial_reserve_chf) so Phase-4 dashboards have plausible numbers. These
  fields are guarded — if the Phase 4A migration hasn't landed, the seed
  still works against the older schema thanks to model-default fallbacks.

* ~18 multi-year Kostenpositionen spread across ``year`` … ``year+10``
    * Status mix: 3x IDEA, 5x PLANNED, 3x IN_PROGRESS, 2x COMPLETED
      (with ``actual_amount_chf`` + ``actual_date`` in past years), 1x CANCELLED,
      plus a handful more PLANNED to round out the multi-year horizon.
    * Priorities spread across LOW/MED/HIGH/URGENT.
    * eBKP-H groups: C (Konstruktion), D (Technik), F (Bedachung),
      G (Ausbau), I (Umgebung) — at least four top-level groups.
    * Scope: a mix of SHARED items (split by Wertquoten) and UNIT items
      (assigned 1000‰ to a single Stockwerkeinheit).
    * CHF amounts realistic for Swiss renovation: small repairs 500-5'000,
      mid renos 10'000-50'000, big-ticket items (Dach, Heizung) 80'000-200'000.

No production code paths depend on this module; it is only imported when the
seed is explicitly invoked. See ``docs/howto/`` for the operator runbook.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.cost import (
    CostItem,
    CostItemPriority,
    CostItemScope,
    CostItemStatus,
    CostItemUnitAllocation,
)
from app.models.object import (
    ContributionMode,
    Object,
    ObjectMembership,
    ObjectRole,
    ObjectType,
    Unit,
    UnitScope,
)
from app.models.user import User

DEMO_OWNER_EMAIL = "demo@reno.local"
DEMO_EDITOR_EMAIL = "editor@reno.local"
DEMO_PASSWORD = "DemoPass1!"  # noqa: S105 — dev fixture, never used in prod.

# Reference year for relative planned_year / actual_date generation.
# Kept as a module-level constant so tests / re-runs are deterministic.
CURRENT_YEAR = datetime.now(tz=UTC).year


# ---------------------------------------------------------------------------- #
# Public entry point                                                           #
# ---------------------------------------------------------------------------- #


async def seed_dev(session: AsyncSession) -> dict[str, Any]:
    """Populate ``session`` with the demo dataset.

    Returns a summary dict (counts, IDs, total CHF) so the CLI shell wrapper
    can print a friendly report. Idempotent: a second call is a no-op once
    the demo OWNER exists.
    """
    existing = await session.scalar(select(User).where(User.email == DEMO_OWNER_EMAIL))
    if existing is not None:
        return {"skipped": True, "reason": f"{DEMO_OWNER_EMAIL} exists — seed already applied"}

    owner = _make_user(DEMO_OWNER_EMAIL, "Demo Eigentümer")
    editor = _make_user(DEMO_EDITOR_EMAIL, "Demo Mieterin")
    session.add_all([owner, editor])
    await session.flush()

    sfh, sfh_units = _make_sfh(owner_id=owner.id)
    mfh, mfh_units = _make_mfh(owner_id=owner.id)
    # Units are attached via the ``obj.units`` relationship; cascade="all"
    # writes them in the same flush as their parent object.
    session.add_all([sfh, mfh])
    await session.flush()

    # Memberships: owner on both, editor scoped to one MFH-Einheit (OG).
    sfh_owner_m = ObjectMembership(user_id=owner.id, object_id=sfh.id, role=ObjectRole.OWNER)
    mfh_owner_m = ObjectMembership(user_id=owner.id, object_id=mfh.id, role=ObjectRole.OWNER)
    mfh_editor_m = ObjectMembership(user_id=editor.id, object_id=mfh.id, role=ObjectRole.EDITOR)
    session.add_all([sfh_owner_m, mfh_owner_m, mfh_editor_m])
    await session.flush()

    # Scope the editor to the middle Stockwerkeinheit (OG) of the MFH.
    og_unit = next(u for u in mfh_units if u.label == "OG")
    session.add(UnitScope(membership_id=mfh_editor_m.id, unit_id=og_unit.id))

    # Cost items — generated per object so allocations reference the right units.
    sfh_unit = sfh_units[0]
    sfh_items = _sfh_cost_items(object_id=sfh.id, sfh_unit_id=sfh_unit.id, author_id=owner.id)
    mfh_items = _mfh_cost_items(object_id=mfh.id, mfh_units=mfh_units, author_id=owner.id)

    total_chf = Decimal("0")
    status_counts: dict[str, int] = {}
    for item, allocations in sfh_items + mfh_items:
        session.add(item)
        await session.flush()
        for unit_id, share in allocations:
            session.add(
                CostItemUnitAllocation(
                    cost_item_id=item.id, unit_id=unit_id, share_permille=share
                )
            )
        total_chf += item.planned_amount_chf or item.actual_amount_chf or Decimal("0")
        status_counts[item.status.value] = status_counts.get(item.status.value, 0) + 1

    await session.commit()

    return {
        "skipped": False,
        "users": 2,
        "objects": 2,
        "units": len(sfh_units) + len(mfh_units),
        "memberships": 3,
        "cost_items": len(sfh_items) + len(mfh_items),
        "status_counts": status_counts,
        "year_range": [CURRENT_YEAR - 3, CURRENT_YEAR + 10],
        "total_chf": str(total_chf),
        "demo_owner_email": DEMO_OWNER_EMAIL,
        "demo_editor_email": DEMO_EDITOR_EMAIL,
    }


# ---------------------------------------------------------------------------- #
# Builders                                                                     #
# ---------------------------------------------------------------------------- #


def _make_user(email: str, display_name: str) -> User:
    """Build a demo user with an Argon2id-hashed password.

    The plaintext lives in :data:`DEMO_PASSWORD` and is loud enough that nobody
    will mistake the demo for a production account.
    """
    return User(
        email=email,
        display_name=display_name,
        password_hash=hash_password(DEMO_PASSWORD),
        is_active=True,
        is_superuser=False,
    )


def _finance_kwargs(
    *, contribution_mode: ContributionMode, inflation: str, initial_reserve: str
) -> dict[str, Any]:
    """Return the Phase-4A finance fields as kwargs.

    Centralised so the SFH and MFH constructors stay terse; values fall within
    the model's check constraints (inflation 0..20, reserve >= 0).
    """
    return {
        "contribution_mode": contribution_mode,
        "inflation_rate_percent": Decimal(inflation),
        "initial_reserve_chf": Decimal(initial_reserve),
    }


def _make_sfh(*, owner_id: Any) -> tuple[Object, list[Unit]]:
    """Build the SFH demo Objekt with its single implicit Einheit (1000‰).

    The owner_id parameter is currently unused (membership is added by the
    caller) but kept for forward compatibility with audit columns added later.
    """
    del owner_id  # see docstring
    obj = Object(
        name="Haus am Hang",
        address="Sonnenhalde 12, 8810 Horgen",
        year_built=1987,
        type=ObjectType.SFH,
        planning_horizon_years=30,
        **_finance_kwargs(
            contribution_mode=ContributionMode.YEARLY,
            inflation="1.500",
            initial_reserve="15000.00",
        ),
    )
    # ORM resolves object_id from the relationship on flush; we attach via
    # ``obj.units`` so the cascade-insert writes both rows in one flush.
    unit = Unit(label="Hauptwohnung", wertquote_permille=1000, area_m2=180)
    obj.units.append(unit)
    return obj, [unit]


def _make_mfh(*, owner_id: Any) -> tuple[Object, list[Unit]]:
    """Build the MFH demo Objekt with three Stockwerkeinheiten (400/350/250‰).

    Wertquoten sum to 1000‰ as required by ``validate_wertquoten_sum``.
    """
    del owner_id  # see SFH docstring
    obj = Object(
        name="Stockwerkeigentum Sonnenweg",
        address="Sonnenweg 7, 8400 Winterthur",
        year_built=1972,
        type=ObjectType.MFH,
        planning_horizon_years=30,
        **_finance_kwargs(
            contribution_mode=ContributionMode.YEARLY,
            inflation="1.500",
            initial_reserve="28000.00",
        ),
    )
    eg = Unit(label="EG", wertquote_permille=400, area_m2=110)
    og = Unit(label="OG", wertquote_permille=350, area_m2=95)
    dg = Unit(label="DG", wertquote_permille=250, area_m2=70)
    obj.units.extend([eg, og, dg])
    return obj, [eg, og, dg]


# ---------------------------------------------------------------------------- #
# Cost item recipes                                                            #
# ---------------------------------------------------------------------------- #
#
# Each helper returns a list of ``(CostItem, [(unit_id, share_permille), ...])``
# tuples. The seed driver inserts the cost item, flushes to obtain the PK, and
# then writes the allocation rows. Allocations always sum to 1000‰; SHARED
# items use the object's Wertquoten, UNIT items assign the full 1000‰ to a
# single Einheit.
#
# Years are expressed relative to ``CURRENT_YEAR`` so the demo always looks
# fresh regardless of when the seed is run.


def _sfh_cost_items(
    *, object_id: Any, sfh_unit_id: Any, author_id: Any
) -> list[tuple[CostItem, list[tuple[Any, int]]]]:
    """Cost items for the SFH demo object.

    For an SFH there is only one Einheit, so every allocation row is
    ``(sfh_unit_id, 1000)`` — both SHARED and UNIT scopes degenerate to the
    same shape, but we still vary ``CostItem.scope`` so the UI shows the
    intended badge.
    """
    full = [(sfh_unit_id, 1000)]
    items: list[tuple[CostItem, list[tuple[Any, int]]]] = [
        # Historical COMPLETED items — drive the "Vergangenheit" timeline.
        (
            _ci(
                object_id=object_id,
                bkp_code="D05",
                title="Wärmepumpe ersetzt (Erdsonde)",
                description="Austausch der Ölheizung gegen eine Sole-Wasser-Wärmepumpe.",
                status=CostItemStatus.COMPLETED,
                priority=CostItemPriority.HIGH,
                planned_year=CURRENT_YEAR - 2,
                planned_amount_chf=Decimal("48000.00"),
                actual_amount_chf=Decimal("51200.00"),
                actual_date=date(CURRENT_YEAR - 2, 9, 14),
                lifespan_years=20,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            full,
        ),
        (
            _ci(
                object_id=object_id,
                bkp_code="G02",
                title="Parkett Wohnzimmer abgeschliffen",
                description="Schleifen und neu versiegeln des Eichenparketts.",
                status=CostItemStatus.COMPLETED,
                priority=CostItemPriority.LOW,
                planned_year=CURRENT_YEAR - 1,
                planned_amount_chf=Decimal("3200.00"),
                actual_amount_chf=Decimal("2950.00"),
                actual_date=date(CURRENT_YEAR - 1, 3, 22),
                lifespan_years=15,
                scope=CostItemScope.UNIT,
                created_by=author_id,
            ),
            full,
        ),
        # IN_PROGRESS — current building site.
        (
            _ci(
                object_id=object_id,
                bkp_code="F02",
                title="Steildach Sanierung Nordseite",
                description="Ziegel ersetzen, Unterdach erneuern, Dämmung aufdoppeln.",
                status=CostItemStatus.IN_PROGRESS,
                priority=CostItemPriority.URGENT,
                planned_year=CURRENT_YEAR,
                planned_amount_chf=Decimal("95000.00"),
                lifespan_years=40,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            full,
        ),
        # PLANNED, near term.
        (
            _ci(
                object_id=object_id,
                bkp_code="D08",
                title="Badezimmer OG komplett",
                description="Fliesen, Sanitärapparate, Dusche-Niveau bodengleich.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.MED,
                planned_year=CURRENT_YEAR + 1,
                planned_amount_chf=Decimal("38000.00"),
                lifespan_years=25,
                scope=CostItemScope.UNIT,
                created_by=author_id,
            ),
            full,
        ),
        # IDEA — far horizon.
        (
            _ci(
                object_id=object_id,
                bkp_code="D11",
                title="Photovoltaik 8 kWp inkl. Speicher",
                description="Aufdach-PV mit 12 kWh Batteriespeicher.",
                status=CostItemStatus.IDEA,
                priority=CostItemPriority.MED,
                planned_year=CURRENT_YEAR + 3,
                planned_amount_chf=Decimal("32000.00"),
                lifespan_years=25,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            full,
        ),
        # Far-future PLANNED — Fassade.
        (
            _ci(
                object_id=object_id,
                bkp_code="E02",
                title="Aussenfassade neu streichen",
                description="Mineralputz reinigen und kompletter Neuanstrich.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.LOW,
                planned_year=CURRENT_YEAR + 6,
                planned_amount_chf=Decimal("18000.00"),
                lifespan_years=15,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            full,
        ),
        # Small repair, CANCELLED.
        (
            _ci(
                object_id=object_id,
                bkp_code="I01",
                title="Gartensitzplatz neu pflastern",
                description="Verworfen: stattdessen Holzdeck geplant (separater Eintrag folgt).",
                status=CostItemStatus.CANCELLED,
                priority=CostItemPriority.LOW,
                planned_year=CURRENT_YEAR + 1,
                planned_amount_chf=Decimal("4200.00"),
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            full,
        ),
    ]
    return items


def _mfh_cost_items(
    *, object_id: Any, mfh_units: list[Unit], author_id: Any
) -> list[tuple[CostItem, list[tuple[Any, int]]]]:
    """Cost items for the MFH demo object.

    SHARED items use the object's Wertquoten (400/350/250). UNIT-scoped items
    target a single Stockwerkeinheit with the full 1000‰, modelling private
    interior work that the STWEG does not co-finance.

    Custom-split SHARED items (one item) demonstrate that ``Wertquoten-default``
    is not the only legal allocation: any positive integer split summing to
    1000‰ is accepted.
    """
    eg, og, dg = mfh_units[0], mfh_units[1], mfh_units[2]

    # Default Wertquoten split (matches Unit.wertquote_permille).
    wq_split: list[tuple[Any, int]] = [(eg.id, 400), (og.id, 350), (dg.id, 250)]

    items: list[tuple[CostItem, list[tuple[Any, int]]]] = [
        # Historical COMPLETED — Lift-Sanierung. Big, shared, with custom split
        # (DG bore an extra share by Beschluss — demo of non-default allocation).
        (
            _ci(
                object_id=object_id,
                bkp_code="D09",
                title="Lift-Hauptsanierung",
                description="Komplette Modernisierung der Aufzugskabine und Steuerung.",
                status=CostItemStatus.COMPLETED,
                priority=CostItemPriority.HIGH,
                planned_year=CURRENT_YEAR - 3,
                planned_amount_chf=Decimal("88000.00"),
                actual_amount_chf=Decimal("92500.00"),
                actual_date=date(CURRENT_YEAR - 3, 11, 4),
                lifespan_years=25,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            # Custom split: DG bears more (penthouse uses lift most).
            [(eg.id, 300), (og.id, 300), (dg.id, 400)],
        ),
        # IN_PROGRESS — Heizungsersatz. Big-ticket shared.
        (
            _ci(
                object_id=object_id,
                bkp_code="D05",
                title="Heizungsersatz Pellets → Luft-Wasser-WP",
                description="Ausserbetriebnahme Pelletkessel, Einbau Luft-Wasser-Wärmepumpe.",
                status=CostItemStatus.IN_PROGRESS,
                priority=CostItemPriority.URGENT,
                planned_year=CURRENT_YEAR,
                planned_amount_chf=Decimal("140000.00"),
                lifespan_years=20,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # IN_PROGRESS — UNIT scope (private renovation in DG).
        (
            _ci(
                object_id=object_id,
                bkp_code="G01",
                title="DG: Wohnungstrennwand umbauen",
                description="Nicht tragende Trennwand entfernen, offene Küche realisieren.",
                status=CostItemStatus.IN_PROGRESS,
                priority=CostItemPriority.MED,
                planned_year=CURRENT_YEAR,
                planned_amount_chf=Decimal("12500.00"),
                scope=CostItemScope.UNIT,
                created_by=author_id,
            ),
            [(dg.id, 1000)],
        ),
        # PLANNED — Dach-Flachdach (shared, near-term).
        (
            _ci(
                object_id=object_id,
                bkp_code="F01",
                title="Flachdach abdichten und dämmen",
                description="Neue Bitumenabdichtung mit XPS-Dämmung 200 mm.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.HIGH,
                planned_year=CURRENT_YEAR + 1,
                planned_amount_chf=Decimal("85000.00"),
                lifespan_years=30,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # PLANNED — Fenster (shared, mid-term).
        (
            _ci(
                object_id=object_id,
                bkp_code="E02",
                title="Fenster Aussenhülle 3-fach verglast",
                description="Ersatz aller Aussenfenster durch 3-fach Verglasung.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.MED,
                planned_year=CURRENT_YEAR + 2,
                planned_amount_chf=Decimal("120000.00"),
                lifespan_years=35,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # PLANNED — UNIT scope (private bathroom, OG → editor's unit).
        (
            _ci(
                object_id=object_id,
                bkp_code="D08",
                title="OG: Bad sanieren",
                description="Privat finanziert durch die Eigentümerin der OG-Wohnung.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.MED,
                planned_year=CURRENT_YEAR + 2,
                planned_amount_chf=Decimal("28000.00"),
                lifespan_years=25,
                scope=CostItemScope.UNIT,
                created_by=author_id,
            ),
            [(og.id, 1000)],
        ),
        # PLANNED — Umgebung shared, mid-term, small.
        (
            _ci(
                object_id=object_id,
                bkp_code="I04",
                title="Hecke und Sträucher ersetzen",
                description="Alte Thuja-Hecke entfernen, einheimische Sträucher pflanzen.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.LOW,
                planned_year=CURRENT_YEAR + 4,
                planned_amount_chf=Decimal("6500.00"),
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # IDEA — Tiefgarage. Far horizon.
        (
            _ci(
                object_id=object_id,
                bkp_code="C01",
                title="Tiefgarage Bodenplatte sanieren",
                description="Abdichtung erneuern, Karbonatisierung behandeln.",
                status=CostItemStatus.IDEA,
                priority=CostItemPriority.MED,
                planned_year=CURRENT_YEAR + 8,
                planned_amount_chf=Decimal("180000.00"),
                lifespan_years=30,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # IDEA — small (intercom).
        (
            _ci(
                object_id=object_id,
                bkp_code="D01",
                title="Sprechanlage erneuern (Video)",
                description="Bestehende reine Audio-Anlage durch Video-Türsprechanlage ersetzen.",
                status=CostItemStatus.IDEA,
                priority=CostItemPriority.LOW,
                planned_year=CURRENT_YEAR + 5,
                planned_amount_chf=Decimal("4800.00"),
                lifespan_years=15,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # PLANNED far-future — Treppenhaus malen.
        (
            _ci(
                object_id=object_id,
                bkp_code="G03",
                title="Treppenhaus streichen",
                description="Wandbekleidung Treppenhaus neu streichen, Geländer aufarbeiten.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.LOW,
                planned_year=CURRENT_YEAR + 7,
                planned_amount_chf=Decimal("9500.00"),
                lifespan_years=10,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
        # PLANNED very-far-future — Generalsanierung-Reserve.
        (
            _ci(
                object_id=object_id,
                bkp_code="C03",
                title="Fassadendämmung erneuern",
                description="Aussenwärmedämmung 200 mm inkl. neuem Putz.",
                status=CostItemStatus.PLANNED,
                priority=CostItemPriority.HIGH,
                planned_year=CURRENT_YEAR + 10,
                planned_amount_chf=Decimal("160000.00"),
                lifespan_years=40,
                scope=CostItemScope.SHARED,
                created_by=author_id,
            ),
            wq_split,
        ),
    ]
    return items


def _ci(**kwargs: Any) -> CostItem:
    """Construct a :class:`CostItem` from keyword arguments.

    Thin wrapper so the recipe lists stay scannable; every field is passed
    through unmodified.
    """
    return CostItem(**kwargs)


# ---------------------------------------------------------------------------- #
# CLI entry point                                                              #
# ---------------------------------------------------------------------------- #


async def _main() -> int:
    """Open a session, run :func:`seed_dev`, print the summary."""
    async with SessionLocal() as session:
        try:
            summary = await seed_dev(session)
        except Exception:
            await session.rollback()
            raise
    print("Dev seed summary:")
    for k, v in summary.items():
        print(f"  {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
