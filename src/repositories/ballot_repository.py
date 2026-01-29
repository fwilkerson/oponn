import asyncio
import secrets
from abc import ABC, abstractmethod
from typing import override
from ..models.ballot_models import Ballot, BallotCreate, Tally


class BallotRepository(ABC):
    """
    Abstract base class for ballot data persistence.
    """

    @abstractmethod
    async def list_all(self) -> list[Ballot]:
        """Retrieve all ballots from storage."""
        pass

    @abstractmethod
    async def get_by_id(self, ballot_id: str) -> Ballot | None:
        """Retrieve a specific ballot by its unique ID."""
        pass

    @abstractmethod
    async def create(
        self, ballot_create: BallotCreate, owner_id: str | None = None
    ) -> Ballot:
        """Create and persist a new ballot."""
        pass

    @abstractmethod
    async def add_vote(self, ballot_id: str, option: str) -> None:
        """Increment the vote count for a specific option on a ballot."""
        pass

    @abstractmethod
    async def get_tallies(self, ballot_id: str) -> list[Tally]:
        """Retrieve the current vote counts for all options on a ballot."""
        pass


class InMemoryBallotRepository(BallotRepository):
    """
    Thread-safe in-memory implementation of the BallotRepository.
    """

    def __init__(self):
        self.ballots_db: dict[str, Ballot] = {}
        self.votes_db: dict[str, dict[str, int]] = {}
        self._lock: asyncio.Lock = asyncio.Lock()

    @override
    async def list_all(self) -> list[Ballot]:
        async with self._lock:
            return list(self.ballots_db.values())

    @override
    async def get_by_id(self, ballot_id: str) -> Ballot | None:
        async with self._lock:
            return self.ballots_db.get(ballot_id)

    @override
    async def create(
        self, ballot_create: BallotCreate, owner_id: str | None = None
    ) -> Ballot:
        async with self._lock:
            ballot_id = secrets.token_urlsafe(16)
            ballot = Ballot(
                ballot_id=ballot_id,
                owner_id=owner_id,
                measure=ballot_create.measure,
                options=ballot_create.options,
                allow_write_in=ballot_create.allow_write_in,
                start_time=ballot_create.start_time,
                end_time=ballot_create.end_time,
            )
            self.ballots_db[ballot_id] = ballot
            self.votes_db[ballot_id] = {option: 0 for option in ballot.options}
            return ballot

    @override
    async def add_vote(self, ballot_id: str, option: str) -> None:
        async with self._lock:
            if ballot_id not in self.votes_db:
                self.votes_db[ballot_id] = {}

            counts = self.votes_db[ballot_id]
            counts[option] = counts.get(option, 0) + 1

    @override
    async def get_tallies(self, ballot_id: str) -> list[Tally]:
        async with self._lock:
            ballot = self.ballots_db.get(ballot_id)
            if not ballot:
                return []

            current_counts = self.votes_db.get(ballot_id, {})

            # Map for quick lookup of existing tallies
            results_map: dict[str, Tally] = {
                option: Tally(option=option, count=current_counts.get(option, 0))
                for option in ballot.options
            }

            # Add write-ins if they aren't in the predefined options
            if ballot.allow_write_in:
                for option, count in current_counts.items():
                    if option not in results_map:
                        results_map[option] = Tally(option=option, count=count)

            return list(results_map.values())
