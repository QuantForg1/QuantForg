"""HTTP request/response schemas for authentication."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator

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
    token_hash: str = Field(min_length=1)
    type: str = Field(default="email", min_length=1, max_length=32)


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
