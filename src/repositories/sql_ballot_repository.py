from typing import override

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..models.ballot_models import Ballot, BallotCreate, Tally
from .ballot_repository import BallotRepository
from .models import BallotTable, OptionTable, VoteTable


class SqlBallotRepository(BallotRepository):
    """
    SQL implementation of the BallotRepository using SQLAlchemy.
    """

    session: AsyncSession

    def __init__(self, session: AsyncSession):
        self.session = session

    @override
    async def list_all(self) -> list[Ballot]:
        stmt = select(BallotTable).options(selectinload(BallotTable.options))
        result = await self.session.execute(stmt)
        ballots = result.scalars().all()
        return [
            Ballot(
                ballot_id=b.id,
                owner_id=b.owner_id,
                measure=b.measure,
                options=[opt.text for opt in b.options],
                allow_write_in=b.allow_write_in,
                start_time=b.start_time,
                end_time=b.end_time,
            )
            for b in ballots
        ]

    @override
    async def get_by_id(self, ballot_id: str) -> Ballot | None:
        stmt = (
            select(BallotTable)
            .where(BallotTable.id == ballot_id)
            .options(selectinload(BallotTable.options))
        )
        result = await self.session.execute(stmt)
        b = result.scalar_one_or_none()
        if not b:
            return None
        return Ballot(
            ballot_id=b.id,
            owner_id=b.owner_id,
            measure=b.measure,
            options=[opt.text for opt in b.options],
            allow_write_in=b.allow_write_in,
            start_time=b.start_time,
            end_time=b.end_time,
        )

    @override
    async def create(
        self, ballot_create: BallotCreate, owner_id: str | None = None
    ) -> Ballot:
        ballot = BallotTable(
            owner_id=owner_id,
            measure=ballot_create.measure,
            allow_write_in=ballot_create.allow_write_in,
            start_time=ballot_create.start_time,
            end_time=ballot_create.end_time,
        )
        self.session.add(ballot)
        await self.session.flush()  # Get ballot.id

        for option_text in ballot_create.options:
            option = OptionTable(ballot_id=ballot.id, text=option_text)
            self.session.add(option)

        await self.session.commit()
        await self.session.refresh(ballot)

        # Re-fetch with options
        res = await self.get_by_id(ballot.id)
        if res is None:
            raise RuntimeError("Failed to re-fetch created ballot")
        return res

    @override
    async def add_vote(self, ballot_id: str, option: str) -> None:
        vote = VoteTable(ballot_id=ballot_id, option_text=option)
        self.session.add(vote)
        await self.session.commit()

    @override
    async def get_tallies(self, ballot_id: str) -> list[Tally]:
        # 1. Get predefined options
        ballot_stmt = (
            select(BallotTable)
            .where(BallotTable.id == ballot_id)
            .options(selectinload(BallotTable.options))
        )
        result = await self.session.execute(ballot_stmt)
        ballot = result.scalar_one_or_none()
        if not ballot:
            return []

        # 2. Get vote counts
        vote_stmt = (
            select(VoteTable.option_text, func.count(VoteTable.id))
            .where(VoteTable.ballot_id == ballot_id)
            .group_by(VoteTable.option_text)
        )
        vote_result = await self.session.execute(vote_stmt)
        vote_counts = {str(text): int(count) for text, count in vote_result.all()}

        # 3. Build tallies
        results_map: dict[str, Tally] = {
            opt.text: Tally(option=opt.text, count=vote_counts.get(opt.text, 0))
            for opt in ballot.options
        }

        # Add write-ins
        if bool(ballot.allow_write_in):
            for option_text, count in vote_counts.items():
                if option_text not in results_map:
                    results_map[option_text] = Tally(option=option_text, count=count)

        return list(results_map.values())
