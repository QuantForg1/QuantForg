"""Authentication HTTP API (Supabase Auth identity provider)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request, status

from app.application.dto.auth import (
    AuthSessionDTO,
    AuthUserDTO,
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    MessageDTO,
    OAuthCallbackCommand,
    OAuthStartCommand,
    RefreshSessionCommand,
    RegisterEmailCommand,
    RequestPasswordResetCommand,
    VerifyEmailCommand,
)
from app.application.services.auth_service import AuthService
from app.domain.interfaces.auth import OAuthProvider
from app.presentation.dependencies.auth import (
    AccessToken,
    CurrentUser,
    get_auth_service,
    get_client_meta,
)
from app.presentation.schemas.auth import (
    AuthSessionResponse,
    AuthUserResponse,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    OAuthCallbackRequest,
    OAuthUrlResponse,
    RefreshRequest,
    RegisterRequest,
    VerifyEmailRequest,
)

router = APIRouter(prefix="/auth", tags=["authentication"])


def _session_response(dto: AuthSessionDTO) -> AuthSessionResponse:
    return AuthSessionResponse(
        access_token=dto.access_token,
        refresh_token=dto.refresh_token,
        expires_in=dto.expires_in,
        token_type=dto.token_type,
        user=AuthUserResponse(
            id=dto.user.id,
            email=dto.user.email,
            display_name=dto.user.display_name,
            role=dto.user.role,
            status=dto.user.status,
            auth_user_id=dto.user.auth_user_id,
        ),
    )


def _user_response(dto: AuthUserDTO) -> AuthUserResponse:
    return AuthUserResponse(
        id=dto.id,
        email=dto.email,
        display_name=dto.display_name,
        role=dto.role,
        status=dto.status,
        auth_user_id=dto.auth_user_id,
    )


@router.post(
    "/register",
    status_code=status.HTTP_201_CREATED,
    response_model=AuthSessionResponse | MessageResponse,
)
async def register(
    body: RegisterRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse | MessageResponse:
    ip, ua = get_client_meta(request)
    result = await auth.register(
        RegisterEmailCommand(
            email=str(body.email),
            password=body.password,
            display_name=body.display_name,
            ip_address=ip,
            user_agent=ua,
        )
    )
    if isinstance(result, MessageDTO):
        return MessageResponse(message=result.message)
    return _session_response(result)


@router.post("/login", response_model=AuthSessionResponse)
async def login(
    body: LoginRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    ip, ua = get_client_meta(request)
    result = await auth.sign_in(
        LoginCommand(
            email=str(body.email),
            password=body.password,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _session_response(result)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    access_token: AccessToken,
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    ip, ua = get_client_meta(request)
    result = await auth.sign_out(
        LogoutCommand(
            access_token=access_token,
            actor_user_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MessageResponse(message=result.message)


@router.post("/refresh", response_model=AuthSessionResponse)
async def refresh(
    body: RefreshRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    ip, ua = get_client_meta(request)
    result = await auth.refresh_session(
        RefreshSessionCommand(
            refresh_token=body.refresh_token,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _session_response(result)


@router.post("/verify-email", response_model=AuthSessionResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    ip, ua = get_client_meta(request)
    result = await auth.confirm_email(
        VerifyEmailCommand(
            token_hash=body.token_hash,
            type=body.type,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _session_response(result)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    ip, ua = get_client_meta(request)
    result = await auth.forgot_password(
        RequestPasswordResetCommand(
            email=str(body.email),
            redirect_to=body.redirect_to,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MessageResponse(message=result.message)


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    request: Request,
    access_token: AccessToken,
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    ip, ua = get_client_meta(request)
    result = await auth.update_password(
        ChangePasswordCommand(
            access_token=access_token,
            new_password=body.new_password,
            actor_user_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MessageResponse(message=result.message)


@router.get("/oauth/{provider}", response_model=OAuthUrlResponse)
async def oauth_start(
    provider: OAuthProvider,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    redirect_to: str | None = None,
) -> OAuthUrlResponse:
    result = await auth.oauth_url(
        OAuthStartCommand(provider=provider, redirect_to=redirect_to)
    )
    return OAuthUrlResponse(provider=result.provider, url=result.url)


@router.post("/oauth/callback", response_model=AuthSessionResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    ip, ua = get_client_meta(request)
    result = await auth.oauth_callback(
        OAuthCallbackCommand(
            code=body.code,
            redirect_to=body.redirect_to,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _session_response(result)


@router.get("/me", response_model=AuthUserResponse)
async def me(user: CurrentUser) -> AuthUserResponse:
    return _user_response(user)
