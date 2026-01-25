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
    print(f"DEBUG: SSE Connection Request for ballot {ballot_id}")

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        print(f"DEBUG: SSE Generator Started for ballot {ballot_id}")
        queue = await service.register_sse_client(ballot_id)
        template = cast(
            Template,
            templates.env.get_template("partials/vote_results.html"),  # pyright: ignore[reportUnknownMemberType]
        )

        try:
            initial_counts = service.get_vote_counts(ballot_id)
            print(f"DEBUG: SSE Yielding initial counts for ballot {ballot_id}")
            yield {"data": str(template.render(results=initial_counts))}

            while True:
                updated_counts = await queue.get()
                print(f"DEBUG: SSE Yielding updated counts for ballot {ballot_id}")
                yield {"data": str(template.render(results=updated_counts))}
        except asyncio.CancelledError:
            print(f"DEBUG: SSE Connection Cancelled for ballot {ballot_id}")
            pass
        finally:
            print(f"DEBUG: SSE Unregistering client for ballot {ballot_id}")
            await service.unregister_sse_client(ballot_id, queue)

    return EventSourceResponse(event_generator())
