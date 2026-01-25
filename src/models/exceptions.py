class OponnError(Exception):
    """Base class for domain-specific errors."""

    pass


class BallotNotFoundError(OponnError):
    """Raised when a ballot cannot be found."""

    pass


class VotingNotOpenError(OponnError):
    """Raised when voting is attempted on a ballot that is pending or ended."""

    pass


class InvalidOptionError(OponnError):
    """Raised when a vote is cast for an invalid or disallowed option."""

    pass
