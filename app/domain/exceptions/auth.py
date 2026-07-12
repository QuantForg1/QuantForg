"""Authentication and authorization domain exceptions."""

from __future__ import annotations

from typing import Any

from app.domain.exceptions.base import DomainError


class AuthenticationError(DomainError):
    """Raised when credentials or session tokens are invalid."""

    def __init__(
        self,
        message: str = "Authentication failed",
        *,
        code: str = "authentication_failed",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)


class AuthorizationError(DomainError):
    """Raised when an authenticated principal lacks required privileges."""

    def __init__(
        self,
        message: str = "Forbidden",
        *,
        code: str = "forbidden",
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, details=details)
