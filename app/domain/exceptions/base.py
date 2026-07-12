"""Base domain exception types.

These exceptions carry structured metadata (``code``, ``details``) so that
presentation-layer error handlers can produce consistent API error bodies
without inspecting exception message strings.
"""

from __future__ import annotations

from typing import Any


class DomainError(Exception):
    """Root of the domain exception hierarchy.

    Parameters
    ----------
    message:
        Human-readable description of the failure.
    code:
        Machine-readable error code for API clients.
    details:
        Optional structured context about the failure.
    """

    def __init__(
        self,
        message: str,
        *,
        code: str = "domain_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.details: dict[str, Any] = details or {}


class NotFoundError(DomainError):
    """Raised when a requested domain entity does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        *,
        code: str = "not_found",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class ValidationError(DomainError):
    """Raised when a domain invariant or input constraint is violated."""

    def __init__(
        self,
        message: str = "Validation failed",
        *,
        code: str = "validation_error",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class ConflictError(DomainError):
    """Raised when an operation conflicts with the current domain state."""

    def __init__(
        self,
        message: str = "Conflict with current state",
        *,
        code: str = "conflict",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
