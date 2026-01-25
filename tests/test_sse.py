import pytest
import asyncio
import threading
import uvicorn
import time
from httpx import AsyncClient
from src.main import app
from src.dependencies import validate_csrf


def run_server():
    uvicorn.run(app, host="127.0.0.1", port=8002, log_level="error")


@pytest.fixture(scope="module")
def server():
    # Override CSRF for all tests in this module
    app.dependency_overrides[validate_csrf] = lambda: None

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    # Wait for server to start
    time.sleep(1)
    yield "http://127.0.0.1:8002"
    # Overrides are cleared after the module
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_sse_updates_robust(server):
    base_url = server
    async with AsyncClient(base_url=base_url, timeout=10.0) as ac:
        # 1. Create a ballot
        response = await ac.post(
            "/create",
            data={"measure": "Robust SSE Test", "options_raw": "Yes, No"},
            headers={"HX-Request": "true"},
        )
        assert response.status_code == 204
        ballot_id_str = response.headers.get("HX-Redirect", "").split("/")[-1]
        ballot_id = int(ballot_id_str)

        # 2. Connect to SSE
        sse_received = []

        async def read_sse():
            try:
                async with ac.stream(
                    "GET", f"/ballots/{ballot_id}/live-results"
                ) as sse_response:
                    assert sse_response.status_code == 200
                    current_event = []
                    async for line in sse_response.aiter_lines():
                        if line.startswith("data:"):
                            current_event.append(line)
                        elif not line and current_event:
                            sse_received.append("\n".join(current_event))
                            current_event = []
                            if len(sse_received) >= 2:  # Initial + 1 update
                                break
            except Exception as e:
                print(f"DEBUG SSE Reader Error: {e}")

        sse_task = asyncio.create_task(read_sse())
        await asyncio.sleep(1)  # Ensure connection is established

        # 3. Cast a vote
        vote_response = await ac.post(
            f"/vote/{ballot_id}", data={"option": "Yes"}, headers={"HX-Request": "true"}
        )
        assert vote_response.status_code == 204

        # Wait for SSE task
        try:
            await asyncio.wait_for(sse_task, timeout=5.0)
        except asyncio.TimeoutError:
            pytest.fail(f"SSE update timed out. Received {len(sse_received)} events.")
        finally:
            if not sse_task.done():
                sse_task.cancel()

        assert len(sse_received) >= 2
        assert "Yes" in sse_received[0]
        assert "Yes" in sse_received[1]
        # Check that the second event has 1 vote for Yes
        assert ">1</span>" in sse_received[1]
