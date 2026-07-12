"""Logging configuration and helpers.

Call :func:`configure_logging` once during application startup.
Thereafter use :func:`get_logger` to obtain bound loggers.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from core.config.settings import Settings


def configure_logging(settings: Settings) -> None:
    """Configure stdlib logging and structlog for the process lifetime.

    Parameters
    ----------
    settings:
        Application settings controlling level and output format.
    """
    log_level = getattr(logging, settings.log_level)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
    ]

    use_json = settings.log_json or settings.log_format == "json"

    if use_json:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=settings.is_development)

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
        foreign_pre_chain=shared_processors,
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_level)

    # Quiet noisy third-party loggers in production.
    for noisy in ("uvicorn.access", "sqlalchemy.engine"):
        logging.getLogger(noisy).setLevel(
            logging.WARNING if not settings.debug else logging.DEBUG
        )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger.

    Parameters
    ----------
    name:
        Optional logger name. Defaults to the calling module when omitted
        by relying on structlog's stdlib integration.
    """
    return structlog.get_logger(name)  # type: ignore[no-any-return]


def bind_context(**kwargs: Any) -> None:
    """Bind key-value pairs into the structlog contextvars for the current task.

    Bound values appear on every subsequent log record until cleared.
    Typical use: request_id, correlation_id, user_id.
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_context() -> None:
    """Clear all structlog contextvars for the current task."""
    structlog.contextvars.clear_contextvars()
