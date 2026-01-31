import asyncio
import secrets
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request, Response
from starlette.staticfiles import StaticFiles

from .dependencies import CSRF_COOKIE_NAME, get_ballot_service
from .logging_conf import configure_logging
from .models.exceptions import (
    BallotNotFoundError,
    InvalidOptionError,
    VotingNotOpenError,
)
from .routes import auth, sse, ui

logger = structlog.stdlib.get_logger()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    """
    Handle startup and shutdown events.
    Starts the background metadata reaper.
    """
    # Startup: Configure logging and start background tasks
    configure_logging()
    logger.info("lifecycle.startup", msg="Application starting up")

    reaper_task = asyncio.create_task(background_reaper())
    yield
    # Shutdown: Stop background tasks
    logger.info("lifecycle.shutdown", msg="Application shutting down")
    __ = reaper_task.cancel()
    try:
        await reaper_task
    except asyncio.CancelledError:
        pass


async def background_reaper():
    """Periodically clean up stale ballot metadata."""
    from .database import SessionLocal
    from .repositories.sql_ballot_repository import SqlBallotRepository

    while True:
        try:
            await asyncio.sleep(60)  # Reap every 60 seconds
            service = get_ballot_service(session=None)

            # If we are using SQL, we need to provide a session for this "reap cycle"
            if SessionLocal is not None:
                async with SessionLocal() as session:
                    # Temporarily point the service to a repository using this session
                    original_repo = service.repository
                    service.repository = SqlBallotRepository(session)
                    try:
                        await service.cleanup_stale_metadata()
                    finally:
                        service.repository = original_repo
            else:
                # In-memory mode
                await service.cleanup_stale_metadata()

        except Exception as e:
            logger.error("background_reaper.error", error=str(e))


app = FastAPI(title="Oponn Voting Service", lifespan=lifespan)


@app.middleware("http")
async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Get existing token or generate a new one
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = secrets.token_urlsafe(32)

    # Make token available to the request state for dependencies and templates
    request.state.csrf_token = token

    response = await call_next(request)

    # Ensure the CSRF cookie is set if not already present
    if CSRF_COOKIE_NAME not in request.cookies:
        from .dependencies import OPONN_ENV

        response.set_cookie(
            CSRF_COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            secure=OPONN_ENV == "production",
        )

    return response


# Infrastructure setup
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Exception Handlers ---


@app.exception_handler(BallotNotFoundError)
async def ballot_not_found_handler(_request: Request, exc: BallotNotFoundError):
    logger.warning("http.not_found", error=str(exc))
    raise HTTPException(status_code=404, detail=str(exc))


@app.exception_handler(VotingNotOpenError)
@app.exception_handler(InvalidOptionError)
async def domain_error_handler(_request: Request, exc: Exception):
    logger.warning("http.bad_request", error=str(exc))
    raise HTTPException(status_code=400, detail=str(exc))


# --- Routers ---

app.include_router(ui.router)
app.include_router(sse.router)
app.include_router(auth.router)
