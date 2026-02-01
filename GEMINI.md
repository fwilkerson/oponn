# Oponn Agent Guide (Revised)

This document provides critical architectural context for Gemini agents to maintain and evolve Oponn in a distributed environment.

## 1. Architectural Philosophy: Distributed SIUI
Oponn follows a **Distributed Server-Informed UI** pattern. The server is the source of truth for data and navigation, and Redis ensures consistency across multiple worker processes.

- **FastAPI + HTMX**: Server-side rendering with partial DOM swaps.
- **Shared State**: All persistent data resides in **Postgres**. All real-time signals reside in **Redis**.
- **Multi-Worker Ready**: Designed to run under Gunicorn with multiple workers. Local memory is strictly for transient caches or cleanup tracking.

## 2. Core Technical Constraints

### Async-First Execution & Loop Locality
Oponn is an **async-native** application. To avoid `RuntimeError: Task attached to a different loop` and database connection corruption:

- **Strict Async Preference**: All database-touching and network-bound code MUST be `async def`.
- **Loop-Aware Singletons**: Infrastructure dependencies (Database Engine, Redis, Repositories) MUST NOT be initialized at the module level. They must be lazily initialized and cached per event loop (using `asyncio.get_running_loop()`) via factory functions in `src/dependencies.py`.
- **Thread Delegation (The "Pure Work" Rule)**: Use `anyio.to_thread.run_sync` only for CPU-bound or blocking synchronous libraries. NEVER pass async-bound objects (Sessions, Redis clients, Services) to a thread. Pass only primitive data types (strings, dicts, ints) and return the same.

### Concurrency & Consistency
- **Distributed Locking**: `BallotService` uses **Redis-backed distributed locks** (`self.redis.lock`) during the `record_vote` process. This ensures that the "Check-then-Act" sequence (validation -> persistence -> broadcast) is linear across the entire cluster.
- **Graceful Fallback**: In `development` or `testing` modes, the service falls back to a local `asyncio.Lock` if Redis is missing.

### SSE & Pub/Sub
- **Redis Pub/Sub**: Live updates are broadcast to Redis channels (`ballot:{id}:updates`).
- **Anyio Task Groups**: The SSE route (`src/routes/sse.py`) uses `anyio.create_task_group` to run a background listener that bridges Redis broadcasts to the client's local SSE stream.

## 4. Development Tooling (`manage.py` & `Makefile`)
The project uses `manage.py` as the primary CLI and `Makefile` as a shortcut for common workflows.

- `make dev`: Launches the development server with hot-reload.
- `make services-up`: Launches Postgres 16 and Redis 7 via Docker Compose.
- `make migrate`: Applies Alembic migrations (alias for `python manage.py db upgrade`).
- `make test`: Executes the full suite with `pytest`.
- `make simulate`: Runs a high-concurrency voting simulation to verify distributed locks and SSE.
- `make prod`: Runs the app via **Gunicorn** with multiple workers.

## 5. Testing Strategy
- **Functional Simulation**: Tests in `tests/test_e2e.py` simulate HTMX requests and verify SSE streams.
- **Isolation**: The `reset_service` fixture ensures a clean state between tests.
- **Environment Agnostic**: Tests default to `InMemoryBallotRepository` for speed but should be verified against `SqlBallotRepository` periodically.

## 6. Critical Operational Notes
- **YAGNI**: Do not add new infrastructure unless it solves a distributed scaling problem.
- **Serialization**: When broadcasting via Redis, always use `model_dump()` on Pydantic models to ensure JSON compatibility.

## 7. UI Design Patterns: Nordic Terminal
Oponn uses a **Nordic Terminal** aesthetic, combining the Nord color palette with a minimalist Command Line Interface (CLI) feel.

### Aesthetic Principles
- **Typography**: Strict use of monospace fonts (`JetBrains Mono`, `Fira Code`).
- **Shapes**: Sharp edges (2px max radius) and square status indicators.
- **Atmosphere**: Subtle scanline overlays and path-style breadcrumbs (`~/oponn/`).

### Color Semantics
- **White (`--text-primary`)**: Root Shell context (`~/oponn/`) and primary data.
- **Blue (`--accent-secondary`)**: **Context & Navigation**. Used for Page Titles, Nav Links, and "View" buttons (e.g., `results`, `return_to_voting`).
- **Purple (`--accent-tertiary`)**: **Commands & Actions**. Used for buttons that change state (e.g., `init_ballot`, `cast_vote`) and the prompt character (`>`).
- **Teal (`--accent-primary`)**: **Data & Selection**. Used for Progress Bars, Radio Inputs, List Highlights, and Status Indicators.
- **Green (`--success`)**: Reserved strictly for success alerts/confirmations (NOT for data visualization).

### Component Standards
- **Progress Bars**: Must use a "segmented" or "blocky" fill pattern (`linear-gradient(90deg, ...)`) to mimic terminal output.
- **Terminology**: Prefer technical, concise terms. Use **`init`** instead of `create` or `initialize`.
- **Interactivity**: Every primary action button MUST include an HTMX indicator (`...`) to provide immediate processing feedback.
- **Borders**: Prefer `border-left` accents for alerts and list items over full boxes when possible.

