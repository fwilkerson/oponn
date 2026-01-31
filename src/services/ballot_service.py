import asyncio
import json
from datetime import datetime, timedelta, timezone

import redis.asyncio as redis
import structlog

from ..models.ballot_models import Ballot, BallotCreate, Tally, Vote
from ..models.exceptions import (
    BallotNotFoundError,
    InvalidOptionError,
    VotingNotOpenError,
)
from ..repositories.ballot_repository import BallotRepository

logger = structlog.stdlib.get_logger()


class BallotService:
    def __init__(self, repository: BallotRepository, redis_url: str | None = None):
        self.repository: BallotRepository = repository
        # This dictionary is now only for cleanup tracking, not the primary data stream
        self._sse_queues: dict[str, list[asyncio.Queue[list[Tally]]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

        # Initialize Redis client if a URL is provided
        self.redis: redis.Redis | None = (
            redis.from_url(redis_url, decode_responses=True) if redis_url else None
        )

    def _get_lock(self, ballot_id: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock for a specific ballot."""
        if ballot_id not in self._locks:
            self._locks[ballot_id] = asyncio.Lock()
        return self._locks[ballot_id]

    async def list_ballots(self) -> list[Ballot]:
        """Retrieve a list of all existing ballots."""
        return await self.repository.list_all()

    async def create_ballot(
        self, ballot_create: BallotCreate, owner_id: str | None = None
    ) -> Ballot:
        """Create a new ballot and initialize its SSE client list."""
        ballot = await self.repository.create(ballot_create, owner_id=owner_id)
        self._sse_queues[ballot.ballot_id] = []

        logger.info(
            "ballot.created",
            ballot_id=ballot.ballot_id,
            owner_id=owner_id,
            measure=ballot.measure,
        )
        return ballot

    async def get_ballot(self, ballot_id: str) -> Ballot:
        """Retrieve a ballot by its ID. Raises BallotNotFoundError if not found."""
        ballot = await self.repository.get_by_id(ballot_id)
        if not ballot:
            raise BallotNotFoundError(f"Ballot {ballot_id} not found")
        return ballot

    async def record_vote(self, ballot_id: str, vote: Vote) -> None:
        """
        Record a vote for a ballot and notify all workers via Redis.
        Uses a Redis-backed distributed lock to ensure consistency across multiple workers.
        """
        lock_name = f"lock:ballot:{ballot_id}"

        try:
            if self.redis:
                # timeout=10 to prevent deadlocks if a worker crashes
                async with self.redis.lock(lock_name, timeout=10):
                    await self._do_record_vote(ballot_id, vote)
            else:
                async with self._get_lock(ballot_id):
                    await self._do_record_vote(ballot_id, vote)

            logger.info(
                "vote.recorded",
                ballot_id=ballot_id,
                option=vote.option,
                is_write_in=vote.is_write_in,
            )
        except Exception:
            # We log the exception here to ensure visibility, then re-raise
            # so the controller can handle the user response.
            logger.error(
                "vote.failed", ballot_id=ballot_id, option=vote.option, exc_info=True
            )
            raise

    async def _do_record_vote(self, ballot_id: str, vote: Vote) -> None:
        """Inner logic for recording a vote."""
        ballot = await self.get_ballot(ballot_id)
        now = datetime.now(timezone.utc)

        if ballot.start_time and now < ballot.start_time:
            raise VotingNotOpenError("Voting has not started for this ballot")
        if ballot.end_time and now > ballot.end_time:
            raise VotingNotOpenError("Voting has ended for this ballot")

        if vote.is_write_in:
            if not ballot.allow_write_in:
                raise InvalidOptionError(
                    "Write-in votes are not allowed for this ballot"
                )
        else:
            if vote.option not in ballot.options:
                raise InvalidOptionError("Invalid option for this ballot")

        await self.repository.add_vote(ballot_id, vote.option)

        # BROADCAST: Notify all workers via Redis Pub/Sub
        updated_counts = await self.get_vote_counts(ballot_id)
        if self.redis:
            data = json.dumps([t.model_dump() for t in updated_counts])
            await self.redis.publish(f"ballot:{ballot_id}:updates", data)

        for queue in self._sse_queues.get(ballot_id, []):
            await queue.put(updated_counts)

    async def get_vote_counts(self, ballot_id: str) -> list[Tally]:
        """Retrieve current vote counts for a ballot."""
        # We check if ballot exists first
        _ = await self.get_ballot(ballot_id)
        return await self.repository.get_tallies(ballot_id)

    async def register_sse_client(self, ballot_id: str) -> asyncio.Queue[list[Tally]]:
        """Register a new SSE client for a ballot and return its event queue."""
        _ = await self.get_ballot(ballot_id)
        queue: asyncio.Queue[list[Tally]] = asyncio.Queue()
        if ballot_id not in self._sse_queues:
            self._sse_queues[ballot_id] = []
        self._sse_queues[ballot_id].append(queue)
        return queue

    async def unregister_sse_client(
        self, ballot_id: str, queue: asyncio.Queue[list[Tally]]
    ):
        """Remove an SSE client's queue from a ballot's notification list."""
        if ballot_id in self._sse_queues:
            try:
                self._sse_queues[ballot_id].remove(queue)
            except ValueError:
                pass

        # Immediate cleanup if the list is now empty
        if ballot_id in self._sse_queues and not self._sse_queues[ballot_id]:
            del self._sse_queues[ballot_id]

    async def cleanup_stale_metadata(self):
        """
        Identify and remove metadata (locks, queue lists) for expired ballots.
        """
        # We work on a copy of the keys to avoid "dict changed size during iteration"
        lock_ids = set(self._locks.keys())
        queue_ids = set(self._sse_queues.keys())
        all_ids = lock_ids.union(queue_ids)

        cleaned_count = 0

        for ballot_id in all_ids:
            try:
                ballot = await self.get_ballot(ballot_id)
                status, _ = self.get_status(ballot)

                # If the ballot is ended, we can potentially clean it up
                if status == "ended":
                    # 1. Handle SSE Queues: only remove if empty
                    if (
                        ballot_id in self._sse_queues
                        and not self._sse_queues[ballot_id]
                    ):
                        del self._sse_queues[ballot_id]
                        cleaned_count += 1

                    # 2. Handle Locks
                    if ballot_id in self._locks:
                        del self._locks[ballot_id]
                        cleaned_count += 1

            except BallotNotFoundError:
                # Ballot was deleted from DB? Clean up everything.
                _ = self._sse_queues.pop(ballot_id, None)
                _ = self._locks.pop(ballot_id, None)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info("metadata.cleanup", cleaned_items=cleaned_count)

    async def listen_for_updates(
        self, ballot_id: str, queue: asyncio.Queue[list[Tally]]
    ):
        """
        Listen to Redis Pub/Sub for updates to a specific ballot and push them to the local queue.
        This allows multiple application workers to share the same update stream.
        """
        if not self.redis:
            return

        pubsub = self.redis.pubsub()
        channel = f"ballot:{ballot_id}:updates"
        await pubsub.subscribe(channel)

        logger.debug("sse.redis_subscribe", ballot_id=ballot_id, channel=channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = json.loads(str(message["data"]))
                    # Parse back into Tally objects
                    tallies = [Tally(**t) for t in data]
                    await queue.put(tallies)
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.close()
            logger.debug("sse.redis_unsubscribe", ballot_id=ballot_id)

    @staticmethod
    def format_time_delta(diff: timedelta) -> str:
        """Format a timedelta into a human-readable string (e.g., '2 hours')."""
        seconds = int(diff.total_seconds())
        if seconds < 60:
            return f"{seconds} seconds"
        minutes = seconds // 60
        if minutes < 60:
            return f"{minutes} minutes"
        hours = minutes // 60
        if hours < 24:
            return f"{hours} hours"
        days = hours // 24
        return f"{days} days"

    @staticmethod
    def get_status(ballot: Ballot) -> tuple[str, str]:
        """
        Determine the current status of a ballot based on the current time.
        Returns a tuple of (status_class, status_text).
        """
        now = datetime.now(timezone.utc)

        st = ballot.start_time
        if st and st.tzinfo is None:
            st = st.replace(tzinfo=timezone.utc)

        et = ballot.end_time
        if et and et.tzinfo is None:
            et = et.replace(tzinfo=timezone.utc)

        if st and now < st:
            return "pending", f"starts in {BallotService.format_time_delta(st - now)}"

        if et and now > et:
            return "ended", "voting closed"

        if et:
            return "active", f"ends in {BallotService.format_time_delta(et - now)}"

        return "active", "voting open"
