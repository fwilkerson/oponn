import httpx
import pytest
from bs4 import BeautifulSoup

# This test suite provides high confidence by simulating HTMX and SSE behavior
# without requiring a full browser environment, making it environment-agnostic.


@pytest.mark.asyncio
async def test_create_ballot_and_vote_functional(server_url: str):
    """Verifies the full lifecycle of a ballot using functional simulation."""
    async with httpx.AsyncClient() as client:
        # 1. Create a ballot (simulate HTMX request)
        response = await client.post(
            f"{server_url}/create",
            data={
                "measure": "Functional Test Ballot",
                "options_raw": "Option X, Option Y",
                "duration_mins": "30",
            },
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 204
        assert "HX-Redirect" in response.headers
        vote_url = response.headers["HX-Redirect"]
        ballot_id = vote_url.split("/")[-1]

        # 2. Get vote page
        response = await client.get(f"{server_url}{vote_url}")
        assert response.status_code == 200
        soup = BeautifulSoup(response.text, "html.parser")
        assert "Functional Test Ballot" in soup.get_text()

        # Verify options are present and get an ID
        option_labels = soup.find_all("label", class_="radio-label")
        option_x_id = None
        for label in option_labels:
            if "Option X" in label.get_text():
                input_el = label.find("input")
                if input_el:
                    option_x_id = input_el["value"]
                break

        assert option_x_id is not None

        # 3. Cast a vote
        response = await client.post(
            f"{server_url}/vote/{ballot_id}",
            data={"option_id": option_x_id},
            follow_redirects=False,
        )
        assert response.status_code == 303  # Redirect to results
        results_url = response.headers["location"]

        # 4. Check results
        response = await client.get(f"{server_url}{results_url}")
        assert response.status_code == 200
        assert "Option X" in response.text
        assert "1" in response.text


@pytest.mark.asyncio
async def test_htmx_validation_errors_functional(server_url: str):
    """Verifies that validation errors return HTMX partials as expected."""
    async with httpx.AsyncClient() as client:
        # 1. Submit too short measure
        response = await client.post(
            f"{server_url}/create",
            data={"measure": "ab", "options_raw": "A, B"},
            headers={"HX-Request": "true"},
        )

        # Should return 200 (re-render form) not 204 (success)
        assert response.status_code == 200

        # Verify it's a partial, not a full page (no <html> tag)
        assert "<html" not in response.text.lower()

        soup = BeautifulSoup(response.text, "html.parser")
        error_msg = soup.find(class_="field-error-msg")
        assert error_msg is not None
        assert "at least 3 characters" in error_msg.get_text()

        # Verify form values are preserved
        measure_input = soup.find("input", {"name": "measure"})
        assert measure_input is not None
        assert measure_input["value"] == "ab"


@pytest.mark.asyncio
async def test_sse_live_updates_functional(server_url: str):
    """Verifies SSE updates by monitoring the stream while casting a vote."""
    async with httpx.AsyncClient(timeout=10.0) as client:
        # 1. Create ballot
        resp = await client.post(
            f"{server_url}/create",
            data={"measure": "SSE Functional", "options_raw": "Yes, No"},
            headers={"HX-Request": "true"},
        )
        ballot_id = resp.headers["HX-Redirect"].split("/")[-1]

        # 2. Start SSE stream
        sse_url = f"{server_url}/ballots/{ballot_id}/live-results"
        async with client.stream("GET", sse_url) as stream:

            async def get_messages():
                current_msg = ""
                async for line in stream.aiter_lines():
                    if line.startswith("data:"):
                        current_msg += line[5:].strip()
                    elif not line and current_msg:
                        yield current_msg
                        current_msg = ""

            messages = get_messages()

            # Initial event
            async for msg in messages:
                assert "Yes" in msg or "No" in msg
                break

            # 3. Vote in background
            # First get the ID
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

            # 4. Check for update event
            async for msg in messages:
                if "1" in msg and "Yes" in msg:
                    break
            else:
                pytest.fail("Did not receive SSE update after vote")
