import asyncio

from src.models.ballot_models import BallotCreate, Vote
from src.repositories.ballot_repository import InMemoryBallotRepository
from src.services.ballot_service import BallotService, BallotStateManager
from src.services.crypto_service import CryptoService


async def test_concurrent_voting_consistency():
    """
    Simulates many concurrent users voting on the same ballot
    to ensure the Lock implementation prevents data loss.
    """
    from tests.conftest import TEST_KEYSET

    repo = InMemoryBallotRepository()
    crypto = CryptoService(master_keyset_json=TEST_KEYSET)
    state = BallotStateManager()
    service = BallotService(repo, crypto=crypto, state_manager=state)

    # Create a ballot
    bc = BallotCreate(
        measure="Concurrent Test", options=["Option A", "Option B"], allow_write_in=True
    )
    ballot = await service.create_ballot(bc)
    option_a_id = [oid for oid, txt in ballot.option_map.items() if txt == "Option A"][
        0
    ]

    num_users = 50
    votes_per_user = 20
    total_expected_votes = num_users * votes_per_user

    async def user_task():
        for _ in range(votes_per_user):
            # Mix of predefined and write-in votes
            vote = Vote(option_id=option_a_id, is_write_in=False)
            await service.record_vote(ballot.ballot_id, vote)

            # Brief yield to encourage context switching
            await asyncio.sleep(0)

    # Launch all users concurrently
    tasks = [asyncio.create_task(user_task()) for _ in range(num_users)]
    await asyncio.gather(*tasks)

    # Verify results
    tallies = await service.get_vote_counts(ballot.ballot_id)
    option_a_tally = next(t for t in tallies if t.option == "Option A")

    assert option_a_tally.count == total_expected_votes
    print(f"Concurrency test passed: {option_a_tally.count} votes recorded correctly.")


async def test_high_concurrency_mixed_options():
    from tests.conftest import TEST_KEYSET

    repo = InMemoryBallotRepository()
    crypto = CryptoService(master_keyset_json=TEST_KEYSET)
    state = BallotStateManager()
    service = BallotService(repo, crypto=crypto, state_manager=state)

    bc = BallotCreate(
        measure="Mixed Concurrent", options=["A", "B"], allow_write_in=True
    )
    ballot = await service.create_ballot(bc)
    option_a_id = [oid for oid, txt in ballot.option_map.items() if txt == "A"][0]
    option_b_id = [oid for oid, txt in ballot.option_map.items() if txt == "B"][0]

    num_tasks = 100

    async def vote_a():
        await service.record_vote(ballot.ballot_id, Vote(option_id=option_a_id))

    async def vote_b():
        await service.record_vote(ballot.ballot_id, Vote(option_id=option_b_id))

    async def vote_write_in(i):
        await service.record_vote(
            ballot.ballot_id, Vote(write_in_value=f"WriteIn_{i}", is_write_in=True)
        )

    tasks = []
    for i in range(num_tasks):
        if i % 3 == 0:
            tasks.append(vote_a())
        elif i % 3 == 1:
            tasks.append(vote_b())
        else:
            tasks.append(vote_write_in(i))

    await asyncio.gather(*tasks)

    tallies = await service.get_vote_counts(ballot.ballot_id)
    total_votes = sum(t.count for t in tallies)
    assert total_votes == num_tasks
