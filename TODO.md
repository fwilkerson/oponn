# Oponn Project Status

## 1. Async Refactoring (Complete)
- [x] Refactor `BallotRepository` interface and `InMemoryBallotRepository` implementation to be `async`.
- [x] Update `BallotService` and routes to `await` all repository calls.
- [x] Ensure `BallotService.record_vote` uses an `asyncio.Lock` per ballot to guarantee SSE update ordering.

## 2. Testing Overhaul (Complete)
- [x] Implement robust functional simulation tests using `httpx` and `BeautifulSoup` to verify HTMX behavior.
- [x] Implement SSE stream monitoring tests with multi-line message accumulation.
- [x] Add high-concurrency stress tests to verify thread-safety and data consistency.
- [x] Adhere to YAGNI by removing brittle Docker/Playwright dependencies in favor of functional testing.

## 3. Maintenance & Cleanup (Complete)
- [x] Move embedded JavaScript to a structured `static/js/app.js`.
- [x] Remove legacy `app.state.ballot_service`.
- [x] Add docstrings to core service and repository methods.
- [x] Flexible CSRF skip logic for static and SSE routes.
- [x] Passed all linting and type-checking standards (`make typecheck`).