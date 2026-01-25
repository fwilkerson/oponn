# Persistence Layer Implementation Plan

## Phase 1: Infrastructure & Dependencies
- [x] Add persistence dependencies: `poetry add sqlalchemy alembic asyncpg`
- [x] Add test dependencies: `poetry add --group dev testcontainers[postgres]`
- [x] Initialize Alembic: `alembic init alembic`
- [x] Configure `alembic/env.py` to support async drivers and read the connection string from environment variables.

## Phase 2: Database Schema & Migrations
- [x] Define SQLAlchemy models in `src/repositories/models.py`.
- [x] Create initial migration script using temporary Postgres container.
- [x] Verify migration generation.

## Phase 3: SQL Repository Implementation
- [x] Implement `SqlBallotRepository(BallotRepository)` in `src/repositories/sql_repository.py`.
- [x] Implement connection pooling and async session management in `src/database.py`.

## Phase 4: Dependency Injection & Configuration
- [x] Update `src/dependencies.py` to support dynamic repository selection.
- [x] Refactor `BallotService` to use shared class-level state for SSE queues and locks to support request-scoped instances.
- [x] Ensure backward compatibility for in-memory tests.

## Phase 5: Testing with Testcontainers
- [x] Create `tests/test_sql_repo.py` using `testcontainers`.
- [x] Verify `SqlBallotRepository` against a real PostgreSQL instance.
- [x] Re-run existing tests to ensure no regressions in in-memory mode.

## Runtime Differences & Considerations
- **Durability:** Data persists across application restarts when `DATABASE_URL` is set.
- **Concurrency:** `BallotService` continues to use `asyncio.Lock` for SSE ordering; SQL repository handles data consistency.
- **Environment:** `DATABASE_URL` enables SQL mode; its absence defaults to in-memory mode.
- **Testing:** Integration tests use `testcontainers` for PostgreSQL; unit/e2e tests default to in-memory for speed but can be run against SQL by setting `DATABASE_URL`.