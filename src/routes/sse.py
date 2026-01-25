import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated, cast

from fastapi import APIRouter, Depends
from jinja2 import Template
from sse_starlette.sse import EventSourceResponse

from ..dependencies import get_ballot_service, templates
from ..services.ballot_service import BallotService

router = APIRouter()


@router.get("/ballots/{ballot_id}/live-results")
async def get_ballot_live_results(
    ballot_id: int, service: Annotated[BallotService, Depends(get_ballot_service)]
):
    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        queue = await service.register_sse_client(ballot_id)
        template = cast(
            Template,
            templates.env.get_template("partials/vote_results.html"),  # pyright: ignore[reportUnknownMemberType]
        )

        try:
            initial_counts = service.get_vote_counts(ballot_id)
            yield {"data": str(template.render(results=initial_counts))}

            while True:
                updated_counts = await queue.get()
                yield {"data": str(template.render(results=updated_counts))}
        except asyncio.CancelledError:
            pass
        finally:
            await service.unregister_sse_client(ballot_id, queue)

    return EventSourceResponse(event_generator())
