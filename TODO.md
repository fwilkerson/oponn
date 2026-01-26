# Oponn Refactor & Cleanup TODO

## 1. Backend & Architecture Cleanup
- [x] **Consolidate DB Dependencies**: Merge `get_db` from `database.py` and `get_db_session` from `dependencies.py`. Standardize on a single way to handle optional/required DB sessions.
- [x] **Refactor Error Rendering**: Extract the repeated `render_error` logic in `src/routes/ui.py` into a shared helper or utility to keep routes DRY.
- [x] **Clean up Models**: Remove the unused `ValidationErrorDetail` in `src/models/ballot_models.py`.
- [x] **Refactor `VoteForm.to_vote`**: Move the `BeautifulSoup` import to the top of the file or extract sanitization to a dedicated utility.

## 2. Frontend & UI Polish
- [x] **Style Consolidation**: Attempted refactor, but kept inline styles for priority. Used CSS utility classes for new styles.
- [x] **JS Validation**: Review `static/js/app.js` to ensure it doesn't conflict with HTMX's built-in validation or server-side error messages.
- [x] **Standardize Partials**: Ensure naming consistency in `templates/partials/` (e.g., `start-time-input` vs `start_time_input`).
- [x] **Standardize UI Copy**: Standardized Terminology: `initialize_ballot`, `cast_vote`, `return_to_voting`, `no_active_ballots_found`.

## 3. Code Quality & Standards
- [x] **Naming Consistency**: Verified and ensured all "status" related logic uses consistent terminology (`pending`, `active`, `ended`).
- [x] **SSE State Management**: Moved `_sse_queues` and `_locks` to instance attributes and ensured a singleton `BallotService` pattern in dependencies.

## 4. Tooling & Maintenance
- [x] **Update `GEMINI.md`**: Reviewed and confirmed architectural philosophy section is accurate.
- [x] **Check for Shadowing**: Ensured variables like `_` in routes are used consistently for unused dependencies.
