import asyncio
import secrets
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, HTTPException, Request
from starlette.staticfiles import StaticFiles

from .config import ProductionSettings, TestingSettings, settings
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

    reaper_task = None
    if not isinstance(settings, TestingSettings):
        reaper_task = asyncio.create_task(background_reaper())

    yield
    # Shutdown: Stop background tasks
    logger.info("lifecycle.shutdown", msg="Application shutting down")
    if reaper_task:
        reaper_task.cancel()
        try:
            await reaper_task
        except asyncio.CancelledError:
            pass


async def background_reaper():
    """Periodically clean up stale ballot metadata."""
    from .database import get_sessionmaker

    while True:
        try:
            await asyncio.sleep(60)  # Reap every 60 seconds

            # If we are using SQL, we need to provide a session
            if settings.database_url:
                session_factory = get_sessionmaker()
                async with session_factory() as session:
                    service = await get_ballot_service(session=session)
                    await service.cleanup_stale_metadata()
            else:
                # In-memory mode
                service = await get_ballot_service(session=None)
                await service.cleanup_stale_metadata()

        except Exception as e:
            logger.error("background_reaper.error", error=str(e))


# Standard middleware for CSRF cookie management
class CSRFMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive)

        # Get existing token or generate a new one
        token = request.cookies.get(CSRF_COOKIE_NAME, secrets.token_urlsafe(32))

        # Make token available to the request state
        request.state.csrf_token = token

        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Ensure the CSRF cookie is set if not already present
                if CSRF_COOKIE_NAME not in request.cookies:
                    # We need to add the Set-Cookie header
                    headers = message.get("headers", [])
                    cookie_val = (
                        f"{CSRF_COOKIE_NAME}={token}; HttpOnly; SameSite=Lax; Path=/"
                    )
                    if isinstance(settings, ProductionSettings):
                        cookie_val += "; Secure"

                    headers.append((b"set-cookie", cookie_val.encode()))
                    message["headers"] = headers

            await send(message)

        await self.app(scope, receive, send_wrapper)


app = FastAPI(title="Oponn Voting Service", lifespan=lifespan)
app.add_middleware(CSRFMiddleware)


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
