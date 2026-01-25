from pydantic import BaseModel, Field, model_validator
from datetime import datetime
from typing import Self


class BallotBase(BaseModel):
    measure: str = Field(..., min_length=3, max_length=255)
    options: list[str] = Field(..., min_length=1)
    allow_write_in: bool
    start_time: datetime | None = None
    end_time: datetime | None = None


class BallotCreate(BallotBase):
    @model_validator(mode="after")
    def validate_options_count(self) -> Self:
        # If write-ins aren't allowed, we need at least 2 predefined options for a valid vote.
        # If they are allowed, 1 predefined option + write-in possibility is acceptable.
        min_options = 1 if self.allow_write_in else 2
        if len(self.options) < min_options:
            raise ValueError(
                f"Ballot must have at least {min_options} options when "
                + f"{'write-ins are enabled' if self.allow_write_in else 'write-ins are disabled'}."
            )

        # Also ensure options themselves aren't too long
        for opt in self.options:
            if not (1 <= len(opt) <= 64):
                raise ValueError(f"Option '{opt}' must be between 1 and 64 characters.")

        return self


class Ballot(BallotBase):
    ballot_id: int


class Vote(BaseModel):
    option: str = Field(..., min_length=1, max_length=64)
    is_write_in: bool = False


class Tally(BaseModel):
    option: str
    count: int
