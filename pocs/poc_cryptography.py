import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

# --- SETUP (Infrastructure/One-time) ---
# In production, this KEK is an environment variable or from a KMS
MASTER_KEY_KEK = AESGCM.generate_key(bit_length=256)

def poc_cryptography():
    print("--- Cryptography (AES-GCM) POC ---")
    
    # 1. GENERATE BALLOT DEK
    ballot_dek = AESGCM.generate_key(bit_length=256)
    
    # 2. ENCRYPT DEK WITH MASTER KEY (For storage in DB)
    kek_cipher = AESGCM(MASTER_KEY_KEK)
    nonce_dek = os.urandom(12)
    encrypted_dek_blob = nonce_dek + kek_cipher.encrypt(nonce_dek, ballot_dek, b"ballot_context")
    
    # Simulate DB Storage
    db_encrypted_dek = base64.b64encode(encrypted_dek_blob).decode()
    print(f"Stored Encrypted DEK: {db_encrypted_dek[:32]}...")

    # 3. DECRYPT DEK FOR USE (Simulate Worker Fetching from DB/Cache)
    raw_blob = base64.b64decode(db_encrypted_dek)
    nonce_read = raw_blob[:12]
    ciphertext_read = raw_blob[12:]
    decrypted_ballot_dek = kek_cipher.decrypt(nonce_read, ciphertext_read, b"ballot_context")

    # 4. ENCRYPT DATA (The Vote)
    data = b"Option A"
    ballot_cipher = AESGCM(decrypted_ballot_dek)
    nonce_vote = os.urandom(12)
    encrypted_vote = nonce_vote + ballot_cipher.encrypt(nonce_vote, data, None)
    
    print(f"Encrypted Vote: {base64.b64encode(encrypted_vote).decode()}")

    # 5. DECRYPT DATA (For Tallies/UI)
    v_nonce = encrypted_vote[:12]
    v_ct = encrypted_vote[12:]
    decrypted_vote = ballot_cipher.decrypt(v_nonce, v_ct, None)
    print(f"Decrypted Vote: {decrypted_vote.decode()}")

if __name__ == "__main__":
    poc_cryptography()
