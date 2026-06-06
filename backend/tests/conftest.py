"""Shared pytest fixtures for the backend test suite."""

from __future__ import annotations

from collections.abc import AsyncIterator, Iterator

import app.core.db as db_module
import pytest
import pytest_asyncio
from app.core.config import get_settings
from app.core.db import Base, get_session
from app.main import create_app
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# --------------------------------------------------------------------------- #
# Unit tests (no DB)                                                          #
# --------------------------------------------------------------------------- #


@pytest.fixture()
def client() -> Iterator[TestClient]:
    """Plain sync TestClient — for endpoints that don't touch persistence."""
    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


# --------------------------------------------------------------------------- #
# Integration tests (real Postgres via testcontainers)                        #
# --------------------------------------------------------------------------- #


@pytest.fixture(scope="session")
def postgres_url() -> Iterator[str]:
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    try:
        sync_url = container.get_connection_url()
        async_url = sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://").replace(
            "postgresql://", "postgresql+asyncpg://"
        )
        yield async_url
    finally:
        container.stop()


@pytest_asyncio.fixture()
async def _engine(postgres_url: str):
    """Per-test engine bound to the current event loop."""
    engine = create_async_engine(postgres_url, pool_pre_ping=True)
    import app.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture()
async def db_session(_engine) -> AsyncIterator[AsyncSession]:
    SessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session


@pytest_asyncio.fixture()
async def integration_app(_engine, monkeypatch) -> AsyncIterator[FastAPI]:
    """FastAPI app wired to the testcontainers Postgres."""
    monkeypatch.setenv("RENO_ENVIRONMENT", "test")
    get_settings.cache_clear()

    SessionLocal = async_sessionmaker(bind=_engine, expire_on_commit=False)

    async def _override() -> AsyncIterator[AsyncSession]:
        async with SessionLocal() as session:
            yield session

    monkeypatch.setattr(db_module, "engine", _engine)
    monkeypatch.setattr(db_module, "SessionLocal", SessionLocal)

    from app.services import mailer as mailer_module

    mailer_module.SENT.clear()

    app = create_app()
    app.dependency_overrides[get_session] = _override
    yield app
    get_settings.cache_clear()


@pytest_asyncio.fixture()
async def integration_client(integration_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """Async HTTP client running in the same event loop as the DB fixtures."""
    transport = ASGITransport(app=integration_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
