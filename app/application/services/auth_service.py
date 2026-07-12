"""Application service facade for authentication endpoints."""

from __future__ import annotations

from dataclasses import dataclass

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
    StartOAuthUseCase,
    VerifyEmailUseCase,
)


@dataclass(frozen=True, slots=True)
class AuthService:
    """Presentation-facing orchestrator for identity use cases."""

    register_email: RegisterWithEmailUseCase
    login: LoginUseCase
    logout: LogoutUseCase
    refresh: RefreshSessionUseCase
    verify_email: VerifyEmailUseCase
    request_password_reset: RequestPasswordResetUseCase
    change_password: ChangePasswordUseCase
    start_oauth: StartOAuthUseCase
    complete_oauth: CompleteOAuthUseCase
    get_current_user: GetCurrentUserUseCase

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
