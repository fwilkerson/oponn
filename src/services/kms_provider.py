import abc
import base64
import io
from typing import Any

import aioboto3
import tink
from tink import cleartext_keyset_handle


class MasterKeyProvider(abc.ABC):
    """Abstract interface for Master Key operations (KEK)."""

    @abc.abstractmethod
    async def encrypt_dek(self, dek_handle: tink.KeysetHandle, ballot_id: str) -> str:
        """Encrypts a Tink KeysetHandle (DEK) and returns a base64 string."""
        pass

    @abc.abstractmethod
    async def decrypt_dek(
        self, encrypted_dek_b64: str, ballot_id: str
    ) -> tink.KeysetHandle:
        """Decrypts a base64 string into a Tink KeysetHandle (DEK)."""
        pass


class LocalMasterKeyProvider(MasterKeyProvider):
    """
    Development provider that uses a local, static master key.
    Enables encryption/decryption logic without an external KMS.
    """

    def __init__(self):
        # Ensure Tink AEAD is registered before we use it
        tink.aead.register()
        # A static keyset for development. DO NOT USE IN PRODUCTION.
        # This allows us to exercise the full Tink pipeline.
        self.keyset_handle = tink.new_keyset_handle(tink.aead.aead_key_templates.AES128_GCM)
        self.aead = self.keyset_handle.primitive(tink.aead.Aead)

    async def encrypt_dek(self, dek_handle: tink.KeysetHandle, ballot_id: str) -> str:
        # 1. Serialize DEK to binary
        out = io.BytesIO()
        writer = tink.BinaryKeysetWriter(out)
        cleartext_keyset_handle.write(writer, dek_handle)
        plaintext_dek = out.getvalue()

        # 2. Encrypt using local AEAD (including context as associated data)
        ciphertext = self.aead.encrypt(plaintext_dek, ballot_id.encode())
        return base64.b64encode(ciphertext).decode()

    async def decrypt_dek(
        self, encrypted_dek_b64: str, ballot_id: str
    ) -> tink.KeysetHandle:
        ciphertext = base64.b64decode(encrypted_dek_b64)

        # 1. Decrypt using local AEAD
        plaintext_dek = self.aead.decrypt(ciphertext, ballot_id.encode())

        # 2. Deserialize to Tink handle
        reader = tink.BinaryKeysetReader(plaintext_dek)
        return cleartext_keyset_handle.read(reader)


class AwsKmsMasterKeyProvider(MasterKeyProvider):
    """Production provider using AWS KMS via aioboto3."""

    def __init__(
        self,
        key_id: str,
        endpoint_url: str | None = None,
        access_key: str | None = None,
        secret_key: str | None = None,
        region: str = "us-east-1",
        is_production: bool = False,
    ):
        self.key_id = key_id
        self.endpoint_url = endpoint_url
        self.region = region
        self.is_production = is_production
        self.access_key = access_key
        self.secret_key = secret_key

        # In non-production, fallback to 'test' credentials if none are provided
        if not self.is_production:
            self.access_key = self.access_key or "test"
            self.secret_key = self.secret_key or "test"

        session_kwargs: dict[str, Any] = {
            "region_name": self.region,
        }
        if self.access_key:
            session_kwargs["aws_access_key_id"] = self.access_key
        if self.secret_key:
            session_kwargs["aws_secret_access_key"] = self.secret_key

        self.session = aioboto3.Session(**session_kwargs)

    def _get_client_args(self) -> dict[str, Any]:
        args: dict[str, Any] = {
            "region_name": self.region,
        }

        if not self.endpoint_url:
            return args

        args["endpoint_url"] = self.endpoint_url

        # Explicitly pass credentials for LocalStack clients
        if not self.is_production:
            args["aws_access_key_id"] = self.access_key
            args["aws_secret_access_key"] = self.secret_key

        args["use_ssl"] = False
        args["verify"] = False
        return args

    async def encrypt_dek(self, dek_handle: tink.KeysetHandle, ballot_id: str) -> str:
        # 1. Serialize DEK to binary
        out = io.BytesIO()
        writer = tink.BinaryKeysetWriter(out)
        cleartext_keyset_handle.write(writer, dek_handle)
        plaintext_dek = out.getvalue()

        # 2. Encrypt via AWS KMS
        async with self.session.client("kms", **self._get_client_args()) as kms:  # type: ignore
            response = await kms.encrypt(
                KeyId=self.key_id,
                Plaintext=plaintext_dek,
                EncryptionContext={"ballot_id": ballot_id},
            )
            return base64.b64encode(response["CiphertextBlob"]).decode()

    async def decrypt_dek(
        self, encrypted_dek_b64: str, ballot_id: str
    ) -> tink.KeysetHandle:
        ciphertext = base64.b64decode(encrypted_dek_b64)

        # 1. Decrypt via AWS KMS
        async with self.session.client("kms", **self._get_client_args()) as kms:  # type: ignore
            response = await kms.decrypt(
                CiphertextBlob=ciphertext,
                EncryptionContext={"ballot_id": ballot_id},
            )
            plaintext_dek = response["Plaintext"]

        # 2. Deserialize to Tink handle
        reader = tink.BinaryKeysetReader(plaintext_dek)
        return cleartext_keyset_handle.read(reader)
