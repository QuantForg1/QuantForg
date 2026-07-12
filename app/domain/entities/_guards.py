"""Shared invariant helpers for rich domain entities."""

from __future__ import annotations

from typing import Any, NoReturn

from app.domain.exceptions.base import ConflictError, ValidationError


def require(condition: bool, message: str, **details: Any) -> None:
    """Raise :class:`ValidationError` when ``condition`` is False."""
    if not condition:
        raise ValidationError(message, details=details or None)


def require_state(
    condition: bool,
    message: str,
    **details: Any,
) -> None:
    """Raise :class:`ConflictError` when a state transition is illegal."""
    if not condition:
        raise ConflictError(message, details=details or None)


def unreachable(message: str = "Unreachable domain state") -> NoReturn:
    """Mark a branch that must never execute if invariants hold."""
    raise ConflictError(message)
