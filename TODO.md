# Oponn Refactor & Cleanup TODO

## 1. Backend & Architecture Cleanup
- [x] **Consolidate DB Dependencies**: Merge `get_db` from `database.py` and `get_db_session` from `dependencies.py`. Standardize on a single way to handle optional/required DB sessions.
- [x] **Refactor Error Rendering**: Extract the repeated `render_error` logic in `src/routes/ui.py` into a shared helper or utility to keep routes DRY.
- [x] **Clean up Models**: Remove the unused `ValidationErrorDetail` in `src/models/ballot_models.py`.
- [x] **Refactor `VoteForm.to_vote`**: Move the `BeautifulSoup` import to the top of the file or extract sanitization to a dedicated utility.

## 2. Frontend & UI Polish
- [ ] **Style Consolidation**: Move hardcoded styles from templates (e.g., in `index.html` and `results.html`) into `static/css/style.css`.
- [ ] **JS Validation**: Review `static/js/app.js` to ensure it doesn't conflict with HTMX's built-in validation or server-side error messages.
- [ ] **Standardize Partials**: Ensure naming consistency in `templates/partials/` (e.g., `start-time-input` vs `start_time_input`).

## 3. Code Quality & Standards
- [ ] **Naming Consistency**: Ensure all "status" related logic uses consistent terminology (e.g., `pending`, `active`, `ended`).
- [ ] **SSE State Management**: Consider moving `_sse_queues` and `_locks` from class attributes in `BallotService` to a dedicated State manager or ensuring the singleton pattern is more explicit.

## 4. Tooling & Maintenance
- [ ] **Update `GEMINI.md`**: Ensure the architectural philosophy section reflects any changes made during this refactor.
- [ ] **Check for Shadowing**: Ensure variables like `_` in routes are used consistently for unused dependencies.