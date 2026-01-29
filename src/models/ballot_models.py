from datetime import datetime, timedelta, timezone
from typing import cast

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field, ValidationError, ValidationInfo, field_validator


def sanitize_html(text: str) -> str:
    """Removes HTML tags from the given text."""
    return BeautifulSoup(text, "html.parser").get_text()


def format_pydantic_errors(
    e: ValidationError, field_mapping: dict[str, str] | None = None
) -> tuple[str | None, dict[str, str]]:
    """
    Centralized helper to clean Pydantic prefixes and map internal
    model fields to form field names.
    Returns (global_error_msg, field_errors_dict)
    """

    field_errors: dict[str, str] = {}
    global_errors: list[str] = []

    for err in e.errors():
        loc = err["loc"]
        msg = err["msg"]

        # Clean up Pydantic prefixes
        msg = msg.replace("Value error, ", "")
        msg = msg.replace("String should have ", "")
        msg = msg.replace("List should have ", "")

        if loc:
            field_name = str(loc[0])
            # Apply mapping if provided (e.g., 'options' -> 'options_raw')
            if field_mapping and field_name in field_mapping:
                field_name = field_mapping[field_name]

            # Prevent overwriting if multiple validators fail for the same field
            if field_name not in field_errors:
                field_errors[field_name] = msg
        else:
            global_errors.append(msg)

    error_msg = "; ".join(global_errors) if global_errors else None
    return error_msg, field_errors


class BallotBase(BaseModel):
    measure: str = Field(
        ...,
        min_length=3,
        max_length=255,
        description="The name or topic of the ballot",
    )
    allow_write_in: bool
    options: list[str] = Field(..., min_length=1)
    start_time: datetime | None = None
    end_time: datetime | None = None


class BallotCreate(BallotBase):
    @field_validator("options")
    @classmethod
    def validate_options_data(cls, v: list[str], info: ValidationInfo) -> list[str]:
        # If write-ins aren't allowed, we need at least 2 predefined options for a valid vote.
        # If they are allowed, 1 predefined option + write-in possibility is acceptable.
        allow_write_in = info.data.get("allow_write_in")
        if allow_write_in is None:
            return v

        min_options = 1 if allow_write_in else 2
        if len(v) < min_options:
            raise ValueError(
                f"at least {min_options} options when "
                + f"{'write-ins are enabled' if allow_write_in else 'write-ins are disabled'}"
            )

        # Also ensure options themselves aren't too long
        for opt in v:
            if not (1 <= len(opt) <= 64):
                raise ValueError("between 1 and 64 characters")

        return v


class BallotCreateForm(BaseModel):
    """
    Model representing the raw data received from the 'Create Ballot' web form.
    This model handles the conversion of raw strings into clean types.
    """

    measure: str = Field(..., min_length=3, max_length=255)
    allow_write_in: bool = False
    options_raw: str = Field(..., min_length=1)
    start_time_type: str = "now"  # "now" or "scheduled"
    scheduled_start_time: str | None = None
    duration_mins: int = Field(default=0, ge=0)

    @field_validator("measure")
    @classmethod
    def validate_measure_text(cls, v: str) -> str:
        if len(v) < 3:
            raise ValueError("at least 3 characters")
        if len(v) > 255:
            raise ValueError("at most 255 characters")
        return v

    @field_validator("options_raw")
    @classmethod
    def split_options(cls, v: str, info: ValidationInfo) -> str:
        """Ensure there's at least one non-empty option after splitting."""
        opts = [o.strip() for o in v.split(",") if o.strip()]
        if not opts:
            raise ValueError("at least 1 item after validation")

        # Also check count here to attribute to options_raw early
        allow_write_in = info.data.get("allow_write_in")
        if allow_write_in is not None:
            min_options = 1 if allow_write_in else 2
            if len(opts) < min_options:
                raise ValueError(
                    f"at least {min_options} options when "
                    + f"{'write-ins are enabled' if allow_write_in else 'write-ins are disabled'}"
                )
        return v

    @field_validator("scheduled_start_time")
    @classmethod
    def validate_timing(cls, v: str | None, info: ValidationInfo) -> str | None:
        """Validates the relationship between start_time_type and scheduled_start_time."""
        start_time_type = info.data.get("start_time_type")
        if start_time_type == "scheduled":
            if not v:
                raise ValueError(
                    "Scheduled start time is required when 'scheduled' is selected"
                )

            try:
                # Pydantic's datetime type could handle this, but since we receive a string
                # that might need 'Z' normalization, we do it here.
                st = datetime.fromisoformat(v.replace("Z", "+00:00"))
                if st < datetime.now(timezone.utc):
                    raise ValueError("Scheduled start time must be in the future")
            except ValueError as e:
                if "future" in str(e):
                    raise e
                raise ValueError("Invalid scheduled start time format")

        return v

    def to_ballot_create(self) -> BallotCreate:
        """Converts the form data into the core BallotCreate domain model."""
        options = [o.strip() for o in self.options_raw.split(",") if o.strip()]

        if self.start_time_type == "scheduled" and self.scheduled_start_time:
            st = datetime.fromisoformat(
                self.scheduled_start_time.replace("Z", "+00:00")
            )
        else:
            st = datetime.now(timezone.utc)

        et = (
            st + timedelta(minutes=self.duration_mins)
            if self.duration_mins > 0
            else None
        )

        return BallotCreate(
            measure=self.measure,
            options=options,
            allow_write_in=self.allow_write_in,
            start_time=st,
            end_time=et,
        )


class Ballot(BallotBase):
    ballot_id: str
    owner_id: str | None = None


class Vote(BaseModel):
    option: str = Field(..., min_length=1, max_length=64)
    is_write_in: bool = False

    @field_validator("option")
    @classmethod
    def validate_option_text(cls, v: str) -> str:
        if len(v) < 1:
            raise ValueError("at least 1 character")
        if len(v) > 64:
            raise ValueError("at most 64 characters")
        return v


class VoteForm(BaseModel):
    """
    Model representing the raw data received from the 'Cast Vote' web form.
    Handles BeautifulSoup sanitization and conditional write-in validation.
    """

    option: str
    write_in_value: str | None = None

    def to_vote(self) -> Vote:
        """Converts the form data into the core Vote domain model."""
        is_write_in = self.option == "__write_in__"
        vote_option = self.write_in_value if is_write_in else self.option

        if is_write_in:
            if not vote_option:
                raise ValueError("Write-in value required")

            # Basic sanitization
            vote_option = sanitize_html(vote_option)

        return Vote(option=cast(str, vote_option), is_write_in=is_write_in)


class Tally(BaseModel):
    option: str
    count: int
