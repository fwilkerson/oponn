import io
import time
import tink
from tink import aead
from tink import cleartext_keyset_handle
import base64
from redis import asyncio as aioredis


class CryptoService:
    """
    Handles envelope encryption using Google Tink with a two-tiered cache.
    - L1: Local process memory (short TTL)
    - L2: Redis (longer sliding TTL)
    """

    redis: aioredis.Redis | None
    _l1_cache: dict[str, tuple[tink.KeysetHandle, float]]
    _l1_ttl: int
    master_keyset_handle: tink.KeysetHandle
    master_aead: aead.Aead

    def __init__(
        self,
        master_keyset_json: str | None = None,
        redis_client: aioredis.Redis | None = None,
    ):
        aead.register()
        self.redis = redis_client

        # L1 Cache: ballot_id -> (keyset_handle, expiry)
        self._l1_cache: dict[str, tuple[tink.KeysetHandle, float]] = {}
        self._l1_ttl = 60  # 1 minute

        if master_keyset_json:
            reader = tink.JsonKeysetReader(master_keyset_json)
            self.master_keyset_handle = cleartext_keyset_handle.read(reader)
        else:
            self.master_keyset_handle = tink.new_keyset_handle(
                aead.aead_key_templates.AES256_GCM
            )

        self.master_aead = self.master_keyset_handle.primitive(aead.Aead)

    async def get_ballot_keyset(
        self, ballot_id: str, encrypted_dek: str | None = None
    ) -> tink.KeysetHandle:
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
                reader = tink.BinaryKeysetReader(raw_bytes)
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

        handle = self.decrypt_ballot_keyset(encrypted_dek, ballot_id)

        # 4. Populate Caches
        self._l1_cache[ballot_id] = (handle, now + self._l1_ttl)
        if self.redis:
            # Serialize the decrypted keyset for Redis
            out = io.BytesIO()
            writer = tink.BinaryKeysetWriter(out)
            cleartext_keyset_handle.write(writer, handle)
            await self.redis.setex(
                l2_key, 600, base64.b64encode(out.getvalue()).decode()
            )

        return handle

    def generate_ballot_keyset(self) -> tink.KeysetHandle:
        """Generates a new unique keyset for a ballot."""
        return tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)

    def encrypt_ballot_keyset(
        self, keyset_handle: tink.KeysetHandle, ballot_id: str
    ) -> str:
        """Encrypts a ballot keyset using the Master AEAD."""
        out = io.BytesIO()
        writer = tink.BinaryKeysetWriter(out)
        context = f"ballot:{ballot_id}".encode()
        keyset_handle.write_with_associated_data(writer, self.master_aead, context)
        return base64.b64encode(out.getvalue()).decode()

    def decrypt_ballot_keyset(
        self, encrypted_keyset_b64: str, ballot_id: str
    ) -> tink.KeysetHandle:
        """Decrypts a ballot keyset using the Master AEAD."""
        raw_bytes = base64.b64decode(encrypted_keyset_b64)
        reader = tink.BinaryKeysetReader(raw_bytes)
        context = f"ballot:{ballot_id}".encode()
        return tink.read_keyset_handle_with_associated_data(
            reader, self.master_aead, context
        )

    def encrypt_string(
        self, plaintext: str, keyset_handle: tink.KeysetHandle, context: str = ""
    ) -> str:
        """Encrypts a string using the provided ballot keyset."""
        primitive = keyset_handle.primitive(aead.Aead)
        ciphertext = primitive.encrypt(plaintext.encode(), context.encode())
        return base64.b64encode(ciphertext).decode()

    def decrypt_string(
        self, ciphertext_b64: str, keyset_handle: tink.KeysetHandle, context: str = ""
    ) -> str:
        """Decrypts a string using the provided ballot keyset."""
        primitive = keyset_handle.primitive(aead.Aead)
        raw_ciphertext = base64.b64decode(ciphertext_b64)
        plaintext = primitive.decrypt(raw_ciphertext, context.encode())
        return plaintext.decode()
