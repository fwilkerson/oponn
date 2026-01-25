# Oponn

Oponn is a modern, lightweight voting service designed with a **Server-Informed UI (SIUI)** architecture. It leverages **FastAPI** for the backend and **HTMX** for seamless, declarative frontend interactivity, all styled with a signature "Gemini-inspired" terminal aesthetic.

## Project Overview

-   **Backend:** FastAPI (Python 3.14+)
-   **Frontend:** Jinja2 Templates + HTMX (Server-Sent Events for live updates)
-   **Styling:** Custom CSS with a "Deep Charcoal" and "Gemini Purple" theme.
-   **Real-time Features:** Live vote results pushed via Server-Sent Events (SSE).
-   **Architecture:** SIUI (Server-Informed UI) where the server manages state and navigation, and HTMX handles partial page updates and "boosted" links.

## Building and Running

### Prerequisites
-   Python 3.12+
-   Poetry (Dependency management)

### Setup
```bash
# Install dependencies
poetry install
```

### Running the Application
```bash
# Start the development server
make run
# OR
poetry run fastapi dev src/main.py
```

### Testing
```bash
# Run all tests
make test
# OR
poetry run pytest
```

### Development Workflow
```bash
# Linting
make lint

# Formatting
make format

# Typechecking
make typecheck
```

### Simulating Votes
To see live results in action, use the provided simulation tool:
```bash
poetry run python tools/simulate_votes.py <ballot_id> <num_votes>
```

## Development Conventions

-   **Architecture:** Prefer server-side logic and template rendering. Use HTMX for any "dynamic" requirements like form submissions and live updates.
-   **Styling:** Follow the established CSS variables in `static/css/style.css` for consistent branding.
-   **Models:** Use Pydantic models (`src/models/ballot_models.py`) for all data transfer between the service and API layers.
-   **Testing:** New features should include corresponding tests in `tests/`. Use `TestClient` for integration testing of SIUI routes.
-   **Type Safety:** The project uses `basedpyright`. Ensure new code passes `make typecheck`.
