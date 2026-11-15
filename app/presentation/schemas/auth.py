"""HTTP request/response schemas for authentication."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

from app.domain.interfaces.auth import OAuthProvider


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=120)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1)


class VerifyEmailRequest(BaseModel):
    token_hash: str | None = Field(default=None, min_length=1, max_length=512)
    email: EmailStr | None = None
    token: str | None = Field(default=None, min_length=6, max_length=6)
    type: str = Field(default="email", min_length=1, max_length=32)

    @field_validator("token")
    @classmethod
    def _otp_digits(cls, value: str | None) -> str | None:
        if value is None:
            return value
        if not value.isdigit() or len(value) != 6:
            raise ValueError("Verification code must be exactly six digits")
        return value

    @model_validator(mode="after")
    def _require_otp_or_hash(self) -> VerifyEmailRequest:
        if self.token and self.email:
            return self
        if self.token_hash:
            return self
        raise ValueError("Provide email with a six-digit code, or a legacy token hash")


class ResendVerificationRequest(BaseModel):
    email: EmailStr


class MfaChallengeRequest(BaseModel):
    factor_id: str = Field(min_length=1, max_length=128)


class MfaVerifyRequest(BaseModel):
    factor_id: str = Field(min_length=1, max_length=128)
    challenge_id: str | None = Field(default=None, max_length=128)
    code: str = Field(min_length=6, max_length=6)
    issue_recovery_codes: bool = False

    @field_validator("code")
    @classmethod
    def _code_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("Authenticator code must be six digits")
        return value


class MfaUnenrollRequest(BaseModel):
    factor_id: str = Field(min_length=1, max_length=128)


class MfaRecoveryConsumeRequest(BaseModel):
    code: str = Field(min_length=8, max_length=32)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr
    redirect_to: str | None = None


class ChangePasswordRequest(BaseModel):
    new_password: str = Field(min_length=8, max_length=128)


class OAuthCallbackRequest(BaseModel):
    code: str = Field(min_length=1)
    redirect_to: str | None = None


class AuthUserResponse(BaseModel):
    id: UUID
    email: str
    display_name: str
    role: str
    status: str
    auth_user_id: UUID | None = None


class AuthSessionResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str
    user: AuthUserResponse
    mfa_required: bool = False
    aal: str | None = None


class MessageResponse(BaseModel):
    message: str


class OAuthUrlResponse(BaseModel):
    provider: str
    url: str

    @field_validator("provider")
    @classmethod
    def _provider_ok(cls, value: str) -> str:
        allowed = {p.value for p in OAuthProvider}
        if value not in allowed:
            msg = f"Unsupported OAuth provider: {value}"
            raise ValueError(msg)
        return value
