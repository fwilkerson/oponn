from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from datetime import datetime
from typing import final


class Base(DeclarativeBase):
    pass


@final
class BallotTable(Base):
    __tablename__ = "ballots"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    measure: Mapped[str] = mapped_column(String(255), nullable=False)
    allow_write_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    start_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    end_time: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    options: Mapped[list["OptionTable"]] = relationship(
        "OptionTable", back_populates="ballot", cascade="all, delete-orphan"
    )
    votes: Mapped[list["VoteTable"]] = relationship(
        "VoteTable", back_populates="ballot", cascade="all, delete-orphan"
    )


@final
class OptionTable(Base):
    __tablename__ = "options"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ballot_id: Mapped[int] = mapped_column(ForeignKey("ballots.id"), nullable=False)
    text: Mapped[str] = mapped_column(String(64), nullable=False)

    ballot: Mapped["BallotTable"] = relationship(
        "BallotTable", back_populates="options"
    )


@final
class VoteTable(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ballot_id: Mapped[int] = mapped_column(ForeignKey("ballots.id"), nullable=False)
    option_text: Mapped[str] = mapped_column(String(64), nullable=False)

    ballot: Mapped["BallotTable"] = relationship("BallotTable", back_populates="votes")
