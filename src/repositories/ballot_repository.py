import asyncio
from abc import ABC, abstractmethod
from typing import override


from datetime import datetime
from .models import BallotTable, OptionTable


class BallotRepository(ABC):
    """
    Abstract base class for ballot data persistence.
    """

    @abstractmethod
    async def list_all(self) -> list[BallotTable]:
        """Retrieve all ballots from storage."""
        pass

    @abstractmethod
    async def get_by_id(self, ballot_id: str) -> BallotTable | None:
        """Retrieve a specific ballot by its unique ID."""
        pass

    @abstractmethod
    async def create_ballot_record(
        self,
        ballot_id: str,
        encrypted_measure: str,
        encrypted_dek: str,
        options: list[str],
        allow_write_in: bool,
        start_time: datetime | None,
        end_time: datetime | None,
        owner_id: str | None = None,
    ) -> BallotTable:
        """Create and persist a new ballot."""
        pass

    @abstractmethod
    async def add_vote(self, ballot_id: str, option_id: int) -> None:
        """Increment the vote count for a specific option on a ballot."""
        pass

    @abstractmethod
    async def add_write_in_option(self, ballot_id: str, encrypted_text: str) -> int:
        """Adds a new write-in option and returns its ID."""
        pass

    @abstractmethod
    async def get_tallies(self, ballot_id: str) -> list[tuple[int, int]]:
        """Retrieve the current vote counts for all options on a ballot."""
        pass


class InMemoryBallotRepository(BallotRepository):
    """
    Thread-safe in-memory implementation of the BallotRepository.
    """

    ballots_db: dict[str, BallotTable]
    votes_db: dict[str, dict[int, int]]
    options_db: dict[str, list[dict[str, object]]]
    _lock: asyncio.Lock
    _opt_id_counter: int

    def __init__(self):
        self.ballots_db: dict[str, BallotTable] = {}
        self.votes_db: dict[str, dict[int, int]] = {}
        self.options_db: dict[str, list[dict[str, object]]] = {}  # ballot_id -> list of options
        self._lock: asyncio.Lock = asyncio.Lock()
        self._opt_id_counter: int = 1

    @override
    async def list_all(self) -> list[BallotTable]:
        async with self._lock:
            return list(self.ballots_db.values())

    @override
    async def get_by_id(self, ballot_id: str) -> BallotTable | None:
        async with self._lock:
            return self.ballots_db.get(ballot_id)

    @override
    async def create_ballot_record(
        self,
        ballot_id: str,
        encrypted_measure: str,
        encrypted_dek: str,
        options: list[str],
        allow_write_in: bool,
        start_time: datetime | None,
        end_time: datetime | None,
        owner_id: str | None = None,
    ) -> BallotTable:
        async with self._lock:
            # Use provided ballot_id instead of generating one

            # This is a bit of a hack since BallotTable is a SQLAlchemy model,
            # but for in-memory we just want the structure.
            ballot = BallotTable(
                id=ballot_id,
                owner_id=owner_id,
                encrypted_measure=encrypted_measure,
                encrypted_dek=encrypted_dek,
                allow_write_in=allow_write_in,
                start_time=start_time,
                end_time=end_time,
            )

            self.ballots_db[ballot_id] = ballot

            ballot.options = []
            for opt_text in options:
                opt_id = self._opt_id_counter
                self._opt_id_counter += 1
                option = OptionTable(
                    id=opt_id,
                    ballot_id=ballot_id,
                    encrypted_text=opt_text,
                    is_write_in=False,
                )
                ballot.options.append(option)

            self.votes_db[ballot_id] = {}
            return ballot

    @override
    async def add_vote(self, ballot_id: str, option_id: int) -> None:
        async with self._lock:
            if ballot_id not in self.votes_db:
                self.votes_db[ballot_id] = {}

            self.votes_db[ballot_id][option_id] = (
                self.votes_db[ballot_id].get(option_id, 0) + 1
            )

    @override
    async def add_write_in_option(self, ballot_id: str, encrypted_text: str) -> int:
        async with self._lock:
            opt_id = self._opt_id_counter
            self._opt_id_counter += 1

            option = OptionTable(
                id=opt_id,
                ballot_id=ballot_id,
                encrypted_text=encrypted_text,
                is_write_in=True,
            )

            if ballot_id in self.ballots_db:
                self.ballots_db[ballot_id].options.append(option)

            return opt_id

    @override
    async def get_tallies(self, ballot_id: str) -> list[tuple[int, int]]:
        async with self._lock:
            counts = self.votes_db.get(ballot_id, {})
            return list(counts.items())
