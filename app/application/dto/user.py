"""User-related application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.user import User
from app.domain.enums.user import UserRole


@dataclass(frozen=True, slots=True)
class RegisterUserCommand:
    """Input for RegisterUserUseCase."""

    email: str
    display_name: str
    role: UserRole = UserRole.TRADER
    password_hash: str = ""


@dataclass(frozen=True, slots=True)
class UserDTO:
    """User representation returned to the presentation layer."""

    id: UUID
    email: str
    display_name: str
    role: str
    status: str

    @classmethod
    def from_entity(cls, user: User) -> UserDTO:
        return cls(
            id=user.id,
            email=str(user.email),
            display_name=str(user.display_name),
            role=user.role.value,
            status=user.status.value,
        )
