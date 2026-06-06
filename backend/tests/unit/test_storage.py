"""Unit tests for the content-addressed storage service (Phase 6).

Exercises the security-critical decisions: mime sniffing rejects spoofed
Content-Type, the size cap actually trips while streaming, identical content
dedups, and the sharded path layout matches what the download endpoint
expects.
"""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from app.core.config import get_settings
from app.services import storage
from fastapi import UploadFile

# Minimal valid PDF body: header + EOF marker. python-magic recognises this.
PDF_BODY = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n"


@pytest.fixture(autouse=True)
def _isolate_uploads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point ``uploads_dir`` at a per-test tmpdir and reset the settings cache."""
    monkeypatch.setenv("RENO_UPLOADS_DIR", str(tmp_path))
    get_settings.cache_clear()
    yield tmp_path
    get_settings.cache_clear()


def _upload(body: bytes, filename: str = "test.pdf") -> UploadFile:
    """Build a Starlette ``UploadFile`` around an in-memory body."""
    return UploadFile(filename=filename, file=io.BytesIO(body))


@pytest.mark.asyncio
async def test_stores_at_sharded_path_and_returns_metadata(_isolate_uploads: Path) -> None:
    stored = await storage.store_upload(_upload(PDF_BODY))
    expected = _isolate_uploads / stored.sha256[:2] / stored.sha256
    assert stored.path == expected
    assert expected.is_file()
    assert expected.read_bytes() == PDF_BODY
    assert stored.size_bytes == len(PDF_BODY)
    assert stored.mime == "application/pdf"
    assert stored.filename == "test.pdf"


@pytest.mark.asyncio
async def test_dedup_on_identical_content(_isolate_uploads: Path) -> None:
    """Uploading the same bytes twice produces one blob and two metadata rows."""
    a = await storage.store_upload(_upload(PDF_BODY, "first.pdf"))
    b = await storage.store_upload(_upload(PDF_BODY, "second.pdf"))
    assert a.sha256 == b.sha256
    assert a.path == b.path
    # Filenames are preserved per-call even when the blob is shared.
    assert a.filename == "first.pdf"
    assert b.filename == "second.pdf"


@pytest.mark.asyncio
async def test_rejects_unsupported_mime(_isolate_uploads: Path) -> None:
    """python-magic detects plain text → not in allowlist → 415-equivalent."""
    with pytest.raises(storage.UnsupportedMediaTypeError):
        await storage.store_upload(_upload(b"hello world\n", "danger.txt"))


@pytest.mark.asyncio
async def test_rejects_when_size_cap_exceeded(
    monkeypatch: pytest.MonkeyPatch, _isolate_uploads: Path
) -> None:
    # Set a tiny cap below the PDF body length and confirm we abort mid-stream.
    monkeypatch.setenv("RENO_UPLOAD_MAX_BYTES", "10")
    get_settings.cache_clear()
    with pytest.raises(storage.FileTooLargeError):
        await storage.store_upload(_upload(PDF_BODY))
    # No blob written.
    blobs = [p for p in _isolate_uploads.rglob("*") if p.is_file() and ".tmp" not in p.parts]
    assert blobs == []


@pytest.mark.asyncio
async def test_rejects_traversal_filename(_isolate_uploads: Path) -> None:
    with pytest.raises(storage.InvalidFilenameError):
        await storage.store_upload(_upload(PDF_BODY, "../../etc/passwd"))


@pytest.mark.asyncio
async def test_strips_directory_prefix(_isolate_uploads: Path) -> None:
    stored = await storage.store_upload(_upload(PDF_BODY, "subdir/report.pdf"))
    assert stored.filename == "report.pdf"


def test_resolve_path_rejects_garbage_hash() -> None:
    with pytest.raises(storage.StorageError):
        storage.resolve_path("not-a-hex-sha")


def test_sanitise_filename_rejects_null_byte() -> None:
    with pytest.raises(storage.InvalidFilenameError):
        storage.sanitise_filename("ok\x00.pdf")
