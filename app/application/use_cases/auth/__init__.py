"""Authentication use cases package."""

from app.application.use_cases.auth.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.auth.login import LoginUseCase
from app.application.use_cases.auth.logout import LogoutUseCase
from app.application.use_cases.auth.oauth import CompleteOAuthUseCase, StartOAuthUseCase
from app.application.use_cases.auth.password import (
    ChangePasswordUseCase,
    RequestPasswordResetUseCase,
)
from app.application.use_cases.auth.refresh_session import RefreshSessionUseCase
from app.application.use_cases.auth.register_email import RegisterWithEmailUseCase
from app.application.use_cases.auth.verify_email import VerifyEmailUseCase

__all__ = [
    "ChangePasswordUseCase",
    "CompleteOAuthUseCase",
    "GetCurrentUserUseCase",
    "LoginUseCase",
    "LogoutUseCase",
    "RefreshSessionUseCase",
    "RegisterWithEmailUseCase",
    "RequestPasswordResetUseCase",
    "StartOAuthUseCase",
    "VerifyEmailUseCase",
]
