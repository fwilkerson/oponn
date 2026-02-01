# Epic: Ballot & Vote Privacy (Column-Level Encryption)

## Overview
Oponn requires "utmost privacy" for its users. This epic covers the implementation of application-side column-level encryption for all sensitive ballot data, including measures, options, and user-submitted write-ins. The system must remain performant under high concurrency (10k+ concurrent voters).

## Architectural Strategy: Envelope Encryption
We will implement an **Envelope Encryption** pattern to balance security and performance.

### 1. Key Hierarchy
*   **Master Key (KEK - Key Encryption Key):** A high-entropy 256-bit key stored in the environment. This key never touches the database.
*   **Ballot Key (DEK - Data Encryption Key):** A unique AES-256-GCM key generated for every individual ballot. 
*   **Storage:** The DEK is stored in the `ballots` table, encrypted by the Master Key (`encrypted_dek`).

### 2. Implementation Details
*   **Library:** `cryptography` (Python). We will use `AES-GCM` for Authenticated Encryption, providing both confidentiality and integrity protection.
*   **Concurrency Optimization:** Decrypted DEKs will be cached in **Redis** with a short TTL (e.g., 5 minutes) to avoid redundant KEK decryption operations during traffic spikes.
*   **Data Masking:** Sensitive strings (`measure`, `option_text`) will be encrypted at the application layer before being sent to the database.

## Database Refactor & Normalization
To reduce the encryption surface area and improve performance, we will refactor the relationship between votes and options.

### Current State
*   `VoteTable` stores raw `option_text` for every vote.
*   Encryption would require encrypting the string for *every* row in the `votes` table, leading to massive storage overhead and slow tallies.

### Future State (Refactored)
*   **`OptionTable`**: Stores `encrypted_text`.
*   **`VoteTable`**: Stores `option_id` (Integer/Foreign Key) instead of raw text.
*   **Write-ins**: When a user submits a write-in, a new row is added to `OptionTable` for that ballot, marked as `is_write_in=True`. The `VoteTable` then references this new ID.
*   **Impact**: Tallies become simple integer counts/group-bys on `option_id`, which is significantly faster during spikes.

## Performance & Scaling
*   **Write Path:** Encryption happens in the worker process using the cached DEK. Sub-millisecond latency.
*   **Read Path (Tallies):** The database performs counts on unencrypted foreign keys. Only the "Option Names" (the unique list) are decrypted for the final UI render.
*   **Cache Strategy:** Redis acts as a distributed "Hot Key" store for DEKs, ensuring horizontal scalability across Gunicorn workers.

## Caching Strategy & Technical Rationale

### 1. Two-Tiered DEK Cache
To protect against high-traffic spikes (10k+ concurrent voters), we utilize a two-tiered caching strategy for Data Encryption Keys (DEKs).

*   **L1 (Process Memory):** A 60-second local LRU cache in each FastAPI worker. 
    *   *Purpose:* Zero-latency access for "supernova" spikes, protecting against Redis network saturation.
*   **L2 (Redis):** A 10-minute sliding window cache shared across the cluster.
    *   *Purpose:* Avoids redundant KMS calls across horizontally scaled workers.
*   **KMS (Source of Truth):** Only hit on an L1+L2 miss.

### 2. Why avoid the KMS? (KMS vs. Redis Latency)
Even when deployed in the same cloud region, a KMS call is significantly "slower" than a Redis call:

| Feature | Redis | Cloud KMS |
| :--- | :--- | :--- |
| **Protocol** | Lightweight TCP (RESP) | Heavyweight HTTPS (REST) |
| **Overhead** | Minimal serialization | TLS Handshake + JSON Parsing + Auth check |
| **Internal Work** | Hash map lookup (O(1)) | Hardware Security Module (HSM) transit + Decryption |
| **P99 Latency** | **< 1ms** | **10ms - 50ms** |
| **Throughput** | Millions of ops/sec | Highly rate-limited (e.g., 1,000 - 10,000 tps) |

**Conclusion:** Relying on the KMS for every vote would introduce a massive bottleneck and potential point of failure during a traffic spike. Redis allows us to keep the "hot" keys at wire speed while the KMS remains the secure root of trust.

### 3. Trust Boundary
*   **Plaintext Sensitive Data:** Only ever exists in the volatile memory (RAM) of the worker process during request execution.
*   **DEKs in Redis:** Stored as raw bytes in a secured, private Redis instance. While "plaintext" relative to the DEK, they are useless without access to the ciphertext stored in the primary SQL database. This isolation creates a "Two-Key" requirement for a successful breach.
