"""Domain exception hierarchy.

All domain-level errors inherit from :class:`DomainError`. Presentation
middleware maps these to appropriate HTTP responses.
"""

from app.domain.exceptions.auth import AuthenticationError, AuthorizationError
from app.domain.exceptions.base import (
    ConflictError,
    DomainError,
    NotFoundError,
    ValidationError,
)

__all__ = [
    "AuthenticationError",
    "AuthorizationError",
    "ConflictError",
    "DomainError",
    "NotFoundError",
    "ValidationError",
]
