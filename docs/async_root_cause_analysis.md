# Asyncio Root Cause Analysis: The "Loop Locality" Trap

## Overview
During the early development of Oponn, we encountered significant stability issues (e.g., `RuntimeError: Task attached to a different loop` and SQLAlchemy `InterfaceError`). This document outlines the staff-level root cause analysis and the structural patterns required to prevent regression.

## 1. The Core Issue: Implicit Loop Binding
In Python, many `asyncio` primitives (Locks, Queues, Connection Pools) are **implicitly bound** to the event loop that was active at the moment of their instantiation.

### The Testing Conflict
*   **Production:** Uvicorn starts a single event loop that lives for the duration of the process. Module-level globals (singletons) work fine here.
*   **Testing:** `pytest-asyncio` creates a **fresh event loop for every test** to ensure isolation.
*   **The Crash:** If a service or database engine is initialized at the module level, it binds to the loop of *Test A*. When *Test B* runs in a new loop, it tries to use the object from *Test A*. `asyncio` detects this cross-loop access and raises a `RuntimeError`.

## 2. The FastAPI Sync/Async Bridge
FastAPI allows mixing `def` and `async def` routes. 
*   `async def`: Runs on the main event loop.
*   `def`: Runs in a separate threadpool to avoid blocking the loop.

**Root Cause of DB Failures:** If a threadpool worker (from a `def` route) attempts to access a SQLAlchemy `AsyncSession` or its underlying `asyncpg` connection, the driver throws an error. These drivers are strictly bound to the thread and loop that created them.

## 3. The "Quickstart" Documentation Debt
Most library documentation (SQLAlchemy, Redis-py) suggests global initialization (`engine = create_async_engine(...)`) to keep examples simple. This pattern is a "trap" for professional-grade applications that require robust test suites.

## 4. Remediation Patterns (The Oponn Standard)

### A. Lazy, Loop-Aware Initialization
Never instantiate async objects at the top level. Use factory functions that cache instances per event loop.

```python
_cache = {}

async def get_service():
    loop = asyncio.get_running_loop()
    if loop not in _cache:
        _cache[loop] = Service()
    return _cache[loop]
```

### B. Strict Async-Only Path for DB Access
To avoid threading issues, all database-touching dependencies and routes should be `async def`. This ensures they always execute on the main event loop where the connection pool resides.

### C. Dependency Injection over Singletons
Pass dependencies (Session, Redis, Crypto) through function arguments rather than importing global instances. This allows tests to easily swap or reset state.