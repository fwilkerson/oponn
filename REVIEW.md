# Cryptography vs. Google Tink: Comparison for Oponn

## At a Glance

| Feature | `cryptography` (PyCA) | `tink` (Google) |
| :--- | :--- | :--- |
| **Philosophy** | "Hazardous Materials" + Recipes | Misuse-resistant by design |
| **Key Management** | Manual (You handle nonces/IVs) | Automated (Encapsulated in Keysets) |
| **Cloud Integration** | Manual / Third-party | Native (AWS/GCP/Azure KMS) |
| **Complexity** | High (Requires understanding nonces) | Low (API handles details) |
| **Dependency Weight** | Lightweight (Standard in Python) | Heavier (C++ core via `tink-python`) |

---

## 1. Code Maintenance (The "Developer Experience")

### `cryptography` (Low-Level Control)
*   **Maintenance Burden:** High. Developers must manually manage **Nonces/IVs**. If a developer reuses a nonce with the same key, the encryption is broken (AES-GCM weakness).
*   **Storage:** You store `Nonce + Ciphertext`. You are responsible for the serialization format.
*   **Risk:** Easy to "do it wrong" if a junior engineer modifies the encryption utility.

### `tink` (High-Level Abstraction)
*   **Maintenance Burden:** Low. `tink` handles nonces, key rotation, and serialization internally.
*   **Storage:** You store a `Keyset`. A Keyset can contain multiple keys, allowing for **seamless key rotation** (the old key stays in the set to decrypt old data, while the new key encrypts new data).
*   **Risk:** Very difficult to misuse. The API forces "Authenticated Encryption" (AEAD).

---

## 2. Distributed Performance (Redis & DEKs)

### `cryptography`
*   **Pros:** Extremely fast. We cache a 32-byte raw key in Redis.
*   **Cons:** No built-in support for key rotation. Rotating the Master Key means re-encrypting every DEK in the database manually.

### `tink`
*   **Pros:** Built-in rotation. We cache the serialized `Keyset` in Redis.
*   **Cons:** Slightly more CPU overhead due to the abstraction layer, but negligible compared to network I/O.

---

## 3. Staff Engineer's Recommendation

For Oponn, I recommend **Google Tink**.

**Why?**
1.  **Key Rotation is Free:** In a system handling sensitive votes, we *will* want to rotate keys. Tink makes this a configuration change rather than a migration nightmare.
2.  **Misuse Resistance:** As Oponn grows, we want to ensure that a mistake in a PR doesn't compromise the privacy of thousands of voters. Tink’s "Keyset" abstraction is a much safer interface for a team than raw AES-GCM primitives.
3.  **Vendor Neutrality:** While Google-made, Tink is open-source and supports AWS, GCP, and HashiCorp Vault. It prevents us from being locked into a single cloud provider's proprietary encryption SDK while giving us the same level of safety.

## POC Files
*   `pocs/poc_cryptography.py`: Demonstrates manual nonce and key handling.
*   `pocs/poc_tink.py`: Demonstrates Keyset-based encryption with metadata.