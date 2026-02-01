import asyncio
import json
from datetime import datetime, timedelta, timezone

from anyio import to_thread
from redis import asyncio as aioredis
import structlog

from ..models.ballot_models import Ballot, BallotCreate, Tally, Vote
from ..models.exceptions import (
    BallotNotFoundError,
    InvalidOptionError,
    VotingNotOpenError,
)
from ..repositories.ballot_repository import BallotRepository
from .crypto_service import CryptoService
from ..repositories.models import BallotTable

logger = structlog.stdlib.get_logger()


class BallotStateManager:
    """
    Singleton container for shared in-memory state.
    Holds asyncio Locks and SSE Queues that must persist across requests.
    """

    def __init__(self):
        self._sse_queues: dict[str, list[asyncio.Queue[list[Tally]]]] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    def get_lock(self, ballot_id: str) -> asyncio.Lock:
        """Get or create an asyncio.Lock for a specific ballot."""
        if ballot_id not in self._locks:
            self._locks[ballot_id] = asyncio.Lock()
        return self._locks[ballot_id]

    def clear(self):
        """Helper for testing to reset state."""
        self._sse_queues.clear()
        self._locks.clear()


class BallotService:
    repository: BallotRepository
    crypto: CryptoService
    state: BallotStateManager
    redis: aioredis.Redis | None

    def __init__(
        self,
        repository: BallotRepository,
        crypto: CryptoService,
        state_manager: BallotStateManager,
        redis_client: aioredis.Redis | None = None,
    ):
        self.repository = repository
        self.crypto = crypto
        self.state = state_manager
        self.redis = redis_client

    async def list_ballots(self) -> list[Ballot]:
        """Retrieve a list of all existing ballots."""
        tables = await self.repository.list_all()
        results = []
        for t in tables:
            results.append(await self._table_to_model(t))
        return results

    async def _table_to_model(self, table: BallotTable) -> Ballot:
        """Helper to decrypt a table row into a domain model."""
        keyset_handle = await self.crypto.get_ballot_keyset(
            table.id, table.encrypted_dek
        )

        def _decrypt_ballot_data():
            measure = self.crypto.decrypt_string(
                table.encrypted_measure, keyset_handle, context="measure"
            )

            option_map = {}
            options_text = []
            for opt in table.options:
                txt = self.crypto.decrypt_string(
                    opt.encrypted_text, keyset_handle, context="option"
                )
                option_map[opt.id] = txt
                if not opt.is_write_in:
                    options_text.append(txt)
            return measure, options_text, option_map

        # Offload decryption to a thread to avoid blocking the event loop
        measure, options_text, option_map = await to_thread.run_sync(
            _decrypt_ballot_data
        )

        return Ballot(
            ballot_id=table.id,
            owner_id=table.owner_id,
            measure=measure,
            options=options_text,
            option_map=option_map,
            allow_write_in=table.allow_write_in,
            start_time=table.start_time,
            end_time=table.end_time,
        )

    async def create_ballot(
        self, ballot_create: BallotCreate, owner_id: str | None = None
    ) -> Ballot:
        """Create a new ballot and initialize its SSE client list."""
        # 1. Generate new keyset (CPU bound)
        keyset_handle = await to_thread.run_sync(self.crypto.generate_ballot_keyset)

        # 2. Encrypt metadata
        from ..repositories.models import generate_id

        ballot_id = generate_id()

        def _encrypt_ballot_data():
            enc_dek = self.crypto.encrypt_ballot_keyset(keyset_handle, ballot_id)
            enc_measure = self.crypto.encrypt_string(
                ballot_create.measure, keyset_handle, context="measure"
            )
            enc_options = [
                self.crypto.encrypt_string(opt, keyset_handle, context="option")
                for opt in ballot_create.options
            ]
            return enc_dek, enc_measure, enc_options

        # Offload encryption to thread
        enc_dek, enc_measure, enc_options = await to_thread.run_sync(
            _encrypt_ballot_data
        )

        # 3. Save to DB
        table = await self.repository.create_ballot_record(
            ballot_id=ballot_id,
            encrypted_measure=enc_measure,
            encrypted_dek=enc_dek,
            options=enc_options,
            allow_write_in=ballot_create.allow_write_in,
            start_time=ballot_create.start_time,
            end_time=ballot_create.end_time,
            owner_id=owner_id,
        )

        self.state._sse_queues[table.id] = []

        logger.info(
            "ballot.created",
            ballot_id=table.id,
            owner_id=owner_id,
        )
        return await self._table_to_model(table)

    async def get_ballot(self, ballot_id: str) -> Ballot:
        """Retrieve a ballot by its ID. Raises BallotNotFoundError if not found."""
        table = await self.repository.get_by_id(ballot_id)
        if not table:
            raise BallotNotFoundError(f"Ballot {ballot_id} not found")
        return await self._table_to_model(table)

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
                async with self.state.get_lock(ballot_id):
                    await self._do_record_vote(ballot_id, vote)

            logger.info(
                "vote.recorded",
                ballot_id=ballot_id,
                is_write_in=vote.is_write_in,
            )
        except Exception:
            logger.error("vote.failed", ballot_id=ballot_id, exc_info=True)
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
            if not vote.write_in_value:
                raise InvalidOptionError("Write-in value is empty")

            # Encrypt the write-in
            table = await self.repository.get_by_id(ballot_id)
            if not table:
                raise BallotNotFoundError(ballot_id)
            keyset_handle = await self.crypto.get_ballot_keyset(
                table.id, table.encrypted_dek
            )

            # Offload write-in encryption
            enc_val = await to_thread.run_sync(
                self.crypto.encrypt_string,
                vote.write_in_value,
                keyset_handle,
                "option",
            )

            # Add option and get ID
            oid = await self.repository.add_write_in_option(ballot_id, enc_val)
            await self.repository.add_vote(ballot_id, oid)
        else:
            if vote.option_id not in ballot.option_map:
                raise InvalidOptionError("Invalid option for this ballot")
            await self.repository.add_vote(ballot_id, vote.option_id)

        # BROADCAST: Notify all workers via Redis Pub/Sub
        updated_counts = await self.get_vote_counts(ballot_id)
        if self.redis:
            data = json.dumps([t.model_dump() for t in updated_counts])
            await self.redis.publish(f"ballot:{ballot_id}:updates", data)

        for queue in self.state._sse_queues.get(ballot_id, []):
            await queue.put(updated_counts)

    async def get_vote_counts(self, ballot_id: str) -> list[Tally]:
        """Retrieve current vote counts for a ballot."""
        ballot = await self.get_ballot(ballot_id)

        tallies_raw = await self.repository.get_tallies(ballot_id)
        counts_dict = {oid: count for oid, count in tallies_raw}

        results = []
        for oid, text in ballot.option_map.items():
            results.append(Tally(option=text, count=counts_dict.get(oid, 0)))

        return results

    async def register_sse_client(self, ballot_id: str) -> asyncio.Queue[list[Tally]]:
        """Register a new SSE client for a ballot and return its event queue."""
        _ = await self.get_ballot(ballot_id)
        queue: asyncio.Queue[list[Tally]] = asyncio.Queue()
        if ballot_id not in self.state._sse_queues:
            self.state._sse_queues[ballot_id] = []
        self.state._sse_queues[ballot_id].append(queue)
        return queue

    async def unregister_sse_client(
        self, ballot_id: str, queue: asyncio.Queue[list[Tally]]
    ):
        """Remove an SSE client's queue from a ballot's notification list."""
        if ballot_id in self.state._sse_queues:
            try:
                self.state._sse_queues[ballot_id].remove(queue)
            except ValueError:
                pass

        if (
            ballot_id in self.state._sse_queues
            and not self.state._sse_queues[ballot_id]
        ):
            del self.state._sse_queues[ballot_id]

    async def cleanup_stale_metadata(self):
        """
        Identify and remove metadata (locks, queue lists) for expired ballots.
        """
        lock_ids = set(self.state._locks.keys())
        queue_ids = set(self.state._sse_queues.keys())
        all_ids = lock_ids.union(queue_ids)

        cleaned_count = 0

        for ballot_id in all_ids:
            try:
                ballot = await self.get_ballot(ballot_id)
                status, _ = self.get_status(ballot)

                if status == "ended":
                    if (
                        ballot_id in self.state._sse_queues
                        and not self.state._sse_queues[ballot_id]
                    ):
                        del self.state._sse_queues[ballot_id]
                        cleaned_count += 1

                    if ballot_id in self.state._locks:
                        del self.state._locks[ballot_id]
                        cleaned_count += 1

            except BallotNotFoundError:
                _ = self.state._sse_queues.pop(ballot_id, None)
                _ = self.state._locks.pop(ballot_id, None)
                cleaned_count += 1

        if cleaned_count > 0:
            logger.info("metadata.cleanup", cleaned_items=cleaned_count)

    async def listen_for_updates(
        self, ballot_id: str, queue: asyncio.Queue[list[Tally]]
    ):
        """
        Listen to Redis Pub/Sub for updates to a specific ballot and push them to the local queue.
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
