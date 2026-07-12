"""Authentication and authorization FastAPI dependencies."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.application.dto.auth import AuthUserDTO
from app.application.services.auth_service import AuthService
from app.application.use_cases.auth import (
    ChangePasswordUseCase,
    CompleteOAuthUseCase,
    GetCurrentUserUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterWithEmailUseCase,
    RequestPasswordResetUseCase,
    StartOAuthUseCase,
    VerifyEmailUseCase,
)
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.user import UserRole
from app.domain.exceptions.auth import AuthenticationError, AuthorizationError
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory
from app.infrastructure.auth.supabase_auth import SupabaseAuthAdapter
from core.config.settings import Settings, get_settings
from core.di.container import get_container

_bearer = HTTPBearer(auto_error=False)


def get_client_meta(request: Request) -> tuple[str, str]:
    """Return ``(ip_address, user_agent)`` for audit logging."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        ip = forwarded.split(",", 1)[0].strip()
    else:
        ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    return ip, user_agent


def get_access_token(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    """Resolve Bearer token from middleware state or Authorization header."""
    token = getattr(request.state, "access_token", None)
    if isinstance(token, str) and token:
        return token
    if credentials is not None and credentials.credentials:
        return credentials.credentials
    raise AuthenticationError(
        "Missing bearer access token",
        code="missing_token",
    )


def get_uow_factory() -> UnitOfWorkFactory:
    container = get_container()
    factory = container.uow_factory
    if factory is None:
        msg = "Unit of Work factory is not available (Supabase not configured)"
        raise RuntimeError(msg)
    return factory  # type: ignore[no-any-return]


def get_auth_provider() -> SupabaseAuthAdapter:
    container = get_container()
    return SupabaseAuthAdapter(container.require_supabase())


def get_auth_service(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthService:
    auth = get_auth_provider()
    uow_factory = get_uow_factory()
    audit = RecordAuditEventUseCase(uow_factory=uow_factory)
    redirect = settings.auth_redirect_url
    return AuthService(
        register_email=RegisterWithEmailUseCase(
            auth=auth, uow_factory=uow_factory, audit=audit
        ),
        login=LoginUseCase(auth=auth, uow_factory=uow_factory, audit=audit),
        logout=LogoutUseCase(auth=auth, audit=audit),
        refresh=RefreshSessionUseCase(auth=auth, uow_factory=uow_factory),
        verify_email=VerifyEmailUseCase(
            auth=auth, uow_factory=uow_factory, audit=audit
        ),
        request_password_reset=RequestPasswordResetUseCase(
            auth=auth, audit=audit, default_redirect_to=redirect
        ),
        change_password=ChangePasswordUseCase(auth=auth, audit=audit),
        start_oauth=StartOAuthUseCase(auth=auth, default_redirect_to=redirect),
        complete_oauth=CompleteOAuthUseCase(
            auth=auth,
            uow_factory=uow_factory,
            audit=audit,
            default_redirect_to=redirect,
        ),
        get_current_user=GetCurrentUserUseCase(auth=auth, uow_factory=uow_factory),
    )


async def get_current_user(
    access_token: Annotated[str, Depends(get_access_token)],
    auth_service: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthUserDTO:
    user = await auth_service.me(access_token=access_token)
    return user


def require_roles(
    *roles: UserRole,
) -> Callable[..., Coroutine[Any, Any, AuthUserDTO]]:
    """Dependency factory enforcing role-based authorization."""

    async def _dependency(
        user: Annotated[AuthUserDTO, Depends(get_current_user)],
    ) -> AuthUserDTO:
        allowed = {role.value for role in roles}
        if user.role not in allowed:
            raise AuthorizationError(
                "Insufficient role for this operation",
                code="insufficient_role",
                details={"required_roles": sorted(allowed), "actual_role": user.role},
            )
        return user

    return _dependency


CurrentUser = Annotated[AuthUserDTO, Depends(get_current_user)]
AccessToken = Annotated[str, Depends(get_access_token)]


def actor_id(user: AuthUserDTO | None) -> UUID | None:
    return user.id if user is not None else None
