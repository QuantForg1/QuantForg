"""Shared helpers for linking Supabase Auth identities to public.users."""

from __future__ import annotations

from app.domain.entities.user import User
from app.domain.enums.user import UserRole, UserStatus
from app.domain.exceptions.auth import AuthenticationError, AuthorizationError
from app.domain.interfaces.auth import AuthUserIdentity
from app.domain.interfaces.unit_of_work import UnitOfWorkPort
from app.domain.value_objects.email import EmailAddress


async def sync_profile_from_identity(
    uow: UnitOfWorkPort,
    identity: AuthUserIdentity,
    *,
    display_name_fallback: str = "",
    role: UserRole = UserRole.TRADER,
    activate_if_confirmed: bool = True,
) -> User:
    """Upsert ``public.users`` from an Auth identity (no duplicate auth tables)."""
    existing = await uow.users.get_by_auth_user_id(identity.id)
    if existing is None:
        email = EmailAddress(value=identity.email)
        by_email = await uow.users.get_by_email(email)
        if by_email is not None:
            existing = by_email
        else:
            name = identity.display_name.strip() or display_name_fallback.strip()
            if not name:
                name = identity.email.split("@", 1)[0]
            existing = User.create(
                email=email,
                display_name=name,
                role=role,
                password_hash="",
            )
            await uow.users.add(existing)

    if existing.auth_user_id is None:
        existing.link_auth_identity(identity.id)
    elif existing.auth_user_id != identity.id:
        raise AuthenticationError(
            "Profile is linked to a different identity provider account",
            code="identity_mismatch",
        )

    if (
        identity.display_name.strip()
        and str(existing.display_name) != identity.display_name
    ):
        existing.rename(identity.display_name)

    if (
        activate_if_confirmed
        and identity.email_confirmed
        and existing.status == UserStatus.PENDING
    ):
        existing.activate()

    await uow.users.update(existing)
    return existing


def ensure_user_may_authenticate(user: User) -> None:
    """Reject suspended / deactivated profiles even if the IdP session is valid."""
    if user.status == UserStatus.SUSPENDED:
        raise AuthorizationError(
            "Account is suspended",
            code="account_suspended",
            details={"user_id": str(user.id)},
        )
    if user.status == UserStatus.DEACTIVATED:
        raise AuthorizationError(
            "Account is deactivated",
            code="account_deactivated",
            details={"user_id": str(user.id)},
        )
