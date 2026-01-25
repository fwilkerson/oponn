from typing import Annotated
from fastapi import Request, Form, Header, HTTPException
from fastapi.templating import Jinja2Templates
from .services.ballot_service import BallotService
from .repositories.ballot_repository import InMemoryBallotRepository

# Infrastructure singletons - ENSURE THESE ARE THE ONLY INSTANCES
# so background threads and main threads share the same in-memory state.
templates = Jinja2Templates(directory="templates")
_ballot_repo = InMemoryBallotRepository()
_ballot_service = BallotService(_ballot_repo)

# Register template globals
templates.env.globals.update(get_ballot_status=BallotService.get_status)  # pyright: ignore[reportUnknownMemberType]

CSRF_COOKIE_NAME = "oponn_csrf_token"


def get_ballot_service() -> BallotService:
    return _ballot_service


async def get_csrf_token(request: Request) -> str:
    return getattr(request.state, "csrf_token", "")


async def validate_csrf(
    request: Request,
    x_csrf_token_form: Annotated[str | None, Form(alias="X-CSRF-Token")] = None,
    x_csrf_token_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    import os
    if os.getenv("OPONN_SKIP_CSRF") == "true":
        return

    csrf_token = x_csrf_token_form or x_csrf_token_header
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token or not csrf_token or csrf_token != cookie_token:
        raise HTTPException(status_code=403, detail="Invalid or Missing CSRF Token")