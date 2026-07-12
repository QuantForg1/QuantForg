"""Authentication provider port — Supabase Auth (or test double).

Identity credentials live with the external identity provider. QuantForg
persists only application profile state in ``public.users`` (linked by
``auth_user_id``). Domain and application layers depend solely on this port.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from uuid import UUID


class OAuthProvider(StrEnum):
    """Supported OAuth identity providers (configured in Supabase)."""

    GOOGLE = "google"
    GITHUB = "github"


@dataclass(frozen=True, slots=True)
class AuthUserIdentity:
    """Identity snapshot from the external auth provider."""

    id: UUID
    email: str
    email_confirmed: bool
    display_name: str = ""
    providers: tuple[str, ...] = ()
    metadata: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class AuthSession:
    """Session tokens issued by the identity provider."""

    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str = "bearer"  # noqa: S105
    user: AuthUserIdentity | None = None


@dataclass(frozen=True, slots=True)
class OAuthRedirect:
    """Browser redirect target for an OAuth authorization flow."""

    provider: OAuthProvider
    url: str


class AuthProviderPort(Protocol):
    """Port for Supabase Auth (or equivalent) operations."""

    async def sign_up(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
    ) -> AuthSession:
        """Register with email/password. May return a session or require verify."""
        ...

    async def sign_in(self, *, email: str, password: str) -> AuthSession:
        """Authenticate with email/password."""
        ...

    async def sign_out(self, *, access_token: str) -> None:
        """Invalidate the current provider session."""
        ...

    async def refresh_session(self, *, refresh_token: str) -> AuthSession:
        """Exchange a refresh token for a new session."""
        ...

    async def get_user(self, *, access_token: str) -> AuthUserIdentity:
        """Validate an access token and return the identity."""
        ...

    async def verify_email(
        self,
        *,
        token_hash: str,
        type: str = "email",
    ) -> AuthSession:
        """Confirm an email address using a verification token hash."""
        ...

    async def request_password_reset(self, *, email: str, redirect_to: str) -> None:
        """Send a password-reset email (always succeeds from caller's view)."""
        ...

    async def update_password(
        self,
        *,
        access_token: str,
        new_password: str,
    ) -> AuthUserIdentity:
        """Change password for the authenticated user."""
        ...

    async def get_oauth_redirect(
        self,
        *,
        provider: OAuthProvider,
        redirect_to: str,
    ) -> OAuthRedirect:
        """Build the OAuth authorization URL for Google/GitHub."""
        ...

    async def exchange_oauth_code(
        self,
        *,
        code: str,
        redirect_to: str | None = None,
    ) -> AuthSession:
        """Exchange an OAuth authorization code for a session."""
        ...
