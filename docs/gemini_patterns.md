  ### 1. Why did I initially suggest the low-level (cryptography) approach?

  Reflex for "Minimalism" and "Vendor Agnosticism".
  My default training often prioritizes:
   1. Fewer Dependencies: The cryptography library is the de-facto standard in Python.
      It's lightweight and doesn't pull in the entire AWS SDK ecosystem (boto3, etc.).
   2. No Vendor Lock-in: The aws-encryption-sdk—while open source—is heavily opinionated
      towards AWS Key Management Service (KMS) patterns. My initial thought was, "If the
      user isn't on AWS yet, they might not want a library named aws-something."
   3. Educational Clarity: Sometimes, explaining "Here is the IV, here is the Ciphertext"
      (low-level) helps a user understand the mechanics better than "Here is a magic black
      box" (high-level).

  However, this was a strategic error on my part.
  For security specifically, "Do It Yourself" is almost always the wrong answer.
   * Low Level: I have to manually handle IVs, nonce reuse, and key rotation logic. One
     typo destroys security.
   * High Level (AWS SDK): It forces the "Envelope" standard, prevents nonce reuse, and
     handles the dangerous parts automatically.
   * Correction: I should have started with the high-level library because it fails safe.

  ### 2. Thoughts on Low-Level vs. High-Level

  High-Level (Preferred for Security):
   * Examples: aws-encryption-sdk, Tink (Google), Libsodium.
   * Why: They abstract away the "foot-guns." They force you to use modern algorithms
     (AES-GCM) and handle the "boring" but critical stuff like message framing and
     padding.
   * Use when: Protecting data, handling auth, storing secrets.

  Low-Level (Use with Caution):
   * Examples: cryptography.hazmat, OpenSSL.
   * Why: You need a specific, non-standard protocol (e.g., "Decrypt this legacy bitstream
     from a 1990s mainframe"), or you are building a high-level library yourself.
   * Use when: You have absolutely no choice.

  3. How to convey your preferences to me?

  You have a few powerful options:

   1. The "Persona" Prompt:
       * "Act as a Senior Security Engineer who prefers established frameworks over custom
         code."
       * "Act as a Minimalist who hates adding new dependencies."

   2. Explicit Constraints:
       * "I prefer using high-level AWS libraries where possible."
       * "Don't reinvent the wheel; if there's a standard library, use it."

   3. The "Save Memory" Tool (Permanent):
       * You can literally tell me right now: "Save this memory: I prefer high-level,
         opinionated libraries (like AWS SDKs) over low-level implementations to ensure
         best practices."
       * I will store this in my long-term memory, and in future sessions, I will check
         this preference before suggesting a solution.
