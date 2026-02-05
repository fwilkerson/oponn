import base64
import io
import time

from redis import asyncio as aioredis
from tink import (
    BinaryKeysetReader,
    BinaryKeysetWriter,
    KeysetHandle,
    aead,
    cleartext_keyset_handle,
    new_keyset_handle,
)

from .kms_provider import MasterKeyProvider


class CryptoService:
    """
    Handles envelope encryption using Google Tink with a two-tiered cache.
    - L1: Local process memory (short TTL)
    - L2: Redis (longer sliding TTL)
    """

    redis: aioredis.Redis | None
    _l1_cache: dict[str, tuple[KeysetHandle, float]]
    _l1_ttl: int
    provider: MasterKeyProvider

    def __init__(
        self,
        provider: MasterKeyProvider,
        redis_client: aioredis.Redis | None = None,
    ):
        aead.register()
        self.redis = redis_client
        self.provider = provider

        # L1 Cache: ballot_id -> (keyset_handle, expiry)
        self._l1_cache = {}
        self._l1_ttl = 60  # 1 minute

    async def get_ballot_keyset(
        self, ballot_id: str, encrypted_dek: str | None = None
    ) -> KeysetHandle:
        """Retrieves a decrypted keyset, checking L1 and L2 caches before hitting the KMS."""
        now = time.time()

        # 1. Check L1
        if ballot_id in self._l1_cache:
            handle, expiry = self._l1_cache[ballot_id]
            if now < expiry:
                return handle
            del self._l1_cache[ballot_id]

        # 2. Check L2 (Redis)
        l2_key = f"dek:ballot:{ballot_id}"
        if self.redis:
            serialized_keyset_b64 = await self.redis.get(l2_key)
            if serialized_keyset_b64:
                # Sliding window: refresh TTL
                await self.redis.expire(l2_key, 600)  # 10 minutes

                raw_bytes = base64.b64decode(serialized_keyset_b64)
                reader = BinaryKeysetReader(raw_bytes)
                # Note: This keyset in Redis is ALREADY decrypted (the "pass")
                handle = cleartext_keyset_handle.read(reader)

                # Populate L1
                self._l1_cache[ballot_id] = (handle, now + self._l1_ttl)
                return handle

        # 3. Cache Miss: Decrypt using Master Key (The "KMS" call)
        if not encrypted_dek:
            raise ValueError(
                f"Encrypted DEK required for cache miss on ballot {ballot_id}"
            )

        handle = await self.decrypt_ballot_keyset(encrypted_dek, ballot_id)

        # 4. Populate Caches
        self._l1_cache[ballot_id] = (handle, now + self._l1_ttl)
        if self.redis:
            # Serialize the decrypted keyset for Redis
            out = io.BytesIO()
            writer = BinaryKeysetWriter(out)
            cleartext_keyset_handle.write(writer, handle)
            await self.redis.setex(
                l2_key, 600, base64.b64encode(out.getvalue()).decode()
            )

        return handle

    def generate_ballot_keyset(self) -> KeysetHandle:
        """Generates a new unique keyset for a ballot."""
        return new_keyset_handle(aead.aead_key_templates.AES256_GCM)

    async def encrypt_ballot_keyset(
        self, keyset_handle: KeysetHandle, ballot_id: str
    ) -> str:
        """Encrypts a ballot keyset using the Master Provider (KEK)."""
        return await self.provider.encrypt_dek(keyset_handle, ballot_id)

    async def decrypt_ballot_keyset(
        self, encrypted_keyset_b64: str, ballot_id: str
    ) -> KeysetHandle:
        """Decrypts a ballot keyset using the Master Provider (KEK)."""
        return await self.provider.decrypt_dek(encrypted_keyset_b64, ballot_id)

    def encrypt_string(
        self, plaintext: str, keyset_handle: KeysetHandle, context: str = ""
    ) -> str:
        """Encrypts a string using the provided ballot keyset."""
        primitive = keyset_handle.primitive(aead.Aead)
        ciphertext = primitive.encrypt(plaintext.encode(), context.encode())
        return base64.b64encode(ciphertext).decode()

    def decrypt_string(
        self, ciphertext_b64: str, keyset_handle: KeysetHandle, context: str = ""
    ) -> str:
        """Decrypts a string using the provided ballot keyset."""
        primitive = keyset_handle.primitive(aead.Aead)
        raw_ciphertext = base64.b64decode(ciphertext_b64)
        plaintext = primitive.decrypt(raw_ciphertext, context.encode())
        return plaintext.decode()
