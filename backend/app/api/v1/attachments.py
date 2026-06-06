"""HTTP routes for attachments on cost items and objects (Phase 6).

Security invariants
-------------------
* Every endpoint resolves the **parent object** and runs the standard
  per-object RBAC dependency. Viewer+ may list/download; editor+ may upload;
  uploader-or-editor+ may delete (uploader always controls their own).
* Mime types are sniffed server-side (:mod:`app.services.storage`); the
  client ``Content-Type`` is ignored. Filenames are sanitised before insert.
* The download endpoint streams the file with
  ``Content-Security-Policy: default-src 'none'`` and
  ``X-Content-Type-Options: nosniff`` so a malicious PDF/HTML cannot execute
  in the browser even if the user opens it inline.
* Files are stored *outside* the web root and are never served by any static
  handler — every byte flows through this router after RBAC.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Annotated
from urllib.parse import quote as urlquote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.db import SessionDep
from app.core.deps import CurrentUser, require_csrf, require_object_access_dep
from app.models.attachment import Attachment, AttachmentTargetType
from app.models.cost import CostItem
from app.models.object import ObjectRole
from app.models.user import User
from app.repositories.cost_item import get_cost_item as repo_get_cost_item
from app.schemas.attachment import AttachmentRead
from app.services import audit as audit_svc
from app.services.rbac import ObjectAccess, require_object_access
from app.services.storage import (
    FileTooLargeError,
    InvalidFilenameError,
    StorageError,
    UnsupportedMediaTypeError,
    resolve_path,
    store_upload,
)

router = APIRouter(prefix="", tags=["attachments"])


# ---- Helpers ----------------------------------------------------------------


def _to_read(att: Attachment) -> AttachmentRead:
    return AttachmentRead.model_validate(att)


def _raise_storage(exc: StorageError) -> None:
    """Translate storage-service errors into HTTP responses with German messages."""
    if isinstance(exc, FileTooLargeError):
        # 413 — Starlette renamed the constant; fall back for older releases.
        raise HTTPException(
            getattr(status, "HTTP_413_CONTENT_TOO_LARGE", 413),
            str(exc),
        )
    if isinstance(exc, UnsupportedMediaTypeError):
        raise HTTPException(status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, str(exc))
    if isinstance(exc, InvalidFilenameError):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))


def _content_disposition(filename: str) -> str:
    """Build a safe ``Content-Disposition`` value.

    RFC 6266 lets us provide both an ASCII fallback (``filename=``) and an
    RFC 5987 UTF-8 form (``filename*=UTF-8''…``). Browsers prefer the latter
    and fall back to the former; both must be valid token sequences.
    """
    # ASCII fallback: replace anything outside printable ASCII with ``_``.
    ascii_safe = "".join(c if 32 <= ord(c) < 127 and c not in '"\\' else "_" for c in filename)
    if not ascii_safe:
        ascii_safe = "download"
    encoded = urlquote(filename, safe="")
    return f'attachment; filename="{ascii_safe}"; filename*=UTF-8\'\'{encoded}'


async def _file_iterator(path: Path) -> AsyncIterator[bytes]:
    """Yield the file in 64-KiB chunks. Synchronous read inside an async generator.

    A FastAPI ``StreamingResponse`` accepts any iterable; a 64-KiB chunk is
    small enough not to block the event loop noticeably while large enough to
    keep syscalls bounded.
    """
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(64 * 1024)
            if not chunk:
                break
            yield chunk


_SECURITY_HEADERS = {
    # No subresource of any kind may execute. Defence in depth — the response
    # is also forced as an attachment via Content-Disposition.
    "Content-Security-Policy": "default-src 'none'",
    # Force the declared content type; never let the browser sniff a .pdf as
    # text/html, which used to be a real XSS vector.
    "X-Content-Type-Options": "nosniff",
    # Don't keep the upload around in shared caches.
    "Cache-Control": "private, no-store",
}


# ---- Cost-item attachments --------------------------------------------------


@router.get(
    "/cost-items/{item_id}/attachments",
    response_model=list[AttachmentRead],
)
async def list_cost_item_attachments(
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> list[AttachmentRead]:
    """List attachments of a cost item. Caller MUST hold >=VIEWER on parent object."""
    item = await repo_get_cost_item(session, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kostenposition nicht gefunden")
    await require_object_access(session, user, item.object_id, ObjectRole.VIEWER)
    rows = (
        (
            await session.execute(
                select(Attachment)
                .where(
                    Attachment.target_type == AttachmentTargetType.COST_ITEM,
                    Attachment.target_id == item_id,
                )
                .order_by(Attachment.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [_to_read(r) for r in rows]


@router.post(
    "/cost-items/{item_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def upload_cost_item_attachment(
    request: Request,
    item_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
    file: Annotated[UploadFile, File(...)],
) -> AttachmentRead:
    """Upload a file to a cost item. Caller MUST hold >=EDITOR on parent object."""
    item = await repo_get_cost_item(session, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Kostenposition nicht gefunden")
    await require_object_access(session, user, item.object_id, ObjectRole.EDITOR)
    return await _persist_attachment(
        session,
        target_type=AttachmentTargetType.COST_ITEM,
        target_id=item_id,
        uploader_id=user.id,
        file=file,
        actor=user,
        object_id=item.object_id,
        request=request,
    )


# ---- Object attachments -----------------------------------------------------


@router.get(
    "/objects/{object_id}/attachments",
    response_model=list[AttachmentRead],
)
async def list_object_attachments(
    object_id: uuid.UUID,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.VIEWER))],
    session: SessionDep,
) -> list[AttachmentRead]:
    """List attachments of an object. Caller MUST hold >=VIEWER."""
    _ = access  # presence enforced; no further filtering at object level
    rows = (
        (
            await session.execute(
                select(Attachment)
                .where(
                    Attachment.target_type == AttachmentTargetType.OBJECT,
                    Attachment.target_id == object_id,
                )
                .order_by(Attachment.created_at)
            )
        )
        .scalars()
        .all()
    )
    return [_to_read(r) for r in rows]


@router.post(
    "/objects/{object_id}/attachments",
    response_model=AttachmentRead,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_csrf)],
)
async def upload_object_attachment(
    request: Request,
    object_id: uuid.UUID,
    user: CurrentUser,
    access: Annotated[ObjectAccess, Depends(require_object_access_dep(ObjectRole.EDITOR))],
    session: SessionDep,
    file: Annotated[UploadFile, File(...)],
) -> AttachmentRead:
    """Upload a file to an object. Caller MUST hold >=EDITOR."""
    _ = access
    return await _persist_attachment(
        session,
        target_type=AttachmentTargetType.OBJECT,
        target_id=object_id,
        uploader_id=user.id,
        file=file,
        actor=user,
        object_id=object_id,
        request=request,
    )


# ---- Download / Delete (by attachment id) -----------------------------------


@router.get("/attachments/{attachment_id}/download")
async def download_attachment(
    attachment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> StreamingResponse:
    """Stream the attachment bytes. Caller MUST hold >=VIEWER on the parent object."""
    att = await _load_or_404(session, attachment_id)
    await _require_parent_access(session, user, att, ObjectRole.VIEWER)

    path = resolve_path(att.sha256)
    if not path.is_file():
        # Row references a missing blob — operator should investigate. Hide
        # the storage layout from the client; surface a generic 404.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Datei nicht verfügbar")

    headers = {
        **_SECURITY_HEADERS,
        "Content-Disposition": _content_disposition(att.filename),
        "Content-Length": str(att.size_bytes),
    }
    return StreamingResponse(_file_iterator(path), media_type=att.mime, headers=headers)


@router.delete(
    "/attachments/{attachment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_csrf)],
)
async def delete_attachment(
    request: Request,
    attachment_id: uuid.UUID,
    user: CurrentUser,
    session: SessionDep,
) -> None:
    """Delete an attachment row.

    Authorisation: uploader may always delete their own; otherwise EDITOR+ on
    the parent object. The on-disk blob is intentionally **not** removed here
    — multiple attachments may dedup to the same content. A future
    garbage-collection job will sweep unreferenced blobs.
    TODO(phase-future): wire the orphan-blob GC job (docs/architecture/).
    """
    att = await _load_or_404(session, attachment_id)
    if att.uploaded_by == user.id:
        # Self-delete is always allowed; we still confirm at least VIEWER so
        # a former member who lost access cannot reach back in.
        await _require_parent_access(session, user, att, ObjectRole.VIEWER)
    else:
        await _require_parent_access(session, user, att, ObjectRole.EDITOR)
    parent_object_id = await _resolve_parent_object_id(session, att)
    filename = att.filename
    att_id = att.id
    await session.delete(att)
    await audit_svc.record(
        session,
        actor=user,
        action=audit_svc.ACTION_ATTACHMENT_DELETE,
        object_id=parent_object_id,
        target_type="attachment",
        target_id=att_id,
        summary=f"Anhang '{filename}' gelöscht",
        request=request,
    )
    await session.commit()


# ---- Internal helpers -------------------------------------------------------


async def _persist_attachment(
    session: SessionDep,
    *,
    target_type: AttachmentTargetType,
    target_id: uuid.UUID,
    uploader_id: uuid.UUID,
    file: UploadFile,
    actor: User,
    object_id: uuid.UUID,
    request: Request,
) -> AttachmentRead:
    """Stream + validate + insert. Common path for both upload endpoints."""
    try:
        stored = await store_upload(file)
    except StorageError as exc:
        _raise_storage(exc)

    att = Attachment(
        target_type=target_type,
        target_id=target_id,
        sha256=stored.sha256,
        filename=stored.filename,
        mime=stored.mime,
        size_bytes=stored.size_bytes,
        uploaded_by=uploader_id,
    )
    session.add(att)
    await session.flush()
    await audit_svc.record(
        session,
        actor=actor,
        action=audit_svc.ACTION_ATTACHMENT_UPLOAD,
        object_id=object_id,
        target_type="attachment",
        target_id=att.id,
        summary=f"Anhang '{att.filename}' hochgeladen ({att.size_bytes} Bytes)",
        payload={"mime": att.mime, "sha256": att.sha256},
        request=request,
    )
    await session.commit()
    await session.refresh(att)
    return _to_read(att)


async def _resolve_parent_object_id(
    session: SessionDep, att: Attachment
) -> uuid.UUID:
    """Return the ``object_id`` an attachment ultimately belongs to."""
    if att.target_type == AttachmentTargetType.OBJECT:
        return att.target_id
    ci = (
        await session.execute(select(CostItem).where(CostItem.id == att.target_id))
    ).scalar_one_or_none()
    if ci is None:
        # Should not happen because the caller already validated access; we
        # fall back to the (now-orphaned) target_id only so the audit row
        # still records *something* meaningful.
        return att.target_id
    return ci.object_id


async def _load_or_404(session: SessionDep, attachment_id: uuid.UUID) -> Attachment:
    att = (
        await session.execute(select(Attachment).where(Attachment.id == attachment_id))
    ).scalar_one_or_none()
    if att is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
    return att


async def _require_parent_access(
    session: SessionDep,
    user: CurrentUser,
    att: Attachment,
    minimum: ObjectRole,
) -> None:
    """Resolve the parent object's id and enforce ``minimum`` role on it.

    For ``target_type == COST_ITEM`` we have to dereference the cost item to
    learn its ``object_id``. For ``target_type == OBJECT`` the target id is
    already the object id.
    """
    if att.target_type == AttachmentTargetType.OBJECT:
        object_id = att.target_id
    else:
        ci = (
            await session.execute(select(CostItem).where(CostItem.id == att.target_id))
        ).scalar_one_or_none()
        if ci is None:
            # Parent vanished (race/data corruption). Treat as not-found.
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Anhang nicht gefunden")
        object_id = ci.object_id
    await require_object_access(session, user, object_id, minimum)
