"""Supabase Auth adapter implementing AuthProviderPort."""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from supabase_auth.helpers import decode_jwt
from supabase_auth.types import Session as GoTrueSession

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


def _factor_to_dict(factor: Any) -> dict[str, object]:
    if isinstance(factor, dict):
        return {
            "id": str(factor.get("id") or ""),
            "friendly_name": str(factor.get("friendly_name") or ""),
            "factor_type": str(factor.get("factor_type") or ""),
            "status": str(factor.get("status") or ""),
        }
    return {
        "id": str(getattr(factor, "id", "") or ""),
        "friendly_name": str(getattr(factor, "friendly_name", "") or ""),
        "factor_type": str(getattr(factor, "factor_type", "") or ""),
        "status": str(getattr(factor, "status", "") or ""),
    }


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
    elif any(
        phrase in lowered
        for phrase in (
            "invalid totp",
            "invalid mfa",
            "invalid code",
            "challenge has expired",
            "mfa challenge",
            "totp code",
            "verification failed",
            "invalid credentials for mfa",
        )
    ):
        code = "invalid_mfa_code"
    elif "session" in lowered and (
        "missing" in lowered or "not found" in lowered or "auth session" in lowered
    ):
        code = "invalid_token"

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

    def _bind_session(
        self, access_token: str, refresh_token: str | None = None
    ) -> None:
        """Bind a user JWT onto the shared GoTrue client without refresh races.

        ``set_session(access, access)`` is unsafe: near-expiry or shared-client
        ``get_session`` may treat the access JWT as a refresh token and fail.
        Bind via ``get_user(jwt)`` + ``_save_session`` instead.
        """
        auth = self._client().auth
        user_response = auth.get_user(access_token)
        user = getattr(user_response, "user", None)
        if user is None:
            raise AuthenticationError(
                "Invalid or expired access token",
                code="invalid_token",
            )
        payload = decode_jwt(access_token)["payload"]
        expires_at = int(payload.get("exp") or 0)
        time_now = int(time.time())
        # Prefer a real refresh token when the caller has one. Fall back to the
        # access token only as a non-empty placeholder; expires_at stays future
        # so get_session will not attempt refresh during this request.
        refresh = (refresh_token or "").strip() or access_token
        bearer_type = "bearer"
        session = GoTrueSession(
            access_token=access_token,
            refresh_token=refresh,
            user=user,
            token_type=bearer_type,
            expires_in=max(expires_at - time_now, 0),
            expires_at=expires_at if expires_at > 0 else time_now + 3600,
        )
        # Intentional: bind JWT onto shared GoTrue client for MFA network calls.
        auth._save_session(session)

    async def list_mfa_factors(self, *, access_token: str) -> list[dict[str, object]]:
        def _call() -> list[dict[str, object]]:
            try:
                # JWT-direct: avoid shared-session list_factors() cache races.
                response = self._client().auth.get_user(access_token)
                user = getattr(response, "user", None)
                factors = list(getattr(user, "factors", None) or []) if user else []
                return [_factor_to_dict(f) for f in factors]
            except AuthenticationError:
                raise
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
                # AuthMFAVerifyResponse carries tokens directly (no .session).
                access = str(getattr(response, "access_token", "") or "")
                if access:
                    identity = None
                    user = getattr(response, "user", None)
                    if user is not None:
                        identity = _identity_from_user(user)
                    return AuthSession(
                        access_token=access,
                        refresh_token=str(getattr(response, "refresh_token", "") or ""),
                        expires_in=int(getattr(response, "expires_in", 0) or 0),
                        token_type=str(
                            getattr(response, "token_type", "bearer") or "bearer"
                        ),
                        user=identity,
                    )
                refreshed = self._client().auth.get_session()
                if refreshed is not None and getattr(refreshed, "access_token", None):
                    return _session_from_response(refreshed)
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
                payload = decode_jwt(access_token)["payload"]
                current_level = payload.get("aal")
                amr = payload.get("amr") or []
                methods: list[dict[str, object]] = []
                if isinstance(amr, list):
                    for entry in amr:
                        if isinstance(entry, dict):
                            methods.append(
                                {
                                    "method": str(entry.get("method") or ""),
                                    "timestamp": entry.get("timestamp"),
                                }
                            )
                        else:
                            methods.append(
                                {
                                    "method": str(getattr(entry, "method", "") or ""),
                                    "timestamp": getattr(entry, "timestamp", None),
                                }
                            )
                # next_level is aal2 when a verified factor exists on the user.
                user_response = self._client().auth.get_user(access_token)
                user = getattr(user_response, "user", None)
                factors = list(getattr(user, "factors", None) or []) if user else []
                has_verified = any(
                    str(getattr(f, "status", "") or "").lower() == "verified"
                    for f in factors
                )
                next_level = "aal2" if has_verified else current_level
                return {
                    "current_level": current_level,
                    "next_level": next_level,
                    "current_authentication_methods": methods,
                }
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
                self._bind_session(access_token)
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
