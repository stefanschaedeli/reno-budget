"""FastAPI application factory.

Kept deliberately small: wiring only. Business logic lives in ``app.services``
and ``app.api.v1.*`` routers. Tests import :func:`create_app` to obtain a fresh
app instance with overridable dependencies.
"""

from __future__ import annotations

from fastapi import FastAPI

from app import __version__
from app.api.v1 import health
from app.core.config import get_settings


def create_app() -> FastAPI:
    """Build and return the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Reno-Budget API",
        version=__version__,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    app.include_router(health.router, prefix=settings.api_prefix)

    return app


app = create_app()
