import pytest
from src.services.kms_provider import LocalMasterKeyProvider
from tink import KeysetHandle, TinkError, new_keyset_handle
from tink.aead import Aead, aead_key_templates


@pytest.mark.asyncio
async def test_local_master_key_provider():
    provider = LocalMasterKeyProvider()
    ballot_id = "test_ballot"

    # Generate a DEK
    dek_handle = new_keyset_handle(aead_key_templates.AES128_GCM)

    # Encrypt DEK
    encrypted_dek = await provider.encrypt_dek(dek_handle, ballot_id)
    assert isinstance(encrypted_dek, str)
    assert len(encrypted_dek) > 0

    # Decrypt DEK
    decrypted_handle = await provider.decrypt_dek(encrypted_dek, ballot_id)
    assert isinstance(decrypted_handle, KeysetHandle)

    # Verify we can use the decrypted DEK
    plaintext = b"hello world"
    context = b"context"

    aead = dek_handle.primitive(Aead)
    ciphertext = aead.encrypt(plaintext, context)

    decrypted_aead = decrypted_handle.primitive(Aead)
    assert decrypted_aead.decrypt(ciphertext, context) == plaintext


@pytest.mark.asyncio
async def test_local_master_key_provider_wrong_context():
    provider = LocalMasterKeyProvider()
    ballot_id = "test_ballot"
    dek_handle = new_keyset_handle(aead_key_templates.AES128_GCM)

    encrypted_dek = await provider.encrypt_dek(dek_handle, ballot_id)

    with pytest.raises(TinkError):
        await provider.decrypt_dek(encrypted_dek, "wrong_ballot_id")
