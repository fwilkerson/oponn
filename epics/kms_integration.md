# Epic: KMS Integration (AWS & LocalStack)

## Overview
Currently, Oponn relies on a "Master Key" (KEK) provided via an environment variable. While functional, this is a security anti-pattern for production systems. This epic covers the migration to a cloud-native **Key Management Service (KMS)** to provide Hardware Security Module (HSM) backed security, automated rotation, and comprehensive audit logging.

## 1. Rationale: Why KMS vs. Manual Generation?

### Security Boundary (The HSM)
In our current setup, the plaintext Master Key exists in the process environment and memory. If a worker process is compromised, the key is easily exfiltrated. With a KMS (like AWS KMS), the **plaintext key never leaves the KMS infrastructure**. We send the "Encrypted DEK" to the KMS, it decrypts it internally using its hardware, and sends the "Plaintext DEK" back to us.

### Access Control & Audit
- **IAM Policies:** We can restrict KMS usage to specific IAM roles (e.g., only the production worker can decrypt).
- **CloudTrail:** Every single decryption/encryption event is logged. We can audit exactly when and why a Ballot Key was accessed.

### High Availability
AWS KMS is a distributed, multi-AZ service. Managing our own high-availability key storage is a massive operational burden that we offload to the provider.

## 2. Key Rotation Mechanics

### Transparent Rotation
AWS KMS supports **Automatic Key Rotation**. When enabled, the KMS generates a new backing key every year. 

*   **Encryption:** The KMS always uses the *latest* version of the key to encrypt new data.
*   **Decryption:** The KMS retains all older versions of the key. When we send an "Encrypted DEK" that was created two years ago, the KMS identifies which version was used and decrypts it automatically.
*   **Impact:** Our application code remains identical during a rotation. We don't need to re-encrypt old ballots.

## 3. Implementation Plan

### Architecture Refactor
We will update `CryptoService` to support multiple "Master Key Providers."
- **Development/Test:** Uses a LocalStack KMS provider.
- **Production:** Uses the AWS KMS provider.

### The "Envelope" remains the same
Our existing hierarchy stays:
1. `Ballot DEK` (AES-GCM) encrypts the Ballot data.
2. `KMS Master Key` (KEK) encrypts the `Ballot DEK`.
3. Only the `Encrypted DEK` is stored in Postgres.

## 4. Development & Testing Strategy

### LocalStack (Mocking AWS)
To maintain our "offline-first" developer loop, we will use **LocalStack** in our `docker-compose.yml`. 
- `make services-up` will now launch a LocalStack container.
- `manage.py infra up` will automatically provision a "Mock KEK" in LocalStack and set the `KMS_KEY_ID` in the local environment.

### Test Isolation
We will use `testcontainers-python` with the `LocalStackContainer` in `tests/conftest.py`.
- Each test run (or suite) will get a fresh, isolated KMS environment.
- This ensures that our integration tests for encryption are 100% representative of production behavior without hitting real AWS or incurring costs.

## 5. Migration Path
1. **Phase 1:** Add LocalStack to `docker-compose` and `manage.py`.
2. **Phase 2:** Refactor `CryptoService` to use `boto3` (Async-wrapped) for KMS operations.
3. **Phase 3:** Create a migration utility to re-encrypt existing "Env-Key" DEKs with the new "KMS" KEK.
4. **Phase 4:** Remove legacy environment-based key support.
