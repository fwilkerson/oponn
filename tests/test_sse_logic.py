import asyncio
import json
import pytest
from src.dependencies import (
    get_redis_client,
    get_ballot_state_manager,
    get_crypto_service,
    get_in_memory_ballot_repo,
)
from src.services.ballot_service import BallotService, Tally


@pytest.mark.asyncio
async def test_ballot_service_redis_listener_logic():
    """
    Unit test for the logic that bridges Redis Pub/Sub to local SSE queues.
    This specifically verifies the fix for JSON serialization/deserialization.
    """
    redis = await get_redis_client()
    if not redis:
        pytest.skip("Redis not available")

    state = await get_ballot_state_manager()
    crypto = await get_crypto_service()
    repo = await get_in_memory_ballot_repo()
    service = BallotService(repo, crypto, state, redis)

    ballot_id = "test_logic_id"
    queue = asyncio.Queue()

    # Manually start the listener in the background
    listener_task = asyncio.create_task(service.listen_for_updates(ballot_id, queue))

    try:
        # Give it a moment to subscribe
        await asyncio.sleep(0.2)

        # Simulate a vote broadcast from another worker
        test_data = [Tally(option="Yes", count=10).model_dump()]
        await redis.publish(f"ballot:{ballot_id}:updates", json.dumps(test_data))

        # Check if the queue received the parsed Tally objects
        try:
            received_tallies = await asyncio.wait_for(queue.get(), timeout=2.0)
            assert len(received_tallies) == 1
            assert received_tallies[0].option == "Yes"
            assert received_tallies[0].count == 10
        except asyncio.TimeoutError:
            pytest.fail(
                "BallotService listener did not receive or process Redis message"
            )

    finally:
        listener_task.cancel()
