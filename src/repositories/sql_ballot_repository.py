from datetime import datetime
from typing import override

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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
    async def list_all(self) -> list[BallotTable]:
        stmt = select(BallotTable).options(selectinload(BallotTable.options))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    @override
    async def get_by_id(self, ballot_id: str) -> BallotTable | None:
        stmt = (
            select(BallotTable)
            .where(BallotTable.id == ballot_id)
            .options(selectinload(BallotTable.options))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    @override
    async def create_ballot_record(
        self,
        ballot_id: str,
        encrypted_measure: str,
        encrypted_dek: str,
        options: list[str],  # These are already encrypted
        allow_write_in: bool,
        start_time: datetime | None,
        end_time: datetime | None,
        owner_id: str | None = None,
        kms_key_id: str = "default",
    ) -> BallotTable:
        ballot = BallotTable(
            id=ballot_id,
            owner_id=owner_id,
            encrypted_measure=encrypted_measure,
            encrypted_dek=encrypted_dek,
            kms_key_id=kms_key_id,
            allow_write_in=allow_write_in,
            start_time=start_time,
            end_time=end_time,
        )
        self.session.add(ballot)
        await self.session.flush()

        for enc_opt in options:
            option = OptionTable(ballot_id=ballot.id, encrypted_text=enc_opt)
            self.session.add(option)

        await self.session.commit()
        await self.session.refresh(ballot)

        # Fetch with options loaded
        res = await self.get_by_id(ballot.id)
        if not res:
            raise RuntimeError("Failed to re-fetch created ballot")
        return res

    @override
    async def add_vote(self, ballot_id: str, option_id: int) -> None:
        vote = VoteTable(ballot_id=ballot_id, option_id=option_id)
        self.session.add(vote)
        await self.session.commit()

    @override
    async def add_write_in_option(self, ballot_id: str, encrypted_text: str) -> int:
        """Adds a new write-in option and returns its ID."""
        option = OptionTable(
            ballot_id=ballot_id, encrypted_text=encrypted_text, is_write_in=True
        )
        self.session.add(option)
        await self.session.flush()
        return option.id

    @override
    async def get_tallies(self, ballot_id: str) -> list[tuple[int, int]]:
        """Returns a list of (option_id, count)."""
        stmt = (
            select(VoteTable.option_id, func.count(VoteTable.id))
            .where(VoteTable.ballot_id == ballot_id)
            .group_by(VoteTable.option_id)
        )
        result = await self.session.execute(stmt)
        return [(int(row[0]), int(row[1])) for row in result.all()]
