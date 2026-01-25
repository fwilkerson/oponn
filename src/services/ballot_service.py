from datetime import datetime, timezone, timedelta
import asyncio

from ..models.ballot_models import (
    Ballot,
    BallotCreate,
    Vote,
    Tally,
)
from ..models.exceptions import (
    BallotNotFoundError,
    VotingNotOpenError,
    InvalidOptionError,
)
from ..repositories.ballot_repository import BallotRepository


class BallotService:
    repository: BallotRepository

    def __init__(self, repository: BallotRepository):
        self.repository = repository
        self.sse_queues: dict[int, list[asyncio.Queue[list[Tally]]]] = {}

    def list_ballots(self) -> list[Ballot]:
        return self.repository.list_all()

    def create_ballot(self, ballot_create: BallotCreate) -> Ballot:
        ballot = self.repository.create(ballot_create)
        self.sse_queues[ballot.ballot_id] = []
        return ballot

    def get_ballot(self, ballot_id: int) -> Ballot:
        ballot = self.repository.get_by_id(ballot_id)
        if not ballot:
            raise BallotNotFoundError(f"Ballot {ballot_id} not found")
        return ballot

    async def record_vote(self, ballot_id: int, vote: Vote) -> None:
        ballot = self.get_ballot(ballot_id)
        now = datetime.now(timezone.utc)

        if ballot.start_time and now < ballot.start_time:
            raise VotingNotOpenError("Voting has not started for this ballot")
        if ballot.end_time and now > ballot.end_time:
            raise VotingNotOpenError("Voting has ended for this ballot")

        if vote.is_write_in:
            if not ballot.allow_write_in:
                raise InvalidOptionError(
                    "Write-in votes are not allowed for this ballot"
                )
        else:
            if vote.option not in ballot.options:
                raise InvalidOptionError("Invalid option for this ballot")

        self.repository.add_vote(ballot_id, vote.option)

        # Notify SSE clients
        updated_counts = self.get_vote_counts(ballot_id)
        for queue in self.sse_queues.get(ballot_id, []):
            await queue.put(updated_counts)

    def get_vote_counts(self, ballot_id: int) -> list[Tally]:
        # We check if ballot exists first
        _ = self.get_ballot(ballot_id)
        return self.repository.get_tallies(ballot_id)

    async def register_sse_client(self, ballot_id: int) -> asyncio.Queue[list[Tally]]:
        _ = self.get_ballot(ballot_id)
        queue: asyncio.Queue[list[Tally]] = asyncio.Queue()
        if ballot_id not in self.sse_queues:
            self.sse_queues[ballot_id] = []
        self.sse_queues[ballot_id].append(queue)
        return queue

    async def unregister_sse_client(
        self, ballot_id: int, queue: asyncio.Queue[list[Tally]]
    ):
        if ballot_id in self.sse_queues:
            try:
                self.sse_queues[ballot_id].remove(queue)
            except ValueError:
                pass

    @staticmethod
    def format_time_delta(diff: timedelta) -> str:
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds} seconds"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minutes"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hours"
        days = hours // 24
        return f"{days} days"

    def get_status(self, ballot: Ballot) -> tuple[str, str]:
        now = datetime.now(timezone.utc)

        st = ballot.start_time
        if st and st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)

        et = ballot.end_time
        if et and et.tzinfo is None:
            et = et.replace(tzinfo=timezone.utc)

        if st and now < st:
            return "pending", f"starts in {self.format_time_delta(st - now)}"

        if et and now > et:
            return "ended", "voting closed"

        if et:
            return "active", f"ends in {self.format_time_delta(et - now)}"

        return "active", "voting open"
