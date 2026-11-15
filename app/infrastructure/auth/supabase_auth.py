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


def _provider_error_text(exc: Exception) -> str:
    """Best-effort extract of GoTrue / httpx error fields for mapping."""
    fragments: list[str] = []
    for attr in (
        "message",
        "msg",
        "error_description",
        "error",
        "error_code",
        "code",
    ):
        raw = getattr(exc, attr, None)
        if raw is not None:
            text = str(raw).strip()
            if text:
                fragments.append(text)
    status = getattr(exc, "status", None)
    if status is not None:
        fragments.append(f"status:{status}")
    for attr in ("json", "body"):
        raw = getattr(exc, attr, None)
        if isinstance(raw, dict):
            for key in ("msg", "message", "error_code", "error"):
                val = raw.get(key)
                if val is not None:
                    text = str(val).strip()
                    if text and text not in fragments:
                        fragments.append(text)
    base = str(exc).strip()
    if base and base not in fragments:
        fragments.append(base)
    return " ".join(fragments) if fragments else "Authentication failed"


def _map_auth_error(exc: Exception) -> AuthenticationError:
    composite = _provider_error_text(exc)
    lowered = composite.lower()
    code = "authentication_failed"
    details: dict[str, object] = {"source": "supabase"}
    status = getattr(exc, "status", None)

    if (
        status == 429
        or "rate limit" in lowered
        or "over_email_send_rate_limit" in lowered
        or "too many requests" in lowered
    ):
        code = "auth_rate_limited"
    elif (
        "error sending confirmation email" in lowered
        or "error sending magic link" in lowered
        or "error sending recovery email" in lowered
        or (
            "unexpected_failure" in lowered
            and ("confirmation email" in lowered or "sending" in lowered)
        )
    ):
        # GoTrue returns 500 (sometimes surfaced/logged as 422) when SMTP cannot
        # deliver — not invalid credentials.
        code = "auth_email_delivery_failed"
        logger.error(
            "supabase_auth_email_delivery_failed",
            provider_message=composite[:500],
            provider_status=status,
        )
    elif (
        (status is not None and int(status) >= 500)
        or "internal server error" in lowered
        or "status:500" in lowered
        or (status == 422 and "unexpected_failure" in lowered)
    ):
        # Supabase Auth 5xx / unexpected 422 — not a bad password.
        code = "auth_provider_error"
        logger.error(
            "supabase_auth_provider_5xx",
            provider_message=composite[:500],
            provider_status=status,
        )
    elif "invalid login" in lowered or "invalid credentials" in lowered:
        code = "invalid_credentials"
    elif (
        "already registered" in lowered
        or "user already" in lowered
        or "email_exists" in lowered
        or "email address is already" in lowered
    ):
        code = "email_already_registered"
    elif "email not confirmed" in lowered or "email_not_confirmed" in lowered:
        code = "email_not_verified"
    elif (
        ("signup" in lowered or "sign up" in lowered)
        and ("not allowed" in lowered or "disabled" in lowered)
    ) or "signups not allowed" in lowered:
        code = "signup_disabled"
    elif any(
        phrase in lowered
        for phrase in (
            "weak password",
            "password is too weak",
            "password strength",
            "password should be",
        )
    ):
        code = "weak_password"
    elif (
        "oauth" in lowered and ("disabled" in lowered or "not enabled" in lowered)
    ) or "provider is disabled" in lowered:
        code = "oauth_provider_unavailable"
    elif "identity" in lowered and "mismatch" in lowered:
        code = "identity_mismatch"
    elif "redirect" in lowered and "oauth" in lowered:
        code = "oauth_redirect_failed"

    if code == "authentication_failed":
        logger.warning(
            "supabase_auth_error_unmapped",
            error_type=type(exc).__name__,
            provider_message=composite[:500],
            mapped_code=code,
        )

    public_message = composite if composite else "Authentication failed"
    return AuthenticationError(public_message, code=code, details=details)


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
                options: dict[str, Any] = {
                    "data": {
                        "display_name": display_name,
                        "full_name": display_name,
                    }
                }
                redirect = (self._supabase.settings.auth_redirect_url or "").strip()
                if redirect:
                    options["email_redirect_to"] = redirect
                response = self._client().auth.sign_up(
                    {
                        "email": email,
                        "password": password,
                        "options": options,
                    }
                )
                # Some GoTrue failures surface as empty user + error attrs
                # instead of a raised exception.
                err_obj = getattr(response, "error", None)
                if err_obj is not None:
                    mapped = (
                        err_obj
                        if isinstance(err_obj, Exception)
                        else Exception(str(err_obj))
                    )
                    raise _map_auth_error(mapped)
                # Anti-enumeration: existing emails return 200 with empty
                # identities instead of email_exists.
                user_obj = getattr(response, "user", None)
                identities = getattr(user_obj, "identities", None) if user_obj else None
                if user_obj is not None and not identities:
                    raise AuthenticationError(
                        "An account with this email already exists",
                        code="email_already_registered",
                        details={"source": "supabase", "signal": "empty_identities"},
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

    async def verify_email_otp(
        self,
        *,
        email: str,
        token: str,
        type: str = "email",
    ) -> AuthSession:
        def _call() -> AuthSession:
            try:
                response = self._client().auth.verify_otp(
                    {
                        "email": email.strip().lower(),
                        "token": token.strip(),
                        "type": type,
                    }
                )
                return _session_from_response(response)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def resend_signup_email(self, *, email: str) -> None:
        def _call() -> None:
            try:
                self._client().auth.resend(
                    {
                        "type": "signup",
                        "email": email.strip().lower(),
                    }
                )
            except Exception as exc:
                # Anti-enumeration: never reveal whether the email exists.
                logger.warning(
                    "supabase_signup_resend_failed",
                    error_type=type(exc).__name__,
                )

        await asyncio.to_thread(_call)

    def _bind_session(self, access_token: str) -> None:
        # Refresh token is required by set_session; reuse access when unknown.
        self._client().auth.set_session(access_token, access_token)

    async def list_mfa_factors(self, *, access_token: str) -> list[dict[str, object]]:
        def _call() -> list[dict[str, object]]:
            try:
                self._bind_session(access_token)
                response = self._client().auth.mfa.list_factors()
                data = getattr(response, "data", response) or {}
                totp = list(getattr(data, "totp", None) or data.get("totp", []) or [])
                phone = list(
                    getattr(data, "phone", None) or data.get("phone", []) or []
                )
                out: list[dict[str, object]] = []
                for factor in [*totp, *phone]:
                    if isinstance(factor, dict):
                        out.append(factor)
                    else:
                        out.append(
                            {
                                "id": str(getattr(factor, "id", "")),
                                "friendly_name": str(
                                    getattr(factor, "friendly_name", "") or ""
                                ),
                                "factor_type": str(
                                    getattr(factor, "factor_type", "") or ""
                                ),
                                "status": str(getattr(factor, "status", "") or ""),
                            }
                        )
                return out
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def enroll_totp(
        self, *, access_token: str, friendly_name: str = "Authenticator"
    ) -> dict[str, object]:
        def _call() -> dict[str, object]:
            try:
                self._bind_session(access_token)
                response = self._client().auth.mfa.enroll(
                    {
                        "factor_type": "totp",
                        "friendly_name": friendly_name,
                    }
                )
                data = getattr(response, "data", response)
                totp = getattr(data, "totp", None) or (
                    data.get("totp") if isinstance(data, dict) else None
                )
                factor_id = str(
                    getattr(data, "id", None)
                    or (data.get("id") if isinstance(data, dict) else "")
                    or ""
                )
                qr = ""
                secret = ""
                uri = ""
                if totp is not None:
                    if isinstance(totp, dict):
                        qr = str(totp.get("qr_code") or "")
                        secret = str(totp.get("secret") or "")
                        uri = str(totp.get("uri") or "")
                    else:
                        qr = str(getattr(totp, "qr_code", "") or "")
                        secret = str(getattr(totp, "secret", "") or "")
                        uri = str(getattr(totp, "uri", "") or "")
                return {
                    "factor_id": factor_id,
                    "qr_code": qr,
                    "secret": secret,
                    "uri": uri,
                    "friendly_name": friendly_name,
                }
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def challenge_mfa(
        self, *, access_token: str, factor_id: str
    ) -> dict[str, object]:
        def _call() -> dict[str, object]:
            try:
                self._bind_session(access_token)
                response = self._client().auth.mfa.challenge({"factor_id": factor_id})
                data = getattr(response, "data", response)
                challenge_id = str(
                    getattr(data, "id", None)
                    or (data.get("id") if isinstance(data, dict) else "")
                    or ""
                )
                if not challenge_id:
                    raise AuthenticationError(
                        "MFA challenge could not be created",
                        code="mfa_challenge_failed",
                    )
                return {"challenge_id": challenge_id, "factor_id": factor_id}
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def verify_mfa(
        self,
        *,
        access_token: str,
        factor_id: str,
        challenge_id: str,
        code: str,
    ) -> AuthSession:
        def _call() -> AuthSession:
            try:
                self._bind_session(access_token)
                response = self._client().auth.mfa.verify(
                    {
                        "factor_id": factor_id,
                        "challenge_id": challenge_id,
                        "code": code.strip(),
                    }
                )
                # Prefer refreshed session when GoTrue returns one.
                try:
                    refreshed = self._client().auth.get_session()
                    if refreshed is not None and getattr(
                        refreshed, "access_token", None
                    ):
                        return _session_from_response(refreshed)
                except Exception:
                    logger.debug(
                        "mfa_verify_get_session_fallback",
                        exc_info=True,
                    )
                return _session_from_response(response, allow_empty_session=False)
            except AuthenticationError:
                raise
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        return await asyncio.to_thread(_call)

    async def unenroll_mfa(self, *, access_token: str, factor_id: str) -> None:
        def _call() -> None:
            try:
                self._bind_session(access_token)
                self._client().auth.mfa.unenroll({"factor_id": factor_id})
            except Exception as exc:
                raise _map_auth_error(exc) from exc

        await asyncio.to_thread(_call)

    async def get_authenticator_assurance_level(
        self, *, access_token: str
    ) -> dict[str, object]:
        def _call() -> dict[str, object]:
            try:
                self._bind_session(access_token)
                response = self._client().auth.mfa.get_authenticator_assurance_level()
                data = getattr(response, "data", response) or {}
                if isinstance(data, dict):
                    return {
                        "current_level": data.get("current_level"),
                        "next_level": data.get("next_level"),
                        "current_authentication_methods": data.get(
                            "current_authentication_methods"
                        ),
                    }
                return {
                    "current_level": getattr(data, "current_level", None),
                    "next_level": getattr(data, "next_level", None),
                    "current_authentication_methods": getattr(
                        data, "current_authentication_methods", None
                    ),
                }
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
