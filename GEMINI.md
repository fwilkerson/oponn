# Oponn Agent Guide

This document provides critical context for Gemini agents to maintain and evolve Oponn effectively.

## 1. Architectural Philosophy: Server-Informed UI (SIUI)

Oponn follows a **Server-Informed UI** pattern. The server is the source of truth for both data and navigation state.

- **FastAPI + HTMX**: Avoid heavy client-side state. Use HTMX for partial DOM swaps (`HX-Target`) and server-side redirects (`HX-Redirect`).
- **Async-First**: The entire stack—from `BallotRepository` to `BallotService`—is fully `async`.
- **SSE for Live Updates**: Live results are pushed via Server-Sent Events. The client (`static/js/app.js`) handles reconnection and DOM updates based on SSE triggers.

## 2. Core Technical Constraints

### Concurrency & Consistency
- **Per-Ballot Locking**: `BallotService` uses an `asyncio.Lock` per `ballot_id` during the `record_vote` process. This ensures that SSE broadcast order matches the persistence order and prevents race conditions in the in-memory tallies.
- **Singleton Service**: The app uses a global singleton for `BallotService` to ensure background SSE threads and request threads share the same state.

### Type Safety
- **basedpyright**: We use strict type checking. Ensure all new code passes `make typecheck`. Avoid `Any` where possible.
- **Pydantic Models**: Use models in `src/models/` for data validation and API schemas.

## 3. Testing Strategy: Functional Simulation

**Do NOT use Playwright or Docker/Testcontainers.** To remain environment-agnostic and fast, we use a "Functional Simulation" approach.

- **Httpx + BeautifulSoup**: Tests in `tests/test_e2e.py` simulate HTMX requests by setting headers like `HX-Request: true` and parsing the resulting HTML fragments.
- **SSE Verification**: SSE streams are tested by monitoring the `httpx` stream and accumulating multi-line `data:` blocks until an empty line is reached. This correctly handles the `sse-starlette` framing.
- **Test Isolation**: A global `reset_service` fixture in `conftest.py` clears the singleton repository before every test.

## 4. Development Tooling

The primary entry point is `dev.py`, built with **Typer**. The `Makefile` acts as a thin wrapper for compatibility.

- `make start` / `./dev.py start`: Runs the uvicorn dev server.
- `make test` / `./dev.py test`: Runs the test suite.
- `./dev.py test -k <pattern>`: Runs specific tests (a key feature for agents).
- `make lint` / `make format`: Ruff-based quality gates.
- `make typecheck`: Strict basedpyright check.

## 5. UI & Styling Conventions

- **Theme**: "Deep Charcoal" and "Gemini Purple" terminal aesthetic.
- **CSS**: Variables are defined in `static/css/style.css`. Always use these variables instead of hardcoded hex codes to maintain the theme.
- **Partials**: HTML fragments intended for HTMX swaps reside in `templates/partials/`.

## 6. Critical Operational Notes for Agents

- **CSRF**: CSRF is bypassed in test environments via the `OPONN_SKIP_CSRF` environment variable. Ensure this is respected in `conftest.py`.
- **YAGNI**: Do not add dependencies (like Redis or Postgres) unless explicitly requested. The current `InMemoryBallotRepository` is intentional for the prototype stage.
- **SSE Cleanup**: When implementing new SSE features, always ensure that client disconnects (detected via `anyio.get_cancelled_stack_group`) trigger proper queue unregistration in the service.