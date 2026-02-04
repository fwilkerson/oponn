# ruff: noqa: E402
import os

# Set environment to testing before any other imports
os.environ["OPONN_ENV"] = "testing"
os.environ["OPONN_SKIP_CSRF"] = "true"

import socket
import threading
import time
from typing import AsyncGenerator

import pytest
import pytest_asyncio
import uvicorn
from httpx import ASGITransport, AsyncClient
from src.dependencies import (
    get_ballot_state_manager,
    get_in_memory_ballot_repo,
    get_crypto_service,
    validate_csrf,
)
from src.database import get_engine
from src.main import app
from src.config import settings
from testcontainers.postgres import PostgresContainer
from testcontainers.redis import RedisContainer
from testcontainers.localstack import LocalStackContainer
from sqlalchemy.ext.asyncio import create_async_engine
from src.repositories.models import Base


@pytest.fixture(scope="session", autouse=True)
def infra_containers():
    """Starts Postgres, Redis, and LocalStack containers for the entire test session."""
    with (
        PostgresContainer("postgres:16-alpine") as postgres,
        RedisContainer("redis:7-alpine") as redis,
        LocalStackContainer("localstack/localstack:latest") as localstack,
    ):
        # Get connection URLs
        db_url = postgres.get_connection_url().replace("psycopg2", "asyncpg")
        redis_url = (
            f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}"
        )
        ls_endpoint = localstack.get_url()

        # Set environment variables for the application and tests to use
        os.environ["DATABASE_URL"] = db_url
        os.environ["REDIS_URL"] = redis_url
        os.environ["LOCALSTACK_ENDPOINT"] = ls_endpoint

        # Initialize KMS key in LocalStack
        import boto3

        kms = boto3.client(
            "kms",
            endpoint_url=ls_endpoint,
            region_name="us-east-1",
            aws_access_key_id="test",
            aws_secret_access_key="test",
        )
        response = kms.create_key(Description="Test KEK")
        os.environ["OPONN_KMS_KEY_ID"] = response["KeyMetadata"]["KeyId"]

        # Force settings to reload from updated environment
        settings.__init__()

        # Sync-style engine for schema creation (using the async engine's run_sync)
        # We need a temporary engine because the singleton one might not be ready
        async def init_db():
            engine = create_async_engine(db_url)
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            await engine.dispose()

        import asyncio

        asyncio.run(init_db())

        yield {
            "postgres": postgres,
            "redis": redis,
            "db_url": db_url,
            "redis_url": redis_url,
        }


def pytest_assertrepr_compare(op: str, left: object, right: object) -> list[str] | None:
    """Custom assertion representation for HTML string comparisons."""
    if (
        isinstance(left, str)
        and isinstance(right, str)
        and op == "in"
        and "<html" in right.lower()
    ):
        try:
            from bs4 import BeautifulSoup

            # Prettify the HTML for easier reading
            right_pretty = BeautifulSoup(right, "html.parser").prettify()
        except ImportError:
            right_pretty = right

        # Write to a temp file for full inspection
        import os

        # Use the project's temp dir if we can identify it, otherwise system temp
        temp_dir = os.path.join(os.getcwd(), ".pytest_failures")
        os.makedirs(temp_dir, exist_ok=True)
        dump_path = os.path.join(temp_dir, "failure_output.html")
        with open(dump_path, "w") as f:
            f.write(right)

        lines = [
            "HTML Comparison Failure:",
            f"Expected string: '{left}'",
            f"Full HTML content dumped to: {dump_path}",
            "Prettified HTML context:",
        ]
        lines.extend(right_pretty.splitlines())
        return lines


def get_free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest_asyncio.fixture(autouse=True)
async def reset_service():
    """Resets the global service state before each test to ensure isolation."""
    # Reset shared State Manager
    state = await get_ballot_state_manager()
    state.clear()

    # Reset Crypto Cache
    crypto = await get_crypto_service()
    crypto._l1_cache.clear()

    # Reset in-memory repo
    repo = await get_in_memory_ballot_repo()
    repo.ballots_db.clear()
    repo.votes_db.clear()
    repo.options_db.clear()
    repo._opt_id_counter = 1

    # Reset SQL Database if using it
    if os.getenv("DATABASE_URL"):
        from sqlalchemy import text

        engine = get_engine()
        async with engine.begin() as conn:
            # Disable foreign key checks temporarily to truncate all tables
            await conn.execute(text("TRUNCATE ballots, options, votes, users CASCADE"))


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    # Override CSRF for local TestClient tests
    app.dependency_overrides[validate_csrf] = lambda: None

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def server_url(infra_containers):
    """Starts a real server in a background thread for SSE and functional tests."""
    # Disable CSRF for the background server during tests
    os.environ["OPONN_SKIP_CSRF"] = "true"

    port = get_free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run)
    thread.daemon = True
    thread.start()

    # Wait for server to start
    url = f"http://127.0.0.1:{port}"
    start_time = time.time()
    while time.time() - start_time < 5:
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=0.1):
                break
        except (OSError, ConnectionRefusedError):
            time.sleep(0.1)
    else:
        pytest.fail("Server failed to start in background")

    yield url

    server.should_exit = True
    thread.join(timeout=2)
    os.environ.pop("OPONN_SKIP_CSRF", None)
