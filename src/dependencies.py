import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Form, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from redis import asyncio as aioredis
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
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
from .services.kms_provider import MasterKeyProvider

# Infrastructure singletons
templates = Jinja2Templates(directory="templates")

# Register template globals
templates.env.globals.update(get_ballot_status=BallotService.get_status)

CSRF_COOKIE_NAME = "oponn_csrf_token"

# Singletons that MIGHT capture loop state (initialized lazily per loop)
_redis_clients: dict[asyncio.AbstractEventLoop, aioredis.Redis] = {}
_crypto_services: dict[asyncio.AbstractEventLoop, CryptoService] = {}
_ballot_state_managers: dict[asyncio.AbstractEventLoop, BallotStateManager] = {}
_in_memory_ballot_repos: dict[asyncio.AbstractEventLoop, InMemoryBallotRepository] = {}
_in_memory_user_repos: dict[asyncio.AbstractEventLoop, InMemoryUserRepository] = {}


async def get_redis_client() -> aioredis.Redis | None:
    """Returns a singleton Redis client per loop, initialized on first use."""
    if not settings.redis_url:
        return None
    loop = asyncio.get_running_loop()
    if loop not in _redis_clients:
        _redis_clients[loop] = aioredis.from_url(
            str(settings.redis_url), decode_responses=False
        )
    return _redis_clients[loop]


async def get_crypto_service() -> CryptoService:
    loop = asyncio.get_running_loop()
    if loop not in _crypto_services:
        from .services.kms_provider import (
            AwsKmsMasterKeyProvider,
            LocalMasterKeyProvider,
        )

        provider: MasterKeyProvider
        if not settings.oponn_kms_key_id:
            if settings.is_production or settings.is_staging:
                raise RuntimeError("OPONN_KMS_KEY_ID must be set in staging/production")
            provider = LocalMasterKeyProvider()
        else:
            # Configuration already contains defaults or strictly validated values
            endpoint = settings.localstack_endpoint

            provider = AwsKmsMasterKeyProvider(
                key_id=settings.oponn_kms_key_id,
                endpoint_url=endpoint,
                access_key=settings.aws_access_key_id,
                secret_key=settings.aws_secret_access_key,
                region=settings.aws_region,
                is_production=settings.is_production,
            )

        _crypto_services[loop] = CryptoService(
            provider=provider, redis_client=await get_redis_client()
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


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """Dependency for getting a DB session."""
    if settings.is_in_memory:
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
    if not settings.is_in_memory and session:
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
    if not settings.is_in_memory and session:
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

    if not settings.is_production and settings.oponn_skip_csrf:
        return

    csrf_token = x_csrf_token_form or x_csrf_token_header
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token or not csrf_token or csrf_token != cookie_token:
        raise HTTPException(status_code=403, detail="Invalid or Missing CSRF Token")
