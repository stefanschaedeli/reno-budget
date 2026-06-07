"""PDF export service (Phase 8).

Generates a one-page A4 Budget-Summary PDF per object using ReportLab's
platypus framework. The layout is deliberately compact — header, reserve
table, top-10 planned positions, underfunding hint — so a Hausverwaltung
can hand it out at an Eigentümerversammlung without further editing.

RBAC mirrors :mod:`app.services.export_xlsx`: scoped EDITOR / VIEWER
members get pro-rated figures; the resulting PDF is what *they* are
allowed to see.
"""

from __future__ import annotations

import io
import uuid
from decimal import Decimal

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app import __version__
from app.repositories.cost_item import list_cost_items as repo_list_cost_items
from app.repositories.object import get_object
from app.services.bkp_shares import iter_bkp_shares
from app.services.budgets import compute_reserve_plan
from app.services.export_xlsx import build_export_filename
from app.services.rbac import ObjectAccess
from app.services.renofond import compute_projection

_PAGE_MARGIN = 15 * mm
_TABLE_HEADER_BG = colors.HexColor("#1f2937")  # slate-800
_TABLE_HEADER_FG = colors.white
_TABLE_ALT_BG = colors.HexColor("#f8fafc")  # slate-50


def _fmt_chf(value: Decimal) -> str:
    """Render a Decimal as ``1'234.56 CHF`` (Swiss apostrophe thousands)."""
    quantised = value.quantize(Decimal("0.01"))
    sign, digits, _ = quantised.as_tuple()
    # Split into franks and rappen.
    raw = f"{abs(quantised):.2f}"
    int_part, dec_part = raw.split(".")
    grouped: list[str] = []
    while len(int_part) > 3:
        grouped.insert(0, int_part[-3:])
        int_part = int_part[:-3]
    grouped.insert(0, int_part)
    out = "'".join(grouped) + "." + dec_part
    del digits, sign  # silence linters; the sign is captured by abs() + prefix
    if quantised < 0:
        out = "-" + out
    return f"{out} CHF"


async def build_pdf(
    session: AsyncSession,
    object_id: uuid.UUID,
    *,
    access: ObjectAccess,
) -> tuple[bytes, str]:
    """Build a one-page Budget-Summary PDF; return ``(bytes, filename)``."""
    obj = await get_object(session, object_id)
    assert obj is not None
    reserve = await compute_reserve_plan(session, object_id, access=access)
    projection = await compute_projection(session, object_id, access=access)
    items = list(await repo_list_cost_items(session, object_id))

    # Expand items into per-BKP-share rows so multi-BKP items appear once
    # per share (with the amount apportioned). Items without a planned
    # amount drop out; uncategorised items render with "—" as the BKP.
    expanded: list[tuple[str, str, int | None, Decimal]] = []
    for i in items:
        if i.planned_amount_chf is None:
            continue
        for code, share_permille in iter_bkp_shares(i):
            share_frac = Decimal(share_permille) / Decimal(1000)
            amount = i.planned_amount_chf * share_frac
            expanded.append(
                (
                    code if code is not None else "—",
                    i.title,
                    i.planned_year,
                    amount,
                )
            )
    expanded.sort(key=lambda row: row[3], reverse=True)
    visible_items = expanded[:10]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=_PAGE_MARGIN,
        rightMargin=_PAGE_MARGIN,
        topMargin=_PAGE_MARGIN,
        bottomMargin=_PAGE_MARGIN,
        title=f"Reno-Budget — {obj.name}",
        author="Reno-Budget",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "Title",
        parent=styles["Title"],
        fontSize=18,
        leading=22,
        spaceAfter=6,
    )
    h2_style = ParagraphStyle(
        "H2",
        parent=styles["Heading2"],
        fontSize=12,
        leading=14,
        spaceBefore=8,
        spaceAfter=4,
    )
    body_style = styles["BodyText"]

    story: list[object] = []

    # ---- Header ----
    story.append(Paragraph(obj.name, title_style))
    if obj.address:
        story.append(Paragraph(obj.address, body_style))
    from datetime import date as _date

    story.append(
        Paragraph(
            f"Erstellt am {_date.today().isoformat()} — Reno-Budget v{__version__}",
            body_style,
        )
    )
    if reserve.scope_pro_rated:
        story.append(
            Paragraph(
                "<i>Beträge sind anteilig auf Ihre Einheiten umgerechnet.</i>",
                body_style,
            )
        )
    story.append(Spacer(1, 6))

    # ---- Reserve table ----
    story.append(Paragraph("Reserve-Planung", h2_style))
    reserve_rows = [
        ["Modus", str(obj.contribution_mode)],
        ["Inflationsrate p.a.", f"{obj.inflation_rate_percent} %"],
        ["Anfangsreserve", _fmt_chf(reserve.initial_reserve_chf)],
        ["Geplant gesamt (inflationsbereinigt)", _fmt_chf(reserve.total_planned_inflated_chf)],
        ["Benötigtes Total", _fmt_chf(reserve.required_total_chf)],
        ["Soll pro Jahr", _fmt_chf(reserve.required_per_year_chf)],
        ["Soll pro Monat", _fmt_chf(reserve.required_per_month_chf)],
    ]
    reserve_table = Table(reserve_rows, colWidths=[80 * mm, 80 * mm])
    reserve_table.setStyle(
        TableStyle(
            [
                ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _TABLE_ALT_BG]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(reserve_table)

    # ---- Top planned positions ----
    story.append(Paragraph("Top-Plan-Positionen", h2_style))
    if not visible_items:
        story.append(Paragraph("Keine geplanten Positionen vorhanden.", body_style))
    else:
        top_rows: list[list[object]] = [["BKP", "Titel", "Jahr", "Geplant CHF"]]
        for code, title, planned_year, amount in visible_items:
            top_rows.append(
                [
                    code,
                    title,
                    str(planned_year) if planned_year is not None else "—",
                    _fmt_chf(amount),
                ]
            )
        top_table = Table(top_rows, colWidths=[20 * mm, 90 * mm, 20 * mm, 40 * mm])
        top_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), _TABLE_HEADER_BG),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _TABLE_HEADER_FG),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("ALIGN", (3, 1), (3, -1), "RIGHT"),
                    ("ALIGN", (2, 1), (2, -1), "CENTER"),
                    ("INNERGRID", (0, 0), (-1, -1), 0.2, colors.lightgrey),
                    ("BOX", (0, 0), (-1, -1), 0.4, colors.grey),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _TABLE_ALT_BG]),
                ]
            )
        )
        story.append(top_table)

    # ---- Underfunding hint ----
    if projection.underfunding_years:
        story.append(Spacer(1, 6))
        years = ", ".join(str(u.year) for u in projection.underfunding_years[:8])
        story.append(
            Paragraph(
                f"<b>Hinweis:</b> Renofond-Projektion zeigt Unterdeckung in {years}.",
                body_style,
            )
        )

    doc.build(story)
    return buf.getvalue(), build_export_filename(obj.name, "pdf")


__all__ = ["build_pdf"]
