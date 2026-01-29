import secrets
from sqlalchemy import String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship, Mapped, mapped_column
from datetime import datetime
from typing import final


def generate_id() -> str:
    """Generates a random URL-safe string (approx 21 chars)."""
    return secrets.token_urlsafe(16)


class Base(DeclarativeBase):
    pass


@final
class UserTable(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=generate_id)
    email: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    # provider: "google" or "apple"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    # The ID returned by the provider (e.g. Google's distinct user ID)
    provider_id: Mapped[str] = mapped_column(String(255), index=True, nullable=False)

    ballots: Mapped[list["BallotTable"]] = relationship(
        "BallotTable", back_populates="owner", cascade="all, delete-orphan"
    )


@final
class BallotTable(Base):
    __tablename__ = "ballots"

    id: Mapped[str] = mapped_column(String(24), primary_key=True, default=generate_id)

    owner_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner: Mapped["UserTable | None"] = relationship(
        "UserTable", back_populates="ballots"
    )

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
    ballot_id: Mapped[str] = mapped_column(ForeignKey("ballots.id"), nullable=False)
    text: Mapped[str] = mapped_column(String(64), nullable=False)

    ballot: Mapped["BallotTable"] = relationship(
        "BallotTable", back_populates="options"
    )


@final
class VoteTable(Base):
    __tablename__ = "votes"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ballot_id: Mapped[str] = mapped_column(ForeignKey("ballots.id"), nullable=False)
    option_text: Mapped[str] = mapped_column(String(64), nullable=False)

    ballot: Mapped["BallotTable"] = relationship("BallotTable", back_populates="votes")
