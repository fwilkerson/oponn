from datetime import datetime, timedelta, timezone
from typing import Annotated, cast
from pydantic import ValidationError

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse

from ..dependencies import get_ballot_service, templates, validate_csrf, get_csrf_token
from ..models.ballot_models import BallotCreate, Vote
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
    options = [o.strip() for o in options_raw.split(",") if o.strip()]

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

    if start_time_type == "scheduled":
        if not scheduled_start_time:
            return render_error(
                field_errors={
                    "scheduled_start_time": "Scheduled start time is required"
                }
            )
        try:
            st = datetime.fromisoformat(scheduled_start_time.replace("Z", "+00:00"))
        except ValueError:
            return render_error(
                field_errors={
                    "scheduled_start_time": "Invalid scheduled start time format"
                }
            )

        if st < datetime.now(timezone.utc):
            return render_error(
                field_errors={
                    "scheduled_start_time": "Scheduled start time must be in the future"
                }
            )
    else:
        st = datetime.now(timezone.utc)

    et = st + timedelta(minutes=duration_mins) if duration_mins > 0 else None

    try:
        ballot_create = BallotCreate(
            measure=measure,
            options=options,
            allow_write_in=allow_write_in,
            start_time=st,
            end_time=et,
        )
    except ValidationError as e:
        field_errors: dict[str, str] = {}
        global_errors: list[str] = []

        for err in e.errors():
            loc = err["loc"]
            msg = err["msg"].replace("Value error, ", "")
            if loc and loc[0] in (
                "measure",
                "options",
                "scheduled_start_time",
            ):  # specific fields
                # map 'options' model field to 'options_raw' form field name if needed,
                # but here validation might be on 'options' list after split.
                # The form field is 'options_raw'.
                field_name = str(loc[0])
                if field_name == "options":
                    field_name = "options_raw"
                field_errors[field_name] = msg
            else:
                global_errors.append(msg)

        return render_error(
            error_msg="; ".join(global_errors) if global_errors else None,
            field_errors=field_errors,
        )
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
    is_write_in = option == "__write_in__"
    vote_option = write_in_value if is_write_in else option

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

    if is_write_in:
        if not vote_option:
            return await render_error(
                field_errors={"write_in_value": "Write-in value required"}
            )
        from bs4 import BeautifulSoup

        vote_option = BeautifulSoup(vote_option, "html.parser").get_text()

    try:
        vote = Vote(option=cast(str, vote_option), is_write_in=is_write_in)
    except ValidationError as e:
        field_errors: dict[str, str] = {}
        for err in e.errors():
            loc = err["loc"]
            msg = err["msg"].replace("Value error, ", "")
            if loc:
                field_errors[str(loc[0])] = msg
        return await render_error(field_errors=field_errors)
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
