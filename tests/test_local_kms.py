import pytest
from src.services.kms_provider import LocalMasterKeyProvider
import tink

@pytest.mark.asyncio
async def test_local_master_key_provider():
    provider = LocalMasterKeyProvider()
    ballot_id = "test_ballot"
    
    # Generate a DEK
    dek_handle = tink.new_keyset_handle(tink.aead.aead_key_templates.AES128_GCM)
    
    # Encrypt DEK
    encrypted_dek = await provider.encrypt_dek(dek_handle, ballot_id)
    assert isinstance(encrypted_dek, str)
    assert len(encrypted_dek) > 0
    
    # Decrypt DEK
    decrypted_handle = await provider.decrypt_dek(encrypted_dek, ballot_id)
    assert isinstance(decrypted_handle, tink.KeysetHandle)
    
    # Verify we can use the decrypted DEK
    plaintext = b"hello world"
    context = b"context"
    
    aead = dek_handle.primitive(tink.aead.Aead)
    ciphertext = aead.encrypt(plaintext, context)
    
    decrypted_aead = decrypted_handle.primitive(tink.aead.Aead)
    assert decrypted_aead.decrypt(ciphertext, context) == plaintext

@pytest.mark.asyncio
async def test_local_master_key_provider_wrong_context():
    provider = LocalMasterKeyProvider()
    ballot_id = "test_ballot"
    dek_handle = tink.new_keyset_handle(tink.aead.aead_key_templates.AES128_GCM)
    
    encrypted_dek = await provider.encrypt_dek(dek_handle, ballot_id)
    
    with pytest.raises(tink.TinkError):
        await provider.decrypt_dek(encrypted_dek, "wrong_ballot_id")
