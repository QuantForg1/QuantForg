"""Authentication use cases package."""

from app.application.use_cases.auth.get_current_user import GetCurrentUserUseCase
from app.application.use_cases.auth.login import LoginUseCase
from app.application.use_cases.auth.logout import LogoutUseCase
from app.application.use_cases.auth.mfa import (
    MfaChallengeUseCase,
    MfaEnrollUseCase,
    MfaRecoveryConsumeUseCase,
    MfaRecoveryGenerateUseCase,
    MfaStatusUseCase,
    MfaUnenrollUseCase,
    MfaVerifyUseCase,
)
from app.application.use_cases.auth.oauth import CompleteOAuthUseCase, StartOAuthUseCase
from app.application.use_cases.auth.password import (
    ChangePasswordUseCase,
    RequestPasswordResetUseCase,
)
from app.application.use_cases.auth.refresh_session import RefreshSessionUseCase
from app.application.use_cases.auth.register_email import RegisterWithEmailUseCase
from app.application.use_cases.auth.resend_verification import ResendVerificationUseCase
from app.application.use_cases.auth.verify_email import VerifyEmailUseCase

__all__ = [
    "ChangePasswordUseCase",
    "CompleteOAuthUseCase",
    "GetCurrentUserUseCase",
    "LoginUseCase",
    "LogoutUseCase",
    "MfaChallengeUseCase",
    "MfaEnrollUseCase",
    "MfaRecoveryConsumeUseCase",
    "MfaRecoveryGenerateUseCase",
    "MfaStatusUseCase",
    "MfaUnenrollUseCase",
    "MfaVerifyUseCase",
    "RefreshSessionUseCase",
    "RegisterWithEmailUseCase",
    "RequestPasswordResetUseCase",
    "ResendVerificationUseCase",
    "StartOAuthUseCase",
    "VerifyEmailUseCase",
]
