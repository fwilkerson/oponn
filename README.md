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

## Security & Key Management

Oponn uses **Envelope Encryption** to protect sensitive data. Every ballot is encrypted with its own unique Data Encryption Key (DEK), which is itself encrypted by a Master Key (KEK) managed by a **Key Management Service (KMS)**.

### Development (LocalStack)
For local development, Oponn uses **LocalStack** to provide a mock AWS KMS environment. 
- Running `make services-up` automatically initializes a KMS key in LocalStack.
- The CLI will output the `OPONN_KMS_KEY_ID` which should be added to your `.env` file.

### Production (AWS KMS)
In production, Oponn requires a real AWS KMS Key ID:
```bash
# .env
OPONN_KMS_KEY_ID="alias/oponn-master-key"
AWS_REGION="us-east-1"
```

## Development Commands

| Command | Description |
|---------|-------------|
| `make test` | Run the full test suite (Uses Testcontainers for DB/Redis/KMS) |
| `make infra-up` | Start Postgres, Redis, and LocalStack |
| `make lint` | Run Python linting (Ruff) |
| `make check` | Full QA suite: Lint, Typecheck, and Test |

---
*Built with simplicity and horizontal scale in mind.*
