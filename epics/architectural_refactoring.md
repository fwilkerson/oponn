# Epic: Architectural Evolution & Refactoring

This document outlines the high-level strategies for evolving Oponn from a functional prototype into a highly scalable, decoupled distributed system.

---

## 1. Advanced Dependency Injection (DI)
**Current State:** `dependencies.py` uses hardcoded `if/else` logic to choose between in-memory and SQL repositories.
**The Goal:** Decouple the "how" of object creation from the "where" it is used, making the application logic agnostic to the environment.

### Code Snippet: The Factory Pattern
```python
# src/repositories/factory.py
from typing import Annotated
from fastapi import Depends
from .ballot_repository import BallotRepository, InMemoryBallotRepository
from .sql_ballot_repository import SqlBallotRepository
from ..config import settings
from ..dependencies import get_db

async def get_ballot_repository(
    session: Annotated[AsyncSession | None, Depends(get_db)]
) -> BallotRepository:
    """A single source of truth for repository selection."""
    if settings.is_in_memory:
        return await get_singleton_in_memory_repo()
    return SqlBallotRepository(session)
```

**Research Topics:**
- [FastAPI Dependency Injection](https://fastapi.tiangolo.com/tutorial/dependencies/)
- [The Dependency Injection Container Pattern (Punq)](https://github.com/allisson/punq)

---

## 2. Formalizing Protocols (Structural Typing)
**Current State:** Repositories use Abstract Base Classes (ABCs).
**The Goal:** Use `typing.Protocol` to define interfaces by *behavior* rather than *inheritance*. This simplifies mocking and allows for "Duck Typing" with type safety.

### Code Snippet: Repository Protocols
```python
from typing import Protocol, runtime_checkable

@runtime_checkable
class BallotRepository(Protocol):
    """Defines the contract for any Ballot Storage engine."""
    async def get_by_id(self, ballot_id: str) -> BallotTable | None: ...
    async def list_all(self) -> list[BallotTable]: ...
    async def add_vote(self, ballot_id: str, option_id: int) -> None: ...
```

**Research Topics:**
- [Python Type Hints: Protocols (PEP 544)](https://peps.python.org/pep-0544/)
- [Structural vs. Nominal Typing](https://docs.python.org/3/library/typing.html#typing.Protocol)

---

## 3. The Event Bus Abstraction (SSE Scaling)
**Current State:** `BallotService` publishes directly to Redis.
**The Goal:** Isolate the "Distribution Logic" from the "Business Logic." The Service should just "emit" an event, and a dedicated Bus handles the delivery (Redis, RabbitMQ, or local memory).

### Code Snippet: Event Bus Interface
```python
class EventBus(Protocol):
    async def publish(self, topic: str, data: dict): ...
    async def subscribe(self, topic: str): ...

class RedisEventBus:
    def __init__(self, redis_client): self.redis = redis_client
    async def publish(self, topic, data):
        await self.redis.publish(topic, json.dumps(data))
```

**Research Topics:**
- [The Pub/Sub Pattern](https://aws.amazon.com/pub-sub-messaging/)
- [Redis Streams for Event Sourcing](https://redis.io/docs/data-types/streams/)

---

## 4. Frontend Componentization (Jinja Macros)
**Current State:** Raw HTML partials.
**The Goal:** Treat UI elements as reusable components with their own logic and styling, preventing template duplication.

### Code Snippet: Jinja Component Macro
```html
{# templates/components/progress_bar.html #}
{% macro progress_bar(label, percentage, color_var='--accent-primary') %}
<div class="terminal-progress">
    <span>{{ label }}</span>
    <div class="bar-bg">
        <div class="bar-fill" style="width: {{ percentage }}%; background: var({{ color_var }});"></div>
    </div>
</div>
{% endmacro %}
```

**Research Topics:**
- [Jinja2 Macros](https://jinja.palletsprojects.com/en/3.1.x/templates/#macros)
- [Jinja-Partials Library](https://github.com/mikeckennedy/jinja_partials)

---

## 5. Background Task Management
**Current State:** Cleanup logic runs inside the main process loop.
**The Goal:** Offload heavy or periodic work (like clearing stale locks or generating PDF reports) to dedicated worker processes.

### Code Snippet: Taskiq (Modern Async Worker)
```python
import taskiq_redis

broker = taskiq_redis.ListQueueBroker("redis://localhost:6379")

@broker.task
async def cleanup_ballot_metadata(ballot_id: str):
    """Runs in a separate worker process."""
    # ... heavy cleanup logic ...
```

**Research Topics:**
- [Taskiq: Distributed Task Queue](https://taskiq-python.github.io/)
- [ARQ: Redis-based Task Queue](https://github.com/samuelcolvin/arq)
