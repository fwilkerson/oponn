from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import ValidationError

from ..dependencies import get_ballot_service, get_csrf_token, templates, validate_csrf
from ..models.ballot_models import (
    BallotCreateForm,
    VoteForm,
    format_pydantic_errors,
)
from ..services.ballot_service import BallotService

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    service: Annotated[BallotService, Depends(get_ballot_service)],
    csrf_token: Annotated[str, Depends(get_csrf_token)],
):
    ballots = await service.list_ballots()
    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={"ballots": ballots, "active_page": "index", "csrf_token": csrf_token},
    )


@router.get("/create", response_class=HTMLResponse)
async def create_page(
    request: Request, csrf_token: Annotated[str, Depends(get_csrf_token)]
):
    return templates.TemplateResponse(
        request=request,
        name="create.html",
        context={"active_page": "create", "csrf_token": csrf_token},
    )


@router.get("/partials/start-time-input", response_class=HTMLResponse)
async def start_time_input(request: Request, start_time_type: str):
    if start_time_type == "scheduled":
        return templates.TemplateResponse(
            request=request, name="partials/start_time_input.html"
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
    # Internal helper to re-render form with error
    def render_error(
        error_msg: str | None = None, field_errors: dict[str, str] | None = None
    ):
        template_name = "create.html"
        if request.headers.get("HX-Request"):
            template_name = "partials/create_form.html"

        context = {
            "active_page": "create",
            "csrf_token": getattr(request.state, "csrf_token", ""),
            "measure": measure,
            "options_raw": options_raw,
            "allow_write_in": allow_write_in,
            "start_time_type": start_time_type,
            "scheduled_start_time": scheduled_start_time,
            "duration_mins": duration_mins,
        }

        if error_msg:
            context["error"] = error_msg
        if field_errors:
            context["field_errors"] = field_errors

        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

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
        return render_error(error_msg=error_msg, field_errors=field_errors)

    except Exception as e:
        err_str = str(e).split("\n")[0]
        return render_error(error_msg=err_str)

    new_ballot = await service.create_ballot(ballot_create)

    if request.headers.get("HX-Request"):
        response = Response(status_code=204)
        response.headers["HX-Redirect"] = f"/vote/{new_ballot.ballot_id}"
        return response

    return RedirectResponse(url=f"/vote/{new_ballot.ballot_id}", status_code=303)


@router.get("/vote/{ballot_id}", response_class=HTMLResponse)
async def vote_page(
    request: Request,
    ballot_id: int,
    service: Annotated[BallotService, Depends(get_ballot_service)],
    csrf_token: Annotated[str, Depends(get_csrf_token)],
):
    ballot = await service.get_ballot(ballot_id)
    return templates.TemplateResponse(
        request=request,
        name="vote.html",
        context={"ballot": ballot, "csrf_token": csrf_token},
    )


@router.post("/vote/{ballot_id}", response_class=HTMLResponse)
async def process_vote(
    request: Request,
    ballot_id: int,
    service: Annotated[BallotService, Depends(get_ballot_service)],
    _: Annotated[None, Depends(validate_csrf)],
    option: Annotated[str, Form()] = "",
    write_in_value: Annotated[str | None, Form()] = None,
):
    async def render_error(
        error_msg: str | None = None, field_errors: dict[str, str] | None = None
    ):
        ballot = await service.get_ballot(ballot_id)
        template_name = "vote.html"
        if request.headers.get("HX-Request"):
            template_name = "partials/vote_form.html"

        context = {
            "ballot": ballot,
            "csrf_token": getattr(request.state, "csrf_token", ""),
        }
        if error_msg:
            context["error"] = error_msg
        if field_errors:
            context["field_errors"] = field_errors

        return templates.TemplateResponse(
            request=request,
            name=template_name,
            context=context,
        )

    try:
        # 1. Load the raw form data into our VoteForm model
        form_data = VoteForm(option=option, write_in_value=write_in_value)
        # 2. Convert and validate to our core Vote model
        vote = form_data.to_vote()

    except ValidationError as e:
        error_msg, field_errors = format_pydantic_errors(
            e, field_mapping={"option": "write_in_value"}
        )
        return await render_error(error_msg=error_msg, field_errors=field_errors)

    except ValueError as e:
        # Handle custom ValueErrors from to_vote (like 'Write-in value required')
        if option == "__write_in__":
            return await render_error(field_errors={"write_in_value": str(e)})
        return await render_error(error_msg=str(e))
    except Exception as e:
        return await render_error(error_msg=str(e))

    await service.record_vote(ballot_id, vote)

    if request.headers.get("HX-Request"):
        response = Response(status_code=204)
        response.headers["HX-Redirect"] = f"/results/{ballot_id}"
        return response

    return RedirectResponse(url=f"/results/{ballot_id}", status_code=303)


@router.get("/results/{ballot_id}", response_class=HTMLResponse)
async def results_page(
    request: Request,
    ballot_id: int,
    service: Annotated[BallotService, Depends(get_ballot_service)],
    csrf_token: Annotated[str, Depends(get_csrf_token)],
):
    ballot = await service.get_ballot(ballot_id)
    results = await service.get_vote_counts(ballot_id)
    return templates.TemplateResponse(
        request=request,
        name="results.html",
        context={"ballot": ballot, "results": results, "csrf_token": csrf_token},
    )
