"""Smoke test: build the production api image and verify it boots end-to-end.

This catches a class of bugs that unit/integration tests cannot detect because
those tests run inside the source tree with the dev venv on sys.path. The image
is what gets deployed — we have to actually run it.

Specifically guards against:

* Missing files in the Dockerfile build context (e.g. README.md referenced
  from pyproject but not copied in)
* Wrong PATH/PYTHONPATH so a binary's shebang resolves but its package does
  not import
* Alembic migrations not being applied at startup
* `app.main:create_app()` failing to import for any reason

Slow (~60-120s on a cold image build, ~15s with cache). Marked with the
``smoke`` marker; the default ``pytest`` invocation skips it. CI / pre-deploy
flows run ``pytest -m smoke``.

Skip the build with ``RENO_SKIP_IMAGE_BUILD=1`` to reuse an existing
``reno-budget-api:smoke`` tag (useful for iterating on the test itself).
"""

from __future__ import annotations

import os
import shutil
import socket
import subprocess
import time
from pathlib import Path

import httpx
import pytest

pytestmark = pytest.mark.smoke

REPO_ROOT = Path(__file__).resolve().parents[3]
IMAGE_TAG = "reno-budget-api:smoke"
STARTUP_TIMEOUT_S = 60


def _docker_available() -> bool:
    if shutil.which("docker") is None:
        return False
    try:
        result = subprocess.run(
            ["docker", "info"],
            check=False,
            capture_output=True,
            timeout=5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return result.returncode == 0


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_for_health(url: str, deadline: float) -> None:
    last_err: Exception | None = None
    while time.monotonic() < deadline:
        try:
            response = httpx.get(url, timeout=2.0)
            if response.status_code == 200:
                return
            last_err = RuntimeError(f"healthz returned {response.status_code}: {response.text!r}")
        except httpx.HTTPError as exc:
            last_err = exc
        time.sleep(1.0)
    raise AssertionError(f"healthz never became green: {last_err}")


@pytest.fixture(scope="module")
def api_image() -> str:
    if not _docker_available():
        pytest.skip("docker is unavailable; smoke test cannot run")

    if os.environ.get("RENO_SKIP_IMAGE_BUILD") == "1":
        return IMAGE_TAG

    build = subprocess.run(
        [
            "docker",
            "build",
            "-f",
            "deploy/Dockerfile.api",
            "-t",
            IMAGE_TAG,
            ".",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        pytest.fail(
            "docker build failed:\nSTDOUT:\n"
            + build.stdout[-4000:]
            + "\nSTDERR:\n"
            + build.stderr[-4000:]
        )
    return IMAGE_TAG


@pytest.fixture(scope="module")
def smoke_postgres() -> tuple[str, str]:
    """Boot a throwaway Postgres reachable from the api container.

    Returns ``(container_id, connection_url_for_api)`` where the URL uses the
    container's network alias so the api can resolve it.
    """
    from testcontainers.postgres import PostgresContainer

    container = PostgresContainer("postgres:16-alpine")
    container.start()
    try:
        sync_url = container.get_connection_url()
        # Rewrite localhost → host.docker.internal so the api container can
        # reach the postgres container exposed on the host.
        host_port = container.get_exposed_port(5432)
        # Build the URL the API expects (psycopg2 driver name)
        username = container.username
        password = container.password
        dbname = container.dbname
        api_url = (
            f"postgresql+asyncpg://{username}:{password}"
            f"@host.docker.internal:{host_port}/{dbname}"
        )
        yield sync_url, api_url
    finally:
        container.stop()


def test_api_image_boots_and_serves_healthz(
    api_image: str,
    smoke_postgres: tuple[str, str],
) -> None:
    """Build, start, hit /healthz, tear down."""
    _, api_url = smoke_postgres
    host_port = _free_port()

    run = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "-d",
            "--add-host=host.docker.internal:host-gateway",
            "-e",
            f"RENO_DATABASE_URL={api_url}",
            "-e",
            "RENO_JWT_SECRET=smoke-test-secret-do-not-use-in-prod",
            "-e",
            "RENO_LOG_LEVEL=WARNING",
            "-p",
            f"{host_port}:8000",
            api_image,
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    if run.returncode != 0:
        pytest.fail(f"docker run failed: {run.stderr}")

    container_id = run.stdout.strip()
    try:
        deadline = time.monotonic() + STARTUP_TIMEOUT_S
        _wait_for_health(f"http://127.0.0.1:{host_port}/api/v1/healthz", deadline)

        # Sanity: the body should be JSON with status=ok. This catches the
        # case where /healthz returns 200 from a generic reverse proxy but
        # not from the real app.
        response = httpx.get(f"http://127.0.0.1:{host_port}/api/v1/healthz", timeout=5.0)
        assert response.status_code == 200
        body = response.json()
        assert body.get("status") == "ok", body

        # And a real route to confirm routing + DB connectivity work past
        # the healthz shortcut. The openapi spec is at /api/v1/openapi.json
        # (FastAPI mounts it under the configured api_prefix).
        spec = httpx.get(f"http://127.0.0.1:{host_port}/api/v1/openapi.json", timeout=5.0)
        assert spec.status_code == 200, spec.text[:500]
        assert "/api/v1/healthz" in spec.text, "openapi spec does not list healthz route"

        # Hit a DB-backed endpoint so a missing/stale migration would be
        # detected. Login with bogus creds should return 401 (DB queried,
        # no user matched) or 422 (validation). Anything 5xx means the DB
        # layer is broken (missing table, etc.).
        login = httpx.post(
            f"http://127.0.0.1:{host_port}/api/v1/auth/login",
            json={"email": "smoke@example.com", "password": "wrong-password"},
            timeout=5.0,
        )
        assert login.status_code < 500, (
            f"login returned {login.status_code} — DB layer is broken (likely missing migration). "
            f"Body: {login.text[:300]}"
        )
    finally:
        # Capture last log lines for failure diagnostics.
        logs = subprocess.run(
            ["docker", "logs", "--tail", "80", container_id],
            check=False,
            capture_output=True,
            text=True,
        )
        if logs.stdout:
            print("=== api container stdout ===")
            print(logs.stdout)
        if logs.stderr:
            print("=== api container stderr ===")
            print(logs.stderr)
        subprocess.run(
            ["docker", "rm", "-f", container_id],
            check=False,
            capture_output=True,
        )


def test_alembic_runs_inside_image(api_image: str, smoke_postgres: tuple[str, str]) -> None:
    """The entrypoint runs alembic upgrade head before uvicorn.

    Verify by overriding the CMD to print the resulting revision.
    """
    _, api_url = smoke_postgres
    result = subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--add-host=host.docker.internal:host-gateway",
            "-e",
            f"RENO_DATABASE_URL={api_url}",
            "-e",
            "RENO_JWT_SECRET=smoke-test-secret-do-not-use-in-prod",
            api_image,
            "alembic",
            "current",
        ],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, f"alembic current failed:\n{result.stderr}"
    # alembic current prints the revision id on stdout; entrypoint also ran
    # `alembic upgrade head` first, so the head should now be applied.
    combined = result.stdout + result.stderr
    assert "head" in combined.lower(), combined
