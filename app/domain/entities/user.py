"""User aggregate — platform identity and access lifecycle.

Why this entity exists
----------------------
Every action on QuantForg is performed by a User. The aggregate owns
identity (email), role, and lifecycle status. It does not own credentials
storage mechanics — only a password-hash reference string — and contains
no authentication protocol logic.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require, require_state
from app.domain.entities.base import Entity
from app.domain.enums.user import UserRole, UserStatus
from app.domain.value_objects.email import EmailAddress
from app.domain.value_objects.identity import PersonName


@dataclass(eq=False, kw_only=True)
class User(Entity):
    """Rich domain model for a platform user."""

    email: EmailAddress
    display_name: PersonName
    role: UserRole = UserRole.TRADER
    status: UserStatus = UserStatus.PENDING
    password_hash: str = ""
    auth_user_id: UUID | None = None
    last_login_at: datetime | None = None
    deactivated_at: datetime | None = None

    def __post_init__(self) -> None:
        self._validate_invariants()

    def _validate_invariants(self) -> None:
        require(
            isinstance(self.email, EmailAddress),
            "User.email must be an EmailAddress",
        )
        require(
            isinstance(self.display_name, PersonName),
            "User.display_name must be a PersonName",
        )
        require(
            isinstance(self.role, UserRole),
            "User.role must be a UserRole",
        )
        require(
            isinstance(self.status, UserStatus),
            "User.status must be a UserStatus",
        )
        if self.auth_user_id is not None:
            require(
                isinstance(self.auth_user_id, UUID),
                "User.auth_user_id must be a UUID when set",
            )
        if self.status == UserStatus.DEACTIVATED:
            require(
                self.deactivated_at is not None,
                "Deactivated users must record deactivated_at",
            )

    @classmethod
    def create(
        cls,
        *,
        email: str | EmailAddress,
        display_name: str | PersonName,
        role: UserRole = UserRole.TRADER,
        password_hash: str = "",
        entity_id: UUID | None = None,
    ) -> Self:
        """Factory: register a new pending user."""
        email_vo = (
            email if isinstance(email, EmailAddress) else EmailAddress(value=email)
        )
        name_vo = (
            display_name
            if isinstance(display_name, PersonName)
            else PersonName(value=display_name)
        )
        require(
            password_hash == "" or len(password_hash) >= 32,
            "password_hash must be empty or at least 32 characters",
            field="password_hash",
        )
        kwargs: dict[str, object] = {
            "email": email_vo,
            "display_name": name_vo,
            "role": role,
            "status": UserStatus.PENDING,
            "password_hash": password_hash,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def activate(self) -> None:
        """Transition PENDING → ACTIVE."""
        require_state(
            self.status in {UserStatus.PENDING, UserStatus.SUSPENDED},
            "Only pending or suspended users can be activated",
            status=self.status.value,
        )
        self.status = UserStatus.ACTIVE
        self.deactivated_at = None
        self.touch()

    def suspend(self) -> None:
        """Transition ACTIVE → SUSPENDED."""
        require_state(
            self.status == UserStatus.ACTIVE,
            "Only active users can be suspended",
            status=self.status.value,
        )
        self.status = UserStatus.SUSPENDED
        self.touch()

    def deactivate(self) -> None:
        """Permanently deactivate the user."""
        require_state(
            self.status != UserStatus.DEACTIVATED,
            "User is already deactivated",
            status=self.status.value,
        )
        self.status = UserStatus.DEACTIVATED
        self.deactivated_at = datetime.now(UTC)
        self.touch()

    def change_role(self, role: UserRole) -> None:
        """Assign a new role. Forbidden for deactivated users."""
        require_state(
            self.status != UserStatus.DEACTIVATED,
            "Cannot change role of a deactivated user",
            status=self.status.value,
        )
        self.role = role
        self.touch()

    def record_login(self, at: datetime | None = None) -> None:
        """Record a successful login timestamp."""
        require_state(
            self.status == UserStatus.ACTIVE,
            "Only active users can log in",
            status=self.status.value,
        )
        self.last_login_at = at or datetime.now(UTC)
        self.touch()

    def rename(self, display_name: str | PersonName) -> None:
        """Update the display name."""
        self.display_name = (
            display_name
            if isinstance(display_name, PersonName)
            else PersonName(value=display_name)
        )
        self.touch()

    def link_auth_identity(self, auth_user_id: UUID) -> None:
        """Bind this profile to a Supabase Auth ``auth.users`` row."""
        require(
            isinstance(auth_user_id, UUID),
            "auth_user_id must be a UUID",
            field="auth_user_id",
        )
        require_state(
            self.auth_user_id is None or self.auth_user_id == auth_user_id,
            "User is already linked to a different auth identity",
            auth_user_id=str(self.auth_user_id) if self.auth_user_id else None,
        )
        self.auth_user_id = auth_user_id
        self.touch()

    def has_role(self, *roles: UserRole) -> bool:
        """Return True when this user's role is in ``roles``."""
        return self.role in roles

    @property
    def is_active(self) -> bool:
        return self.status == UserStatus.ACTIVE

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "email": str(self.email),
                "display_name": str(self.display_name),
                "role": self.role.value,
                "status": self.status.value,
                "auth_user_id": str(self.auth_user_id) if self.auth_user_id else None,
                "last_login_at": (
                    self.last_login_at.isoformat() if self.last_login_at else None
                ),
                "deactivated_at": (
                    self.deactivated_at.isoformat() if self.deactivated_at else None
                ),
            }
        )
        return base
