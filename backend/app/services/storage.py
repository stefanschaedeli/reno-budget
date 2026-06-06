"""Content-addressed file storage for attachments (Phase 6).

Files are stored at::

    <uploads_dir>/<sha256[:2]>/<sha256>

This Git-LFS-style two-character sharding keeps individual directories below a
reasonable inode count even when the repository grows into millions of blobs.
Identical content (same SHA-256) maps to the same path → automatic dedup;
storing the same PDF twice writes one blob and references it from two
``Attachment`` rows.

Security
--------
* Mime type is **sniffed** from the first 4 KiB with ``python-magic``. The
  client's ``Content-Type`` header is never trusted; if the sniff result is
  not in :data:`ALLOWED_MIME_TYPES` we reject the upload with 415.
* Hard size cap from :attr:`Settings.upload_max_bytes` (default 25 MiB).
  Exceeded → 413. The cap is enforced *while streaming* so a hostile client
  cannot fill the disk by sending a 10 GiB body.
* Filenames are sanitised: no path separators, null bytes, or ``..``
  traversal sequences. Sanitisation runs before the row is inserted; the
  sanitised value is what we echo in ``Content-Disposition``.
* The on-disk path is derived from the SHA-256 only — never from the client
  filename — so a malicious upload cannot escape ``uploads_dir`` even if the
  filename slipped through sanitisation.

Concurrency
-----------
We hash + write to a per-upload temp file in the same directory, then
``os.replace`` it onto the content-address path. ``os.replace`` is atomic on
POSIX, so concurrent uploads of the same content can both "win" without
races: whichever finishes last simply overwrites a byte-identical file.

Public API
----------
* :func:`store_upload` — async; consumes a Starlette ``UploadFile``, returns
  :class:`StoredFile`.
* :func:`resolve_path` — given a SHA-256, return the disk path.
* :exc:`StorageError` and subclasses — raised on any validation failure;
  routers translate them to HTTP statuses.
"""

from __future__ import annotations

import contextlib
import hashlib
import secrets
from dataclasses import dataclass
from pathlib import Path
from typing import IO

import magic
from fastapi import UploadFile

from app.core.config import get_settings

# ---- Allowlist --------------------------------------------------------------

# Only these mime types are accepted. The set is intentionally narrow:
# documents (PDF, Excel) and common photo formats. Adding anything else
# requires a code change and a security review (HTML/SVG/zip are dangerous
# even when served behind Content-Disposition: attachment).
ALLOWED_MIME_TYPES: frozenset[str] = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/heic",
        # Modern Excel (.xlsx)
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        # Legacy Excel (.xls) — libmagic typically reports this for OLE
        # compound documents; some installations may emit
        # 'application/x-ole-storage'. We accept both.
        "application/vnd.ms-excel",
        "application/x-ole-storage",
    }
)

# Bytes sniffed for mime detection. 4 KiB is enough for every libmagic
# signature we care about and avoids loading the entire file into memory
# just to identify it.
_SNIFF_BYTES = 4096

# Streaming read chunk while hashing/writing.
_CHUNK = 64 * 1024


# ---- Errors -----------------------------------------------------------------


class StorageError(Exception):
    """Base class for storage-service failures."""


class FileTooLargeError(StorageError):
    """Uploaded body exceeds :attr:`Settings.upload_max_bytes` (HTTP 413)."""


class UnsupportedMediaTypeError(StorageError):
    """Sniffed mime type not in :data:`ALLOWED_MIME_TYPES` (HTTP 415)."""


class InvalidFilenameError(StorageError):
    """Filename contains forbidden characters (HTTP 400)."""


# ---- Result -----------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class StoredFile:
    """Outcome of a successful upload.

    The router uses these fields verbatim to populate the ``Attachment`` row.
    """

    sha256: str
    size_bytes: int
    mime: str
    filename: str  # sanitised original
    path: Path  # on-disk content-address path


# ---- Filename hygiene -------------------------------------------------------


def sanitise_filename(raw: str) -> str:
    """Reject obviously dangerous filenames and strip directory components.

    The router still stores the *sanitised* basename, not a placeholder, so
    users see something close to what they uploaded in download dialogs.
    """
    if not raw:
        raise InvalidFilenameError("Dateiname fehlt")
    if "\x00" in raw:
        raise InvalidFilenameError("Dateiname enthält Null-Byte")
    # Reject path traversal *before* basenaming so we don't silently allow
    # ".." in a path that happens to start with a legitimate prefix.
    if ".." in raw.split("/") or ".." in raw.split("\\"):
        raise InvalidFilenameError("Dateiname enthält ungültige Pfadangabe")
    # Strip any directory prefix the client may have sent.
    base = Path(raw.replace("\\", "/")).name
    if not base or base in {".", ".."}:
        raise InvalidFilenameError("Dateiname ungültig")
    # Cap at the column width to guarantee the row fits.
    if len(base) > 255:
        base = base[-255:]
    return base


