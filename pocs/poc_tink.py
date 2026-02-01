import tink
from tink import aead
from tink import cleartext_keyset_handle
import io

# --- SETUP (Infrastructure/One-time) ---
aead.register()

# In Tink, the "Master Key" is usually a Keyset or a KMS integration.
# For this POC, we use a cleartext keyset to simulate the Master KEK.
# In production, this would be: 
# master_key_aead = kms_client.get_aead("aws-kms://...")
keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
master_key_aead = keyset_handle.primitive(aead.Aead)

def poc_tink():
    print("\n--- Google Tink POC ---")

    # 1. GENERATE BALLOT DEK (As a Keyset)
    ballot_keyset_handle = tink.new_keyset_handle(aead.aead_key_templates.AES256_GCM)
    
    # 2. ENCRYPT DEK WITH MASTER KEY (For storage in DB)
    # Tink handles the serialization and encryption of the keyset in one go.
    out = io.BytesIO()
    writer = tink.BinaryKeysetWriter(out)
    ballot_keyset_handle.write_with_metadata(writer, master_key_aead, b"ballot_context")
    db_encrypted_dek = out.getvalue()
    print(f"Stored Encrypted Keyset (DEK): {db_encrypted_dek.hex()[:32]}...")

    # 3. DECRYPT DEK FOR USE
    reader = tink.BinaryKeysetReader(io.BytesIO(db_encrypted_dek))
    decrypted_keyset_handle = tink.read_keyset_handle_with_metadata(reader, master_key_aead, b"ballot_context")
    ballot_aead = decrypted_keyset_handle.primitive(aead.Aead)

    # 4. ENCRYPT DATA (The Vote)
    data = b"Option A"
    encrypted_vote = ballot_aead.encrypt(data, b"vote_context")
    print(f"Encrypted Vote: {encrypted_vote.hex()}")

    # 5. DECRYPT DATA
    decrypted_vote = ballot_aead.decrypt(encrypted_vote, b"vote_context")
    print(f"Decrypted Vote: {decrypted_vote.decode()}")

if __name__ == "__main__":
    poc_tink()
