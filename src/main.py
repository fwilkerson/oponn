import secrets
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, HTTPException, Request, Response
from starlette.staticfiles import StaticFiles

from .dependencies import CSRF_COOKIE_NAME, get_ballot_service, templates
from .models.exceptions import (
    BallotNotFoundError,
    InvalidOptionError,
    VotingNotOpenError,
)
from .routes import sse, ui

app = FastAPI(title="Oponn Voting Service")


@app.middleware("http")
async def csrf_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    # Get existing token or generate a new one
    token = request.cookies.get(CSRF_COOKIE_NAME)
    if not token:
        token = secrets.token_urlsafe(32)

    # Make token available to the request (so routes/templates can use it)
    request.state.csrf_token = token

    response = await call_next(request)

    # Always set the cookie to ensure persistence
    response.set_cookie(
        CSRF_COOKIE_NAME,
        token,
        httponly=True,
        samesite="lax",
        secure=False,  # Set to True in production
    )

    return response


# Infrastructure setup
app.mount("/static", StaticFiles(directory="static"), name="static")

# Register global helper for templates
_global_service = get_ballot_service()
templates.env.globals.update(get_ballot_status=_global_service.get_status)  # pyright: ignore[reportUnknownMemberType]

# App state for tests (legacy support)
app.state.ballot_service = _global_service

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
