# Encryption Strategy: Column-Level Privacy with Performance

## 1. Problem Statement
We need to encrypt sensitive user fields (e.g., PII in `User` models) to enhance privacy. However, the application (`oponn`) experiences high traffic spikes. Traditional encryption methods (fetching a key from a remote KMS for every read/write) would introduce unacceptable latency and cost.

## 2. Solution: Envelope Encryption with Keyrings & Caching
We utilize the **AWS Encryption SDK for Python (v4+)** and the **AWS Cryptographic Material Providers Library (MPL)**. This modern architecture uses "Keyrings" instead of legacy "Master Key Providers" to manage Data Keys (DEKs).

### 2.1 Core Concepts

| Term | Definition | Role in Oponn |
| :--- | :--- | :--- |
| **KEK (Key Encryption Key)** | The **Master Key**. A static, highly secure key (e.g., in AWS KMS or a Raw AES key). | Protects the DEKs. We touch this as infrequently as possible. |
| **DEK (Data Key)** | A temporary key generated for the data. | Encrypts the actual database columns. |
| **Keyring** | The modern gatekeeper for Data Keys. | Responsible for generating, wrapping, and unwrapping DEKs using the KEK. |
| **CMM (Crypto Materials Manager)** | The "Brain" of the operation. | Orchestrates the caching logic and interacts with the Keyring to get DEKs. |

## 3. The Modern Architecture (MPL & Keyrings)

As of version 4.0, the AWS Encryption SDK has transitioned to the **Material Providers Library (MPL)**.

### 3.1 Why Keyrings?
*   **Identical Behavior:** Keyrings behave identically across all AWS SDK languages (Java, Python, C#, etc.).
*   **Key Commitment:** Keyrings enforce "Key Commitment," a security feature that ensures a ciphertext can only be decrypted by the exact key that encrypted it, preventing advanced cipher-substitution attacks.
*   **Clean Abstraction:** Keyrings focus purely on key operations (Wrap/Unwrap), making it easier to swap providers (e.g., moving from a local Raw AES key to AWS KMS).

### 3.2 The Read/Decrypt Flow with Caching
When the application reads a record:

1.  **Fetch:** App retrieves the Base64 string from Postgres.
2.  **Parse:** The SDK decodes the header and identifies the correct Keyring.
3.  **Cache Check:**
    *   **Cache Hit:** The SDK retrieves the **Plaintext DEK** from local RAM. **0ms latency.**
    *   **Cache Miss:** The CMM asks the **Keyring** to "Unwrap" the DEK using the Master Key. The result is cached.
4.  **Decrypt:** The Plaintext DEK decrypts the user data.

## 4. Tuning Guide: Caching & Performance

| Parameter | Recommended | Description |
| :--- | :--- | :--- |
| **`max_messages_encrypted`** | **1,000** | **Write Control.** How many rows share the same DEK. 1,000 provides a good balance. |
| **`max_age`** | **300.0s** | **Time Limit.** Forces rotation after 5 minutes. |
| **`capacity`** | **100** | **Memory Limit.** Number of unique DEKs in RAM. Uses LRU eviction. |

## 5. Security Architecture & Trade-offs

### 5.1 Local RAM vs. Redis
We use **Local Memory** for caching plaintext DEKs to minimize the attack surface. Broadcasting plaintext keys to Redis significantly increases risk and introduces network latency.

### 5.2 Encryption Context (Binding)
To prevent **"Confused Deputy"** attacks, we bind every encryption to a `user_id` context.
*   **Encrypt:** `context={"user_id": "123", "field": "email"}`
*   **Decrypt:** `context={"user_id": "123", "field": "email"}`
If the context doesn't match, decryption fails.

## 6. Implementation Detail

### 6.1 Dependencies
```toml
[tool.poetry.dependencies]
aws-encryption-sdk = "^4.0.0"
aws-cryptographic-material-providers-library = "^1.0.0"
```

### 6.2 Modern Code Pattern (v4+)
`src/services/crypto_service.py`

```python
from aws_cryptographic_material_providers.mpl import AwsCryptographicMaterialProviders
from aws_cryptographic_material_providers.mpl.models import CreateRawAesKeyringInput, ...

# 1. Initialize MPL
mpl_client = AwsCryptographicMaterialProviders()

# 2. Create Keyring
keyring = mpl_client.create_raw_aes_keyring(
    CreateRawAesKeyringInput(
        key_name="oponn-master-v1",
        key_namespace="oponn",
        wrapping_alg=AesWrappingAlg.ALG_AES_256_GCM_IV12_TAG16,
        plaintext_aes_key=master_key_bytes
    )
)

# 3. Create CMM with Caching
cmm = mpl_client.create_default_cryptographic_materials_manager(
    CreateDefaultCryptographicMaterialsManagerInput(keyring=keyring)
)
# (Caching is then wrapped around this CMM)
```