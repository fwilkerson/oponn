from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from ..dependencies import get_ballot_service, templates, validate_csrf
from ..models.ballot_models import (
    BallotCreateForm,
    VoteForm,
    format_pydantic_errors,
)
from ..services.ballot_service import BallotService
from .auth import get_current_user_id

router = APIRouter()


def render_template(
    request: Request,
    name: str,
    context: dict[str, object],
    partial_name: str | None = None,
) -> Response:
    """
    Helper to render a template, optionally switching to a partial if HX-Request is present.
    """
    template_name = name
    if partial_name and request.headers.get("HX-Request"):
        template_name = partial_name

    # Ensure CSRF token is always available in context if present in request state
    if "csrf_token" not in context:
        context["csrf_token"] = getattr(request.state, "csrf_token", "")

    context["user_id"] = get_current_user_id(request)

    return templates.TemplateResponse(
        request=request,
        name=template_name,
        context=context,
    )


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    service: Annotated[BallotService, Depends(get_ballot_service)],
):
    user_id = get_current_user_id(request)
    ballots = []
    if user_id:
        all_ballots = await service.list_ballots()
        ballots = [b for b in all_ballots if b.owner_id == user_id]

    return render_template(
        request,
        "index.html",
        {"ballots": ballots, "active_page": "index"},
    )


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    return render_template(
        request,
        "login.html",
        {"active_page": "login"},
    )


@router.get("/create", response_class=HTMLResponse)
async def create_page(request: Request):
    return render_template(
        request,
        "create.html",
        {"active_page": "create"},
    )


@router.get("/partials/start-time-input", response_class=HTMLResponse)
async def start_time_input(request: Request, start_time_type: str):
    if start_time_type == "scheduled":
        return templates.TemplateResponse(
            request=request, name="partials/start-time-input.html"
        )
    return HTMLResponse("")


@router.post("/create", response_class=HTMLResponse)
async def process_create(
    request: Request,
    service: Annotated[BallotService, Depends(get_ballot_service)],
    _: Annotated[None, Depends(validate_csrf)],
    measure: Annotated[str, Form()] = "",
    options_raw: Annotated[str, Form()] = "",
    allow_write_in: Annotated[bool, Form()] = False,
    start_time_type: Annotated[str, Form()] = "now",
    scheduled_start_time: Annotated[str | None, Form()] = None,
    duration_mins: Annotated[int, Form()] = 0,
):
    # Context shared between normal and error rendering
    context: dict[str, object] = {
        "active_page": "create",
        "measure": measure,
        "options_raw": options_raw,
        "allow_write_in": allow_write_in,
        "start_time_type": start_time_type,
        "scheduled_start_time": scheduled_start_time,
        "duration_mins": duration_mins,
    }

    try:
        # 1. Load the raw form data into our Form Model
        form_data = BallotCreateForm(
            measure=measure,
            options_raw=options_raw,
            allow_write_in=allow_write_in,
            start_time_type=start_time_type,
            scheduled_start_time=scheduled_start_time,
            duration_mins=duration_mins,
        )
        # 2. Convert to our core BallotCreate model (which does further domain validation)
        ballot_create = form_data.to_ballot_create()

    except ValidationError as e:
        error_msg, field_errors = format_pydantic_errors(
            e, field_mapping={"options": "options_raw"}
        )
        context.update({"error": error_msg, "field_errors": field_errors})
        return render_template(
            request, "create.html", context, "partials/create_form.html"
        )

    except Exception as e:
        err_str = str(e).split("\n")[0]
        context["error"] = err_str
        return render_template(
            request, "create.html", context, "partials/create_form.html"
        )

    user_id = get_current_user_id(request)
    new_ballot = await service.create_ballot(ballot_create, owner_id=user_id)

    if request.headers.get("HX-Request"):
        response = Response(status_code=204)
        response.headers["HX-Redirect"] = f"/vote/{new_ballot.ballot_id}"
        return response

    return RedirectResponse(url=f"/vote/{new_ballot.ballot_id}", status_code=303)


@router.get("/vote/{ballot_id}", response_class=HTMLResponse)
async def vote_page(
    request: Request,
    ballot_id: str,
    service: Annotated[BallotService, Depends(get_ballot_service)],
):
    ballot = await service.get_ballot(ballot_id)
    has_voted = request.cookies.get(f"voted_{ballot_id}")
    return render_template(
        request, "vote.html", {"ballot": ballot, "has_voted": has_voted}
    )


@router.post("/vote/{ballot_id}", response_class=HTMLResponse)
async def process_vote(
    request: Request,
    ballot_id: str,
    service: Annotated[BallotService, Depends(get_ballot_service)],
    _: Annotated[None, Depends(validate_csrf)],
    option_id: Annotated[str, Form()] = "",
    write_in_value: Annotated[str | None, Form()] = None,
):
    if request.cookies.get(f"voted_{ballot_id}"):
        ballot = await service.get_ballot(ballot_id)
        return render_template(
            request,
            "vote.html",
            {"ballot": ballot, "error": "You have already voted on this ballot."},
        )

    try:
        # 1. Load the raw form data into our VoteForm model
        form_data = VoteForm(option_id=option_id, write_in_value=write_in_value)
        # 2. Convert and validate to our core Vote model
        vote = form_data.to_vote()

    except (ValidationError, ValueError, Exception) as e:
        ballot = await service.get_ballot(ballot_id)
        context: dict[str, object] = {"ballot": ballot}

        if isinstance(e, ValidationError):
            error_msg, field_errors = format_pydantic_errors(
                e,
                field_mapping={
                    "option_id": "option_id",
                    "write_in_value": "write_in_value",
                },
            )
            context.update({"error": error_msg, "field_errors": field_errors})
        elif isinstance(e, ValueError) and option_id == "__write_in__":
            context["field_errors"] = {"write_in_value": str(e)}
        else:
            context["error"] = str(e)

        return render_template(request, "vote.html", context, "partials/vote_form.html")

    await service.record_vote(ballot_id, vote)

    if request.headers.get("HX-Request"):
        response = Response(status_code=204)
        response.headers["HX-Redirect"] = f"/results/{ballot_id}"
        response.set_cookie(f"voted_{ballot_id}", "true", max_age=60 * 60 * 24 * 365)
        return response

    response = RedirectResponse(url=f"/results/{ballot_id}", status_code=303)
    response.set_cookie(f"voted_{ballot_id}", "true", max_age=60 * 60 * 24 * 365)
    return response


@router.get("/results/{ballot_id}", response_class=HTMLResponse)
async def results_page(
    request: Request,
    ballot_id: str,
    service: Annotated[BallotService, Depends(get_ballot_service)],
):
    ballot = await service.get_ballot(ballot_id)
    results = await service.get_vote_counts(ballot_id)
    return render_template(
        request, "results.html", {"ballot": ballot, "results": results}
    )
