import secrets
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.staticfiles import StaticFiles

from .dependencies import CSRF_COOKIE_NAME
from .models.exceptions import (
    BallotNotFoundError,
    InvalidOptionError,
    VotingNotOpenError,
)
from .routes import sse, ui

app = FastAPI(title="Oponn Voting Service")

# CSRF Skip Configuration
CSRF_SKIP_PATHS = [
    "/static",
    "/ballots/",  # Handled by dynamic check for live-results
]


@app.middleware("http")
async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    path = request.url.path

    # Skip logic
    should_skip = any(path.startswith(p) for p in CSRF_SKIP_PATHS if p != "/ballots/")
    if not should_skip and path.startswith("/ballots/") and "live-results" in path:
        should_skip = True

    if should_skip:
        return await call_next(request)

    # Get existing token or generate a new one
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = secrets.token_urlsafe(32)

    # Make token available to the request state for dependencies and templates
    request.state.csrf_token = token

    response = await call_next(request)

    # Ensure the CSRF cookie is set if not already present
    if CSRF_COOKIE_NAME not in request.cookies:
        response.set_cookie(
            CSRF_COOKIE_NAME,
            token,
            httponly=True,
            samesite="lax",
            secure=False,  # Set to True in production with HTTPS
        )

    return response


# Infrastructure setup
app.mount("/static", StaticFiles(directory="static"), name="static")

# --- Exception Handlers ---


@app.exception_handler(BallotNotFoundError)
async def ballot_not_found_handler(_request: Request, exc: BallotNotFoundError):
    raise HTTPException(status_code=404, detail=str(exc))


@app.exception_handler(VotingNotOpenError)
@app.exception_handler(InvalidOptionError)
async def domain_error_handler(_request: Request, exc: Exception):
    raise HTTPException(status_code=400, detail=str(exc))


# --- Routers ---

app.include_router(ui.router)
app.include_router(sse.router)
