"""Supabase Auth adapter implementing AuthProviderPort."""

from __future__ import annotations

import asyncio
from typing import Any
from uuid import UUID

from app.domain.exceptions.auth import AuthenticationError
from app.domain.interfaces.auth import (
    AuthSession,
    AuthUserIdentity,
    OAuthProvider,
    OAuthRedirect,
)
from app.infrastructure.supabase.client import SupabaseClient
from core.logging import get_logger

logger = get_logger(__name__)


def _as_uuid(value: str | UUID) -> UUID:
    return value if isinstance(value, UUID) else UUID(str(value))


def _identity_from_user(user: Any) -> AuthUserIdentity:
    meta = getattr(user, "user_metadata", None) or {}
    if not isinstance(meta, dict):
        meta = {}
    app_meta = getattr(user, "app_metadata", None) or {}
    if not isinstance(app_meta, dict):
        app_meta = {}
    providers_raw = app_meta.get("providers") or app_meta.get("provider") or []
    if isinstance(providers_raw, str):
        providers: tuple[str, ...] = (providers_raw,)
    elif isinstance(providers_raw, list):
        providers = tuple(str(p) for p in providers_raw)
    else:
        providers = ()

    display_name = ""
    for key in ("full_name", "name", "display_name", "user_name"):
        candidate = meta.get(key)
        if isinstance(candidate, str) and candidate.strip():
            display_name = candidate.strip()
            break

    email = str(getattr(user, "email", "") or "")
    confirmed_at = getattr(user, "email_confirmed_at", None)
    return AuthUserIdentity(
        id=_as_uuid(user.id),
        email=email,
        email_confirmed=confirmed_at is not None,
        display_name=display_name,
        providers=providers,
        metadata=dict(meta),
    )


def _session_from_response(
    response: Any, *, allow_empty_session: bool = False
) -> AuthSession:
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if session is None and hasattr(response, "access_token"):
        session = response
    if session is None:
        if allow_empty_session and user is not None:
            return AuthSession(
                access_token="",
                refresh_token="",
                expires_in=0,
                token_type="bearer",  # noqa: S106
                user=_identity_from_user(user),
            )
        raise AuthenticationError(
            "Authentication provider returned no session",
            code="auth_provider_error",
        )
    access = str(getattr(session, "access_token", "") or "")
    refresh = str(getattr(session, "refresh_token", "") or "")
    expires_in = int(getattr(session, "expires_in", 0) or 0)
    token_type = str(getattr(session, "token_type", "bearer") or "bearer")
    identity = _identity_from_user(user) if user is not None else None
    return AuthSession(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        token_type=token_type,
        user=identity,
    )


def _map_auth_error(exc: Exception) -> AuthenticationError:
    message = str(exc).strip() or "Authentication failed"
    lowered = message.lower()
    code = "authentication_failed"
    if "invalid login" in lowered or "invalid credentials" in lowered:
        code = "invalid_credentials"
    elif "already registered" in lowered or "user already" in lowered:
        code = "email_already_registered"
    elif "email not confirmed" in lowered:
        code = "email_not_verified"
    return AuthenticationError(message, code=code)


class SupabaseAuthAdapter:
    """AuthProviderPort backed by the official Supabase Python client."""

    def __init__(self, supabase: SupabaseClient) -> None:
        self._supabase = supabase

    def _client(self) -> Any:
        return self._supabase.client

    async def sign_up(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
    ) -> AuthSession:
        def _call() -> AuthSession:
            try:
                response = self._client().auth.sign_up(
                    {
                        "email": email,
                        "password": password,
                        "options": {
                            "data": {
                                "display_name": display_name,
                                "full_name": display_name,
                            }
                        },
                    }
                )
                return _session_from_response(response, allow_empty_session=True)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def sign_in(self, *, email: str, password: str) -> AuthSession:
        def _call() -> AuthSession:
            try:
                response = self._client().auth.sign_in_with_password(
                    {"email": email, "password": password}
                )
                return _session_from_response(response)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def sign_out(self, *, access_token: str) -> None:
        def _call() -> None:
            try:
                base = self._supabase.settings.supabase_url.rstrip("/")
                api_key = self._supabase.settings.supabase_api_key
                assert api_key is not None
                import httpx

                httpx.post(
                    f"{base}/auth/v1/logout",
                    headers={
                        "apikey": api_key,
                        "Authorization": f"Bearer {access_token}",
                    },
                    timeout=10.0,
                )
            except Exception as exc:
                logger.warning("supabase_sign_out_failed", error=str(exc))

        await asyncio.to_thread(_call)

    async def refresh_session(self, *, refresh_token: str) -> AuthSession:
        def _call() -> AuthSession:
            try:
                response = self._client().auth.refresh_session(refresh_token)
                return _session_from_response(response)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def get_user(self, *, access_token: str) -> AuthUserIdentity:
        def _call() -> AuthUserIdentity:
            try:
                response = self._client().auth.get_user(access_token)
                user = getattr(response, "user", response)
                if user is None:
                    raise AuthenticationError(
                        "Invalid or expired access token",
                        code="invalid_token",
                    )
                return _identity_from_user(user)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def verify_email(
        self,
        *,
        token_hash: str,
        type: str = "email",
    ) -> AuthSession:
        def _call() -> AuthSession:
            try:
                response = self._client().auth.verify_otp(
                    {"token_hash": token_hash, "type": type}
                )
                return _session_from_response(response)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def request_password_reset(self, *, email: str, redirect_to: str) -> None:
        def _call() -> None:
            try:
                self._client().auth.reset_password_email(
                    email, options={"redirect_to": redirect_to}
                )
            except Exception as exc:
                # Do not leak whether the email exists.
                logger.warning("supabase_password_reset_request_failed", error=str(exc))

        await asyncio.to_thread(_call)

    async def update_password(
        self,
        *,
        access_token: str,
        new_password: str,
    ) -> AuthUserIdentity:
        def _call() -> AuthUserIdentity:
            try:
                # Bound session for the update_user call.
                self._client().auth.set_session(access_token, access_token)
                response = self._client().auth.update_user({"password": new_password})
                user = getattr(response, "user", None)
                if user is None:
                    raise AuthenticationError(
                        "Password update failed",
                        code="password_update_failed",
                    )
                return _identity_from_user(user)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def get_oauth_redirect(
        self,
        *,
        provider: OAuthProvider,
        redirect_to: str,
    ) -> OAuthRedirect:
        def _call() -> OAuthRedirect:
            try:
                response = self._client().auth.sign_in_with_oauth(
                    {
                        "provider": provider.value,
                        "options": {"redirect_to": redirect_to},
                    }
                )
                url = str(getattr(response, "url", "") or "")
                if not url:
                    raise AuthenticationError(
                        "OAuth provider did not return a redirect URL",
                        code="oauth_redirect_failed",
                    )
                return OAuthRedirect(provider=provider, url=url)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def exchange_oauth_code(
        self,
        *,
        code: str,
        redirect_to: str | None = None,
    ) -> AuthSession:
        def _call() -> AuthSession:
            try:
                options: dict[str, Any] = {}
                if redirect_to:
                    options["redirect_to"] = redirect_to
                response = self._client().auth.exchange_code_for_session(
                    {"auth_code": code, **({"options": options} if options else {})}
                )
                return _session_from_response(response)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)
