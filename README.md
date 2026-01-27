# Oponn Voting Service

Oponn is a high-performance, real-time voting service built with **FastAPI**, **HTMX**, and **Server-Sent Events (SSE)**. It follows the **Server-Informed UI (SIUI)** pattern, providing a terminal-inspired "Deep Charcoal" and "Gemini Purple" aesthetic.

## Architecture

Oponn is designed for horizontal scalability. It uses a distributed synchronization layer to ensure live results reach all users instantly, regardless of which server instance they are connected to.

```text
    ┌───────────┐             ┌───────────┐
    │ Browser A │             │ Browser B │
    └─────┬─────┘             └─────┬─────┘
          │ (SSE)                   │ (SSE)
          ▼                         ▼
  ┌────────────────┐       ┌────────────────┐
  │ Gunicorn Wkr 1 │       │ Gunicorn Wkr 2 │
  └───────┬────────┘       └────────▲───────┘
          │                         │
   1. Cast Vote              3. Signal Sync
          │                         │
          ▼                         │
  ┌────────────────┐       ┌────────┴───────┐
  │  Postgres DB   │──────▶│ Redis Pub/Sub  │
  │ (Persistence)  │   2.  │   (Sync Hub)   │
  └────────────────┘       └────────────────┘
```

### Key Components
- **FastAPI**: Handles the ASGI web requests and SSE streaming.
- **HTMX**: Powers dynamic DOM updates without client-side frameworks.
- **Redis**: Manages distributed locking and real-time event broadcasting.
- **Postgres**: Ensures durable persistence of ballots and vote counts.
- **Lifespan Reaper**: A background task that prunes stale in-memory metadata.

## Getting Started

### Prerequisites
- Python 3.12+
- [Poetry](https://python-poetry.org/)
- Docker Desktop (for Postgres/Redis)

### 1. Installation
```bash
poetry install
```

### 2. Infrastructure
```bash
make services-up   # Start Postgres 16 & Redis 7
make upgrade       # Apply migrations
```

### 3. Running the Application
- **`make dev`**: Single worker with hot-reload (Standard Dev).
- **`make prod`**: Multi-worker Gunicorn (Production Simulation).

## Development Commands

| Command | Description |
|---------|-------------|
| `make test` | Run the full test suite (In-Memory) |
| `make test-sql` | Run tests against a Postgres container |
| `make format-ui` | Reformat all HTML/CSS/JS files |
| `make lint` | Run Python linting (Ruff) |
| `make typecheck` | Run strict type checking (Basedpyright) |

---
*Built with simplicity and horizontal scale in mind.*
