import asyncio

import httpx
import pytest


async def test_sse_updates_robust(server_url: str):
    """
    Test that voting on a ballot triggers an SSE update on the live results page.
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Create a ballot
        create_resp = await client.post(
            f"{server_url}/create",
            data={
                "measure": "SSE Test Ballot",
                "options_raw": "Yes, No",
                "duration_mins": "60",
            },
            headers={"HX-Request": "true"},
        )
        assert create_resp.status_code == 204
        ballot_id = create_resp.headers["HX-Redirect"].split("/")[-1]

        # 2. Subscribe to SSE
        sse_url = f"{server_url}/ballots/{ballot_id}/live-results"

        async with client.stream("GET", sse_url) as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]

            async def get_messages():
                current_msg = ""
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        current_msg += line[5:].strip()
                    elif not line and current_msg:
                        yield current_msg
                        current_msg = ""

            messages = get_messages()

            # First event: initial counts
            async for msg in messages:
                assert "Yes" in msg or "No" in msg
                break

            # 3. Cast a vote in a separate task
            async def cast_vote():
                await asyncio.sleep(0.5)
                # Get the ID first
                from bs4 import BeautifulSoup

                vote_page = await client.get(f"{server_url}/vote/{ballot_id}")
                soup = BeautifulSoup(vote_page.text, "html.parser")
                yes_id = None
                for label in soup.find_all("label", class_="radio-label"):
                    if "Yes" in label.get_text():
                        input_el = label.find("input")
                        if input_el:
                            yes_id = input_el["value"]
                        break

                _ = await client.post(
                    f"{server_url}/vote/{ballot_id}", data={"option_id": yes_id}
                )

            vote_task = asyncio.create_task(cast_vote())

            # 4. Wait for the second event
            async for msg in messages:
                if "1" in msg and "Yes" in msg:
                    break
            else:
                pytest.fail("Did not receive SSE update")

            await vote_task
