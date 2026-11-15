"""Application service facade for authentication endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.auth import (
    AuthSessionDTO,
    AuthUserDTO,
    ChangePasswordCommand,
    LoginCommand,
    LogoutCommand,
    MessageDTO,
    OAuthCallbackCommand,
    OAuthStartCommand,
    OAuthUrlDTO,
    RefreshSessionCommand,
    RegisterEmailCommand,
    RequestPasswordResetCommand,
    ResendVerificationCommand,
    VerifyEmailCommand,
)
from app.application.use_cases.auth import (
    ChangePasswordUseCase,
    CompleteOAuthUseCase,
    GetCurrentUserUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
    RegisterWithEmailUseCase,
    RequestPasswordResetUseCase,
    ResendVerificationUseCase,
    StartOAuthUseCase,
    VerifyEmailUseCase,
)
from app.application.use_cases.auth.mfa import (
    MfaChallengeUseCase,
    MfaEnrollUseCase,
    MfaRecoveryConsumeUseCase,
    MfaRecoveryGenerateUseCase,
    MfaStatusUseCase,
    MfaUnenrollUseCase,
    MfaVerifyUseCase,
)


@dataclass(frozen=True, slots=True)
class AuthService:
    """Presentation-facing orchestrator for identity use cases."""

    register_email: RegisterWithEmailUseCase
    login: LoginUseCase
    logout: LogoutUseCase
    refresh: RefreshSessionUseCase
    verify_email: VerifyEmailUseCase
    resend_verification: ResendVerificationUseCase
    request_password_reset: RequestPasswordResetUseCase
    change_password: ChangePasswordUseCase
    start_oauth: StartOAuthUseCase
    complete_oauth: CompleteOAuthUseCase
    get_current_user: GetCurrentUserUseCase
    mfa_status: MfaStatusUseCase
    mfa_enroll: MfaEnrollUseCase
    mfa_challenge: MfaChallengeUseCase
    mfa_verify: MfaVerifyUseCase
    mfa_unenroll: MfaUnenrollUseCase
    mfa_recovery_generate: MfaRecoveryGenerateUseCase
    mfa_recovery_consume: MfaRecoveryConsumeUseCase

    async def register(
        self, command: RegisterEmailCommand
    ) -> AuthSessionDTO | MessageDTO:
        return await self.register_email.execute(command)

    async def sign_in(self, command: LoginCommand) -> AuthSessionDTO:
        return await self.login.execute(command)

    async def sign_out(self, command: LogoutCommand) -> MessageDTO:
        return await self.logout.execute(command)

    async def refresh_session(self, command: RefreshSessionCommand) -> AuthSessionDTO:
        return await self.refresh.execute(command)

    async def confirm_email(self, command: VerifyEmailCommand) -> AuthSessionDTO:
        return await self.verify_email.execute(command)

    async def resend_email(self, command: ResendVerificationCommand) -> MessageDTO:
        return await self.resend_verification.execute(command)

    async def forgot_password(self, command: RequestPasswordResetCommand) -> MessageDTO:
        return await self.request_password_reset.execute(command)

    async def update_password(self, command: ChangePasswordCommand) -> MessageDTO:
        return await self.change_password.execute(command)

    async def oauth_url(self, command: OAuthStartCommand) -> OAuthUrlDTO:
        return await self.start_oauth.execute(command)

    async def oauth_callback(self, command: OAuthCallbackCommand) -> AuthSessionDTO:
        return await self.complete_oauth.execute(command)

    async def me(self, *, access_token: str) -> AuthUserDTO:
        return await self.get_current_user.execute(access_token=access_token)

    async def get_mfa_status(self, *, access_token: str) -> dict[str, object]:
        return await self.mfa_status.execute(access_token=access_token)

    async def enroll_mfa(
        self, *, access_token: str, actor_user_id: UUID | None
    ) -> dict[str, object]:
        return await self.mfa_enroll.execute(
            access_token=access_token, actor_user_id=actor_user_id
        )

    async def challenge_mfa(
        self, *, access_token: str, factor_id: str
    ) -> dict[str, object]:
        return await self.mfa_challenge.execute(
            access_token=access_token, factor_id=factor_id
        )

    async def verify_mfa(
        self,
        *,
        access_token: str,
        factor_id: str,
        challenge_id: str,
        code: str,
        actor_user_id: UUID | None,
        issue_recovery_codes: bool = False,
    ) -> AuthSessionDTO | dict[str, object]:
        return await self.mfa_verify.execute(
            access_token=access_token,
            factor_id=factor_id,
            challenge_id=challenge_id,
            code=code,
            actor_user_id=actor_user_id,
            issue_recovery_codes=issue_recovery_codes,
        )

    async def unenroll_mfa(
        self, *, access_token: str, factor_id: str, actor_user_id: UUID | None
    ) -> MessageDTO:
        return await self.mfa_unenroll.execute(
            access_token=access_token,
            factor_id=factor_id,
            actor_user_id=actor_user_id,
        )

    async def generate_mfa_recovery(self, *, user_id: UUID) -> dict[str, object]:
        return await self.mfa_recovery_generate.execute(user_id=user_id)

    async def consume_mfa_recovery(
        self, *, access_token: str, code: str, actor_user_id: UUID
    ) -> AuthSessionDTO:
        return await self.mfa_recovery_consume.execute(
            access_token=access_token, code=code, actor_user_id=actor_user_id
        )
