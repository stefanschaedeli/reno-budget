"""HTTP routes for object exports (Phase 8).

Three read-only endpoints — all require ``VIEWER`` on the object — that
stream a generated artefact back to the caller:

* ``GET /objects/{id}/export/xlsx`` — Kostenpositionen + Budget workbook.
* ``GET /objects/{id}/export/pdf``  — One-page Budget-Summary PDF.
* ``GET /objects/{id}/export/npk``  — NPK 2025 JSON stub.

Every successful export writes a single :class:`AuditEvent` with
``action="object.export"`` and the format in the summary. Scoped EDITOR /
VIEWER members receive pro-rated numbers (the exporters reuse the Phase 4
RBAC pro-rating logic). Outsiders get 404 via the dependency.
"""

from __future__ import annotations

import uuid
from urllib.parse import quote as urlquote

from fastapi import APIRouter, Request, Response

from app.core.db import SessionDep
from app.core.deps import CurrentUser
from app.models.object import ObjectRole
from app.services import audit as audit_svc
from app.services.export_npk import build_npk
from app.services.export_pdf import build_pdf
from app.services.export_xlsx import build_xlsx
from app.services.rbac import ObjectAccess, require_object_access

router = APIRouter(prefix="/objects/{object_id}/export", tags=["exports"])


_XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_PDF_MIME = "application/pdf"
_JSON_MIME = "application/json"


def _content_disposition(filename: str) -> str:
    """Build a Content-Disposition header that survives non-ASCII filenames.

    Same RFC 5987 trick as the attachments router — provide an ASCII
    fallback and a UTF-8 ``filename*`` so every browser gets a usable
    download name.
    """
    ascii_safe = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in filename)
    if not ascii_safe:
        ascii_safe = "export"
    encoded = urlquote(filename, safe="")
    return f'attachment; filename="{ascii_safe}"; filename*=UTF-8\'\'{encoded}'


async def _audit(
    session: SessionDep,
    *,
    user: CurrentUser,
    object_id: uuid.UUID,
    request: Request,
    fmt: str,
) -> None:
    """Record an ``object.export`` audit event and commit.

    The audit row is committed *after* the export bytes are generated but
    *before* the bytes leave the application — if the export blew up we
    don't want a misleading "export succeeded" row.
    """
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_OBJECT_EXPORT,
        object_id=object_id,
        target_type="object",
        target_id=object_id,
        summary=f"Export erstellt ({fmt.upper()})",
        payload={"format": fmt},
        request=request,
    )
    await session.commit()


@router.get("/xlsx")
async def export_xlsx(
    request: Request,
    object_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Stream the Kostenpositionen + Budget workbook. VIEWER+ on object."""
    access: ObjectAccess = await require_object_access(
        session, user, object_id, ObjectRole.VIEWER
    )
    body, filename = await build_xlsx(session, object_id, access=access)
    await _audit(session, user=user, object_id=object_id, request=request, fmt="xlsx")
    return Response(
        content=body,
        media_type=_XLSX_MIME,
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/pdf")
async def export_pdf(
    request: Request,
    object_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Stream the Budget-Summary PDF. VIEWER+ on object."""
    access = await require_object_access(session, user, object_id, ObjectRole.VIEWER)
    body, filename = await build_pdf(session, object_id, access=access)
    await _audit(session, user=user, object_id=object_id, request=request, fmt="pdf")
    return Response(
        content=body,
        media_type=_PDF_MIME,
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "private, no-store",
        },
    )


@router.get("/npk")
async def export_npk(
    request: Request,
    object_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> Response:
    """Stream the NPK-stub JSON. VIEWER+ on object."""
    access = await require_object_access(session, user, object_id, ObjectRole.VIEWER)
    body, filename = await build_npk(session, object_id, access=access)
    await _audit(session, user=user, object_id=object_id, request=request, fmt="npk")
    return Response(
        content=body,
        media_type=_JSON_MIME,
        headers={
            "Content-Disposition": _content_disposition(filename),
            "Cache-Control": "private, no-store",
        },
    )