# ---- Path helpers -----------------------------------------------------------


def _root() -> Path:
    """Return the configured uploads root, ensured to exist."""
    root = Path(get_settings().uploads_dir).resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_path(sha256: str) -> Path:
    """Return the on-disk path for a given content hash.

    Does not check that the file actually exists; callers that need to stream
    bytes should ``Path.is_file()`` before opening.
    """
    if len(sha256) != 64 or not all(c in "0123456789abcdef" for c in sha256):
        raise StorageError("Ungültiger SHA-256-Hash")
    return _root() / sha256[:2] / sha256


# ---- Core API ---------------------------------------------------------------


async def store_upload(upload: UploadFile) -> StoredFile:
    """Persist ``upload`` to content-addressed storage.

    Performs, in order:

    1. Sanitise the original filename.
    2. Sniff the mime type from the first 4 KiB; reject if not allowed.
    3. Stream the body into a temp file in the target shard directory,
       hashing as we go and enforcing :attr:`Settings.upload_max_bytes`.
    4. Atomically rename onto ``<shard>/<sha256>``. If the destination
       already exists (dedup hit) we discard the temp file instead — saves
       one fsync and keeps mtime stable for older blobs.

    Raises :class:`StorageError` subclasses on validation failure; the caller
    must translate to HTTP. The temp file is unlinked on every error path so
    we never leak partial bytes.
    """
    settings = get_settings()
    max_bytes = settings.upload_max_bytes

    filename = sanitise_filename(upload.filename or "")

    # ---- Mime sniff (header bytes only) --------------------------------------
    head = await upload.read(_SNIFF_BYTES)
    sniffed = magic.from_buffer(head, mime=True) if head else ""
    if sniffed not in ALLOWED_MIME_TYPES:
        await upload.close()
        raise UnsupportedMediaTypeError(f"Dateityp nicht erlaubt: {sniffed or 'unbekannt'}")

    # Rewind the underlying stream so we can re-read the head bytes into the
    # temp file along with the rest of the body. ``UploadFile.seek`` is async.
    await upload.seek(0)

    # ---- Stream → temp file, hashing & size-capping --------------------------
    # The temp file lives in the *target* shard directory so the final
    # ``os.replace`` is a same-filesystem rename (atomic, no copy).
    root = _root()
    hasher = hashlib.sha256()
    size = 0

    # Pre-create *some* shard dir; the real one is known only after we have
    # the full hash, so we stage in a generic ``.tmp`` subdir and rename
    # into the right shard at the end.
    tmp_dir = root / ".tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = tmp_dir / f"upload-{secrets.token_hex(16)}.part"

    try:
        with tmp_path.open("wb") as fh:
            while True:
                chunk = await upload.read(_CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise FileTooLargeError(
                        f"Datei überschreitet Maximalgrösse von {max_bytes} Byte"
                    )
                hasher.update(chunk)
                fh.write(chunk)
    except StorageError:
        _unlink_quiet(tmp_path)
        raise
    finally:
        await upload.close()

    sha256 = hasher.hexdigest()
    final_path = root / sha256[:2] / sha256
    final_path.parent.mkdir(parents=True, exist_ok=True)

    if final_path.exists():
        # Dedup hit — the existing blob is byte-identical (same hash). Drop
        # the temp file and keep the older blob (preserves mtime for any
        # external indexers we may add later).
        _unlink_quiet(tmp_path)
    else:
        # Atomic rename. On the same filesystem this is a single inode op.
        # ``Path.replace`` wraps ``os.replace`` with the same atomicity guarantee.
        tmp_path.replace(final_path)

    return StoredFile(
        sha256=sha256,
        size_bytes=size,
        mime=sniffed,
        filename=filename,
        path=final_path,
    )


def sniff_mime(stream: IO[bytes]) -> str:
    """Sniff the mime type of an already-open binary stream.

    Exposed for unit tests; production code goes through :func:`store_upload`.
    The stream position is restored on return.
    """
    pos = stream.tell()
    try:
        head = stream.read(_SNIFF_BYTES)
        return magic.from_buffer(head, mime=True) if head else ""
    finally:
        stream.seek(pos)


# ---- Internals --------------------------------------------------------------


def _unlink_quiet(p: Path) -> None:
    """Best-effort unlink; ignore missing-file errors (we may never have created it)."""
    with contextlib.suppress(FileNotFoundError):
        p.unlink()
