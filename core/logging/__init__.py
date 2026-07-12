"""Structured logging for QuantForg.

Uses structlog for consistent, machine-parseable log records across
development (pretty console) and production (JSON) environments.
"""

from core.logging.setup import (
    bind_context,
    clear_context,
    configure_logging,
    get_logger,
)

__all__ = [
    "bind_context",
    "clear_context",
    "configure_logging",
    "get_logger",
]
