"""Authentication application DTOs."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.domain.entities.user import User
from app.domain.enums.user import UserRole
from app.domain.interfaces.auth import AuthSession, OAuthProvider


@dataclass(frozen=True, slots=True)
class AuthUserDTO:
    """Authenticated application profile returned to clients."""

    id: UUID
    email: str
    display_name: str
    role: str
    status: str
    auth_user_id: UUID | None

    @classmethod
    def from_entity(cls, user: User) -> AuthUserDTO:
        return cls(
            id=user.id,
            email=str(user.email),
            display_name=str(user.display_name),
            role=user.role.value,
            status=user.status.value,
            auth_user_id=user.auth_user_id,
        )


@dataclass(frozen=True, slots=True)
class AuthSessionDTO:
    """Session tokens + profile."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user: AuthUserDTO

    @classmethod
    def from_session(cls, session: AuthSession, user: User) -> AuthSessionDTO:
        return cls(
            access_token=session.access_token,
            refresh_token=session.refresh_token,
            expires_in=session.expires_in,
            token_type=session.token_type,
            user=AuthUserDTO.from_entity(user),
        )


@dataclass(frozen=True, slots=True)
class RegisterEmailCommand:
    email: str
    password: str
    display_name: str
    role: UserRole = UserRole.TRADER
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class LoginCommand:
    email: str
    password: str
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class LogoutCommand:
    access_token: str
    actor_user_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class RefreshSessionCommand:
    refresh_token: str
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class VerifyEmailCommand:
    token_hash: str
    type: str = "email"
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class RequestPasswordResetCommand:
    email: str
    redirect_to: str | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class ChangePasswordCommand:
    access_token: str
    new_password: str
    actor_user_id: UUID | None = None
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class OAuthStartCommand:
    provider: OAuthProvider
    redirect_to: str | None = None


@dataclass(frozen=True, slots=True)
class OAuthCallbackCommand:
    code: str
    redirect_to: str | None = None
    ip_address: str = ""
    user_agent: str = ""
    role: UserRole = UserRole.TRADER


@dataclass(frozen=True, slots=True)
class OAuthUrlDTO:
    provider: str
    url: str


@dataclass(frozen=True, slots=True)
class MessageDTO:
    message: str
