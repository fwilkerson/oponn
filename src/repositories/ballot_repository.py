import threading
from abc import ABC, abstractmethod
from typing import override
from ..models.ballot_models import Ballot, BallotCreate, Tally


class BallotRepository(ABC):
    @abstractmethod
    def list_all(self) -> list[Ballot]:
        pass

    @abstractmethod
    def get_by_id(self, ballot_id: int) -> Ballot | None:
        pass

    @abstractmethod
    def create(self, ballot_create: BallotCreate) -> Ballot:
        pass

    @abstractmethod
    def add_vote(self, ballot_id: int, option: str) -> None:
        pass

    @abstractmethod
    def get_tallies(self, ballot_id: int) -> list[Tally]:
        pass


class InMemoryBallotRepository(BallotRepository):
    def __init__(self):
        self.ballots_db: dict[int, Ballot] = {}
        self.ballot_id_counter: int = 0
        self.votes_db: dict[int, dict[str, int]] = {}
        self._lock: threading.Lock = threading.Lock()

    @override
    def list_all(self) -> list[Ballot]:
        with self._lock:
            return list(self.ballots_db.values())

    @override
    def get_by_id(self, ballot_id: int) -> Ballot | None:
        with self._lock:
            return self.ballots_db.get(ballot_id)

    @override
    def create(self, ballot_create: BallotCreate) -> Ballot:
        with self._lock:
            self.ballot_id_counter += 1
            ballot = Ballot(
                ballot_id=self.ballot_id_counter,
                measure=ballot_create.measure,
                options=ballot_create.options,
                allow_write_in=ballot_create.allow_write_in,
                start_time=ballot_create.start_time,
                end_time=ballot_create.end_time,
            )
            self.ballots_db[self.ballot_id_counter] = ballot
            self.votes_db[self.ballot_id_counter] = {
                option: 0 for option in ballot.options
            }
            return ballot

    @override
    def add_vote(self, ballot_id: int, option: str) -> None:
        with self._lock:
            if ballot_id not in self.votes_db:
                self.votes_db[ballot_id] = {}

            self.votes_db[ballot_id][option] = (
                self.votes_db[ballot_id].get(option, 0) + 1
            )

    @override
    def get_tallies(self, ballot_id: int) -> list[Tally]:
        with self._lock:
            ballot = self.ballots_db.get(ballot_id)
            if not ballot:
                return []

            current_counts = self.votes_db.get(ballot_id, {})
            results: list[Tally] = []

            # Ensure all predefined options are included
            for option in ballot.options:
                results.append(
                    Tally(option=option, count=current_counts.get(option, 0))
                )

            # Include write-ins if allowed
            if ballot.allow_write_in:
                predefined_set = set(ballot.options)
                for option, count in current_counts.items():
                    if option not in predefined_set:
                        results.append(Tally(option=option, count=count))

            return results
