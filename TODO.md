# Oponn Project Improvements

## 1. Separation of Concerns (Priority: High)
- [x] Implement Repository Pattern to decouple `BallotService` from in-memory storage.
- [x] Remove `HTTPException` from `BallotService` and use domain-specific exceptions.
- [x] Use FastAPI's Dependency Injection (`Depends`) for `BallotService`.

## 2. Project Structure (Priority: High)
- [x] Split `main.py` into modular routes (e.g., `src/routes/ui.py`, `src/routes/sse.py`).
- [x] Remove redundant `src/oponn/` directory.

## 3. Security & Validation (Priority: Medium)
- [x] Implement CSRF protection for HTML forms.
- [x] Add length constraints and sanitization for ballot measures and options.
- [x] Implement write-in value sanitization.

## 4. Concurrency & Reliability (Priority: Medium)
- [x] Add thread-safety (locks) to in-memory data structures.
- [x] Improve error handling UX by re-rendering forms with inline error messages using HTMX.

## 5. Testing (Priority: Medium)
- [ ] Add unit tests for lower-level logic (e.g., `format_time_delta`).
- [ ] Implement SSE stream tests.
- [ ] Mock `BallotService` in UI integration tests.

## 6. Maintenance (Priority: Low)
- [ ] Move embedded JavaScript from templates to a structured `static/js/app.js`.
