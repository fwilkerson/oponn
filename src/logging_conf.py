import logging
import sys

import structlog

from .config import ProductionSettings, settings


def configure_logging():
    """
    Configures structlog to output JSON in production/testing
    and pretty-printed text in development.
    """

    log_level = settings.log_level

    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="%H:%M:%S"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if settings.log_format == "json":
        # Production: JSON rendering
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Development: Pretty console rendering
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(),
        ]

    # 1. Configure structlog
    structlog.configure(
        processors=processors,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # 2. Configure standard library logging (to capture Uvicorn/FastAPI logs)
    # We redirect stdlib logging to structlog's PrintLoggerFactory or similar
    # but the cleanest way is to use a formatter.

    # However, for simplicity and compatibility with Uvicorn's own loggers,
    # we will just configure the root logger to output to stdout with the basic config,
    # relying on structlog to wrap our app logs.

    # Ideally, we want Uvicorn logs to also be JSON in production.
    # To do that, we would replace the logging handler.
    # For this iteration, we focus on Application logging.

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )
