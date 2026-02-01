import asyncio
import os
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Form, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from .database import get_sessionmaker
from .repositories.ballot_repository import (
    BallotRepository,
    InMemoryBallotRepository,
)
from .repositories.sql_ballot_repository import SqlBallotRepository
from .repositories.sql_user_repository import SqlUserRepository
from .repositories.user_repository import (
    InMemoryUserRepository,
    UserRepository,
)
from .services.auth_service import AuthService
from .services.ballot_service import BallotService, BallotStateManager
from .services.crypto_service import CryptoService
from redis import asyncio as aioredis

# Infrastructure singletons
templates = Jinja2Templates(directory="templates")

# Register template globals
templates.env.globals.update(get_ballot_status=BallotService.get_status)

CSRF_COOKIE_NAME = "oponn_csrf_token"
OPONN_ENV = os.getenv("OPONN_ENV", "development").lower()
REDIS_URL = os.getenv("REDIS_URL")

# Singletons that MIGHT capture loop state (initialized lazily per loop)
_redis_clients: dict[asyncio.AbstractEventLoop, aioredis.Redis] = {}
_crypto_services: dict[asyncio.AbstractEventLoop, CryptoService] = {}
_ballot_state_managers: dict[asyncio.AbstractEventLoop, BallotStateManager] = {}
_in_memory_ballot_repos: dict[asyncio.AbstractEventLoop, InMemoryBallotRepository] = {}
_in_memory_user_repos: dict[asyncio.AbstractEventLoop, InMemoryUserRepository] = {}


async def get_redis_client() -> aioredis.Redis | None:
    """Returns a singleton Redis client per loop, initialized on first use."""
    if not REDIS_URL:
        return None
    loop = asyncio.get_running_loop()
    if loop not in _redis_clients:
        _redis_clients[loop] = aioredis.from_url(REDIS_URL, decode_responses=False)
    return _redis_clients[loop]


async def get_crypto_service() -> CryptoService:
    loop = asyncio.get_running_loop()
    if loop not in _crypto_services:
        ks = os.getenv("OPONN_MASTER_KEYSET")
        _crypto_services[loop] = CryptoService(
            master_keyset_json=ks, redis_client=await get_redis_client()
        )
    return _crypto_services[loop]


async def get_ballot_state_manager() -> BallotStateManager:
    loop = asyncio.get_running_loop()
    if loop not in _ballot_state_managers:
        _ballot_state_managers[loop] = BallotStateManager()
    return _ballot_state_managers[loop]


async def get_in_memory_ballot_repo() -> InMemoryBallotRepository:
    loop = asyncio.get_running_loop()
    if loop not in _in_memory_ballot_repos:
        _in_memory_ballot_repos[loop] = InMemoryBallotRepository()
    return _in_memory_ballot_repos[loop]


async def get_in_memory_user_repo() -> InMemoryUserRepository:
    loop = asyncio.get_running_loop()
    if loop not in _in_memory_user_repos:
        _in_memory_user_repos[loop] = InMemoryUserRepository()
    return _in_memory_user_repos[loop]


# Dependency Validation
if OPONN_ENV == "production":
    if not os.getenv("DATABASE_URL"):
        raise RuntimeError("DATABASE_URL must be set in production mode")
    if not REDIS_URL:
        raise RuntimeError("REDIS_URL must be set in production mode")
    if not os.getenv("OPONN_MASTER_KEYSET"):
        raise RuntimeError("OPONN_MASTER_KEYSET must be set in production mode")


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """Dependency for getting a DB session."""
    if os.getenv("DATABASE_URL") is None:
        yield None
        return

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        yield session


async def get_ballot_service(
    session: Annotated[AsyncSession | None, Depends(get_db)] = None,
) -> BallotService:
    """
    Dependency that returns a fresh BallotService instance per request.
    This avoids race conditions where multiple requests might share a singleton
    service while having different request-scoped repositories.
    """
    repo: BallotRepository
    if os.getenv("DATABASE_URL") and session:
        repo = SqlBallotRepository(session)
    else:
        repo = await get_in_memory_ballot_repo()

    return BallotService(
        repository=repo,
        crypto=await get_crypto_service(),
        state_manager=await get_ballot_state_manager(),
        redis_client=await get_redis_client(),
    )


async def get_auth_service(
    session: Annotated[AsyncSession | None, Depends(get_db)] = None,
) -> AuthService:
    """
    Dependency that returns a fresh AuthService instance per request.
    """
    repo: UserRepository
    if os.getenv("DATABASE_URL") and session:
        repo = SqlUserRepository(session)
    else:
        repo = await get_in_memory_user_repo()

    return AuthService(repository=repo)


async def get_csrf_token(request: Request) -> str:
    return getattr(request.state, "csrf_token", "")


async def validate_csrf(
    request: Request,
    x_csrf_token_form: Annotated[str | None, Form(alias="X-CSRF-Token")] = None,
    x_csrf_token_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    # GET requests are exempt from CSRF as they are read-only
    if request.method == "GET":
        return

    if OPONN_ENV != "production" and os.getenv("OPONN_SKIP_CSRF") == "true":
        return

    csrf_token = x_csrf_token_form or x_csrf_token_header
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token or not csrf_token or csrf_token != cookie_token:
        raise HTTPException(status_code=403, detail="Invalid or Missing CSRF Token")
