import os
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, Form, Header, HTTPException, Request
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from .database import SessionLocal
from .repositories.ballot_repository import InMemoryBallotRepository
from .repositories.sql_repository import SqlBallotRepository
from .services.ballot_service import BallotService

# Infrastructure singletons
templates = Jinja2Templates(directory="templates")

# Register template globals
templates.env.globals.update(get_ballot_status=BallotService.get_status)  # pyright: ignore[reportUnknownMemberType]

CSRF_COOKIE_NAME = "oponn_csrf_token"

# In-memory repo singleton for when DATABASE_URL is not set
_in_memory_repo = InMemoryBallotRepository()
_ballot_service = BallotService(
    _in_memory_repo, redis_url=os.getenv("REDIS_URL")
)  # Exported for tests


async def get_db() -> AsyncGenerator[AsyncSession | None, None]:
    """Dependency for getting a DB session."""
    if SessionLocal is None:
        yield None
        return
    async with SessionLocal() as session:
        yield session


def get_ballot_service(
    session: Annotated[AsyncSession | None, Depends(get_db)] = None,
) -> BallotService:
    """
    Dependency that returns a BallotService.
    If DATABASE_URL is set, it uses SqlBallotRepository with the current session.
    Otherwise, it uses the global InMemoryBallotRepository.
    """
    if os.getenv("DATABASE_URL"):
        if session is None:
            # We allow None only if it's explicitly handled (like in the reaper)
            # but for FastAPI routes, we want to ensure a session exists.
            return _ballot_service
        _ballot_service.repository = SqlBallotRepository(session)
    else:
        _ballot_service.repository = _in_memory_repo

    return _ballot_service


async def get_csrf_token(request: Request) -> str:
    return getattr(request.state, "csrf_token", "")


async def validate_csrf(
    request: Request,
    x_csrf_token_form: Annotated[str | None, Form(alias="X-CSRF-Token")] = None,
    x_csrf_token_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    if os.getenv("OPONN_SKIP_CSRF") == "true":
        return

    csrf_token = x_csrf_token_form or x_csrf_token_header
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token or not csrf_token or csrf_token != cookie_token:
        raise HTTPException(status_code=403, detail="Invalid or Missing CSRF Token")
