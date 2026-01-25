from typing import Annotated
from fastapi import Request, Form, Header, HTTPException
from fastapi.templating import Jinja2Templates
from .services.ballot_service import BallotService
from .repositories.ballot_repository import InMemoryBallotRepository

# Infrastructure singletons
templates = Jinja2Templates(directory="templates")
ballot_repo = InMemoryBallotRepository()
_ballot_service = BallotService(ballot_repo)

CSRF_COOKIE_NAME = "oponn_csrf_token"


def get_ballot_service() -> BallotService:
    return _ballot_service


async def validate_csrf(
    request: Request,
    x_csrf_token_form: Annotated[str | None, Form(alias="X-CSRF-Token")] = None,
    x_csrf_token_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
):
    csrf_token = x_csrf_token_form or x_csrf_token_header
    cookie_token = request.cookies.get(CSRF_COOKIE_NAME)

    if not cookie_token or not csrf_token or csrf_token != cookie_token:
        raise HTTPException(status_code=403, detail="Invalid or Missing CSRF Token")
