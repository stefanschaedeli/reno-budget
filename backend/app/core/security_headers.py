"""HTTP security-header middleware.

Adds a baseline set of security headers to every response from the API,
without clobbering stricter headers that individual endpoints already set
(e.g. the attachment download endpoint sets its own
``Content-Security-Policy: default-src 'none'`` and we leave that alone).

Header policy (Phase 10):

- ``Strict-Transport-Security`` only when we are sure the connection is HTTPS
  (either ``X-Forwarded-Proto: https`` from the upstream proxy, or
  ``RENO_ENVIRONMENT=production``). Never set on plain ``http://`` requests —
  setting HSTS over HTTP is a no-op per RFC 6797 but we keep things tidy.
- ``X-Content-Type-Options: nosniff`` — always.
- ``X-Frame-Options: DENY`` — always.
- ``Referrer-Policy: strict-origin-when-cross-origin`` — always.
- ``Permissions-Policy`` — disables geolocation/camera/microphone/payment.
- ``Cross-Origin-Opener-Policy: same-origin`` — always.
- ``Content-Security-Policy`` — only for ``text/html`` responses (the SPA is
  served by nginx, but we set a sane default in case anything reaches a
  browser through the API). Skipped for ``/docs`` and ``/redoc`` because
  Swagger-UI needs ``unsafe-inline``/``unsafe-eval`` to render.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import get_settings

_BASELINE: dict[str, str] = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), camera=(), microphone=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}

_HTML_CSP = (
    "default-src 'self'; "
    "img-src 'self' data:; "
    "style-src 'self' 'unsafe-inline'; "
    "script-src 'self'; "
    "connect-src 'self'; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'"
)

_HSTS_VALUE = "max-age=15552000; includeSubDomains"


def _is_https(request: Request) -> bool:
    """Detect HTTPS either directly or through a trusted proxy."""
    if request.url.scheme == "https":
        return True
    forwarded = request.headers.get("x-forwarded-proto", "").lower()
    if forwarded == "https":
        return True
    settings = get_settings()
    return settings.environment == "production"


def _path_is_docs(path: str) -> bool:
    return path.endswith("/docs") or path.endswith("/redoc") or path.endswith("/openapi.json")


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach baseline security headers to every response."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)

        for header, value in _BASELINE.items():
            response.headers.setdefault(header, value)

        if _is_https(request):
            response.headers.setdefault("Strict-Transport-Security", _HSTS_VALUE)

        content_type = response.headers.get("content-type", "").lower()
        if content_type.startswith("text/html") and not _path_is_docs(request.url.path):
            response.headers.setdefault("Content-Security-Policy", _HTML_CSP)

        return response
