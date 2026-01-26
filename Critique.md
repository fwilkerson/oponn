# Codebase Critique: Oponn Voting Service

This document summarizes the architectural evaluation of the Oponn codebase, focusing on the Repository pattern, Server-Sent Events (SSE) implementation, and scalability considerations.

## 1. Repository Pattern Evaluation
The project uses a dual-repository strategy (`InMemoryBallotRepository` and `SqlBallotRepository`).

### Strengths
*   **Testability:** Enables high-speed unit and functional tests without requiring a database container.
*   **Decoupling:** The `BallotService` depends on the `BallotRepository` interface, making the business logic agnostic of the storage backend.

### Concerns & Risks
*   **Transaction Boundary Leakage:** In `SqlBallotRepository`, `commit()` is called within the repository methods (e.g., `add_vote`). In a production system, transactions should ideally be managed at the Service or Dependency level to allow multiple repository calls to be atomic.
*   **Default Behavior Safety:** `dependencies.py` defaults to the In-Memory repository if `DATABASE_URL` is missing. For production, this should fail loudly to prevent accidental data loss in ephemeral containers.
*   **Locking Inconsistency:** The In-Memory repo uses a global `asyncio.Lock`, while the SQL repo relies on DB-level consistency. This can lead to different race-condition behaviors between dev/test and production.

## 2. Server-Sent Events (SSE) & Real-Time Results
The SSE implementation follows the Server-Informed UI (SIUI) pattern but contains a significant bottleneck for horizontal scaling.

### Scalability Bottleneck (Critical)
The `BallotService` manages `_sse_queues` and `_locks` as **in-memory class variables**:
```python
_sse_queues: dict[int, list[asyncio.Queue[list[Tally]]]] = {}
_locks: dict[int, asyncio.Lock] = {}
```
*   **Multi-Worker Failure:** If the app runs with multiple Uvicorn/Gunicorn workers, a vote recorded on **Worker A** will only trigger SSE updates for clients connected to **Worker A**. Clients on **Worker B** will never see the update until they refresh.
*   **Distributed State:** To support horizontal scaling, these queues must be replaced with a distributed Pub/Sub system (e.g., Redis).

### Memory Management
*   **Cleanup:** While `unregister_sse_client` handles queue removal, the `_locks` and `_sse_queues` keys themselves are never purged from the dictionaries. Over time, as thousands of ballots are created, this will result in a slow memory leak.

## 3. General Architecture & Quality
*   **SIUI Adherence:** The use of HTMX for partial swaps and `sse-starlette` for live updates is very clean and follows modern "boring technology" best practices.
*   **Type Safety:** Excellent use of `basedpyright` and Pydantic. The codebase is resilient to common Python type errors.
*   **Frontend:** The "Deep Charcoal" and "Gemini Purple" aesthetic is well-maintained via CSS variables.

## 4. Recommended Next Steps
1.  **Extract Transaction Logic:** Move `commit()` calls out of the `SqlBallotRepository` and into the dependency/service layer or use a context manager for atomic units of work.
2.  **Redis Pub/Sub:** Replace the in-memory `asyncio.Queue` system in `BallotService` with a Redis-backed broadcaster to support multi-process deployments.
3.  **Ballot Lifecycle Management:** Implement a background task to "reap" expired ballots and clean up associated in-memory metadata (locks, etc.).
4.  **Production Hardening:** Update `dependencies.py` to require a database configuration when a `PRODUCTION` flag is set.
