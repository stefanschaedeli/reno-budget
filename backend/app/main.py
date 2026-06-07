"""FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app import __version__
from app.api.v1 import attachments as attachments_router
from app.api.v1 import audit as audit_router
from app.api.v1 import auth as auth_router
from app.api.v1 import bkp as bkp_router
from app.api.v1 import budgets as budgets_router
from app.api.v1 import cost_items as cost_items_router
from app.api.v1 import exports as exports_router
from app.api.v1 import finances as finances_router
from app.api.v1 import health
from app.api.v1 import objects as objects_router
from app.api.v1 import projects as projects_router
from app.api.v1 import renofond as renofond_router
from app.api.v1 import tags as tags_router
from app.core.config import get_settings
from app.core.security_headers import SecurityHeadersMiddleware


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="Reno-Budget API",
        version=__version__,
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
    )

    # Rate limiter (slowapi). Disabled under RENO_ENVIRONMENT=test so the
    # test suite isn't throttled by per-IP login limits.
    auth_router.limiter.enabled = settings.environment != "test"
    app.state.limiter = auth_router.limiter
    app.add_middleware(SlowAPIMiddleware)
    app.add_middleware(SecurityHeadersMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def _rate_limit_handler(_request: Request, exc: RateLimitExceeded) -> JSONResponse:
        return JSONResponse(
            status_code=429,
            content={"detail": f"Zu viele Anfragen — bitte später erneut versuchen ({exc.detail})"},
        )

    app.include_router(health.router, prefix=settings.api_prefix)
    app.include_router(auth_router.router, prefix=settings.api_prefix)
    app.include_router(objects_router.router, prefix=settings.api_prefix)
    app.include_router(bkp_router.router, prefix=settings.api_prefix)
    app.include_router(cost_items_router.router, prefix=settings.api_prefix)
    app.include_router(budgets_router.router, prefix=settings.api_prefix)
    app.include_router(renofond_router.router, prefix=settings.api_prefix)
    app.include_router(finances_router.router, prefix=settings.api_prefix)
    app.include_router(attachments_router.router, prefix=settings.api_prefix)
    app.include_router(audit_router.router, prefix=settings.api_prefix)
    app.include_router(exports_router.router, prefix=settings.api_prefix)
    app.include_router(projects_router.router_objects, prefix=settings.api_prefix)
    app.include_router(projects_router.router_projects, prefix=settings.api_prefix)
    app.include_router(tags_router.router_objects, prefix=settings.api_prefix)
    app.include_router(tags_router.router_tags, prefix=settings.api_prefix)
    app.include_router(tags_router.router_target_tags, prefix=settings.api_prefix)

    return app


app = create_app()
