"""Authentication HTTP API (Supabase Auth identity provider)."""

from __future__ import annotations

from typing import Annotated, Any

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
    ResendVerificationCommand,
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
    MfaChallengeRequest,
    MfaRecoveryConsumeRequest,
    MfaUnenrollRequest,
    MfaVerifyRequest,
    OAuthCallbackRequest,
    OAuthUrlResponse,
    RefreshRequest,
    RegisterRequest,
    ResendVerificationRequest,
    VerifyEmailRequest,
)
from core.config.settings import Settings, get_settings

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
        mfa_required=dto.mfa_required,
        aal=dto.aal,
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
            email=str(body.email) if body.email else None,
            token=body.token,
            type=body.type,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _session_response(result)


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    ip, ua = get_client_meta(request)
    result = await auth.resend_email(
        ResendVerificationCommand(
            email=str(body.email),
            ip_address=ip,
            user_agent=ua,
        )
    )
    return MessageResponse(message=result.message)


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> MessageResponse:
    from app.presentation.security.redirects import sanitize_redirect_to

    ip, ua = get_client_meta(request)
    redirect = sanitize_redirect_to(body.redirect_to, settings=settings)
    result = await auth.forgot_password(
        RequestPasswordResetCommand(
            email=str(body.email),
            redirect_to=redirect,
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
    settings: Annotated[Settings, Depends(get_settings)],
    redirect_to: str | None = None,
) -> OAuthUrlResponse:
    from app.domain.exceptions.base import ValidationError
    from app.presentation.security.redirects import sanitize_redirect_to

    if not settings.auth_oauth_enabled:
        raise ValidationError(
            "Google sign-in is disabled for this deployment. Use email and password.",
            code="oauth_disabled",
        )

    redirect = sanitize_redirect_to(redirect_to, settings=settings)
    result = await auth.oauth_url(
        OAuthStartCommand(provider=provider, redirect_to=redirect)
    )
    return OAuthUrlResponse(provider=result.provider, url=result.url)


@router.post("/oauth/callback", response_model=AuthSessionResponse)
async def oauth_callback(
    body: OAuthCallbackRequest,
    request: Request,
    auth: Annotated[AuthService, Depends(get_auth_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AuthSessionResponse:
    from app.domain.exceptions.base import ValidationError
    from app.presentation.security.redirects import sanitize_redirect_to

    if not settings.auth_oauth_enabled:
        raise ValidationError(
            "Google sign-in is disabled for this deployment. Use email and password.",
            code="oauth_disabled",
        )

    ip, ua = get_client_meta(request)
    redirect = sanitize_redirect_to(body.redirect_to, settings=settings)
    result = await auth.oauth_callback(
        OAuthCallbackCommand(
            code=body.code,
            redirect_to=redirect,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _session_response(result)


@router.get("/me", response_model=AuthUserResponse)
async def me(user: CurrentUser) -> AuthUserResponse:
    return _user_response(user)


@router.get("/mfa/status")
async def mfa_status(
    access_token: AccessToken,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    return await auth.get_mfa_status(access_token=access_token)


@router.post("/mfa/enroll")
async def mfa_enroll(
    access_token: AccessToken,
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    return await auth.enroll_mfa(access_token=access_token, actor_user_id=user.id)


@router.post("/mfa/challenge")
async def mfa_challenge(
    body: MfaChallengeRequest,
    access_token: AccessToken,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    return await auth.challenge_mfa(
        access_token=access_token, factor_id=body.factor_id
    )


@router.post("/mfa/verify")
async def mfa_verify(
    body: MfaVerifyRequest,
    access_token: AccessToken,
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse | dict[str, Any]:
    result = await auth.verify_mfa(
        access_token=access_token,
        factor_id=body.factor_id,
        challenge_id=body.challenge_id or "",
        code=body.code,
        actor_user_id=user.id,
        issue_recovery_codes=body.issue_recovery_codes,
    )
    if isinstance(result, AuthSessionDTO):
        return _session_response(result)
    session = result.get("session")
    codes = result.get("recovery_codes")
    if isinstance(session, AuthSessionDTO):
        return {
            "session": _session_response(session).model_dump(),
            "recovery_codes": codes,
        }
    return result


@router.post("/mfa/unenroll", response_model=MessageResponse)
async def mfa_unenroll(
    body: MfaUnenrollRequest,
    access_token: AccessToken,
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> MessageResponse:
    result = await auth.unenroll_mfa(
        access_token=access_token,
        factor_id=body.factor_id,
        actor_user_id=user.id,
    )
    return MessageResponse(message=result.message)


@router.post("/mfa/recovery/generate")
async def mfa_recovery_generate(
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> dict[str, Any]:
    return await auth.generate_mfa_recovery(user_id=user.id)


@router.post("/mfa/recovery/consume", response_model=AuthSessionResponse)
async def mfa_recovery_consume(
    body: MfaRecoveryConsumeRequest,
    access_token: AccessToken,
    user: CurrentUser,
    auth: Annotated[AuthService, Depends(get_auth_service)],
) -> AuthSessionResponse:
    result = await auth.consume_mfa_recovery(
        access_token=access_token,
        code=body.code,
        actor_user_id=user.id,
    )
    return _session_response(result)
