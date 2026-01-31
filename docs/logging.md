# Logging Guidelines

This document outlines the logging strategy for Oponn, including when and why to use specific log levels.

## Log Levels

### DEBUG
- **When:** Verbose details useful only during development or deep troubleshooting.
- **Why:** To track high-volume technical events that would clutter logs in normal operation.
- **Example:** `sse.redis_subscribe` events or internal repository queries.

### INFO
- **When:** Significant milestones or successful business operations.
- **Why:** To provide a "heartbeat" of the system's health and activity.
- **Example:** `vote.recorded`, `ballot.created`, `lifecycle.startup`.

### WARNING
- **When:** Handled errors, invalid client input, or unusual but non-fatal conditions.
- **Why:** To identify potential abuse, client-side bugs, or environmental issues that don't stop the service.
- **Example:** `http.bad_request` (invalid form submission), `http.not_found`.

### ERROR
- **When:** Unhandled exceptions or failures that prevent a request/task from completing.
- **Why:** To signal critical issues that require developer attention or indicate a service outage.
- **Example:** `vote.failed` (database down), `background_reaper.error`.

## Structured Logging
Oponn uses `structlog` for structured logging.
- **Development:** Outputs pretty-printed, colored text for human readability.
- **Production:** Outputs JSON for machine parsing (Datadog, ELK, etc.).

## Contextual Data
Always prefer adding data as key-value pairs rather than embedding them in the message string.
- **Good:** `logger.info("vote.recorded", ballot_id=id, option=opt)`
- **Bad:** `logger.info(f"Vote recorded for ballot {id} with option {opt}")`
