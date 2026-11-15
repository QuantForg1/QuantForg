"""In-memory AuthProviderPort for unit tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID, uuid4

from app.domain.exceptions.auth import AuthenticationError
from app.domain.interfaces.auth import (
    AuthSession,
    AuthUserIdentity,
    OAuthProvider,
    OAuthRedirect,
)


@dataclass
class FakeAuthProvider:
    """Deterministic auth double used only in unit tests."""

    users: dict[str, dict[str, object]] = field(default_factory=dict)
    tokens: dict[str, str] = field(default_factory=dict)
    refresh_tokens: dict[str, str] = field(default_factory=dict)
    require_email_confirm: bool = False
    fail_next: str | None = None

    def _maybe_fail(self, op: str) -> None:
        if self.fail_next == op:
            self.fail_next = None
            raise AuthenticationError(f"{op} failed", code=f"{op}_failed")

    def _session_for(self, email: str, *, confirmed: bool) -> AuthSession:
        record = self.users[email]
        auth_id = UUID(str(record["id"]))
        access = f"access-{auth_id}"
        refresh = f"refresh-{auth_id}"
        self.tokens[access] = email
        self.refresh_tokens[refresh] = email
        identity = AuthUserIdentity(
            id=auth_id,
            email=email,
            email_confirmed=confirmed,
            display_name=str(record["display_name"]),
            providers=tuple(record.get("providers", ("email",))),  # type: ignore[arg-type]
        )
        return AuthSession(
            access_token=access,
            refresh_token=refresh,
            expires_in=3600,
            user=identity,
        )

    async def sign_up(
        self,
        *,
        email: str,
        password: str,
        display_name: str,
    ) -> AuthSession:
        self._maybe_fail("sign_up")
        key = email.lower()
        if key in self.users:
            raise AuthenticationError(
                "User already registered",
                code="email_already_registered",
            )
        auth_id = uuid4()
        confirmed = not self.require_email_confirm
        self.users[key] = {
            "id": auth_id,
            "password": password,
            "display_name": display_name,
            "confirmed": confirmed,
            "providers": ("email",),
        }
        if self.require_email_confirm:
            identity = AuthUserIdentity(
                id=auth_id,
                email=key,
                email_confirmed=False,
                display_name=display_name,
                providers=("email",),
            )
            return AuthSession(
                access_token="",
                refresh_token="",
                expires_in=0,
                user=identity,
            )
        return self._session_for(key, confirmed=True)

    async def sign_in(self, *, email: str, password: str) -> AuthSession:
        self._maybe_fail("sign_in")
        key = email.lower()
        record = self.users.get(key)
        if record is None or record["password"] != password:
            raise AuthenticationError(
                "Invalid login credentials",
                code="invalid_credentials",
            )
        confirmed = bool(record["confirmed"])
        return self._session_for(key, confirmed=confirmed)

    async def sign_out(self, *, access_token: str) -> None:
        self.tokens.pop(access_token, None)

    async def refresh_session(self, *, refresh_token: str) -> AuthSession:
        self._maybe_fail("refresh")
        email = self.refresh_tokens.get(refresh_token)
        if email is None:
            raise AuthenticationError("Invalid refresh token", code="invalid_token")
        record = self.users[email]
        return self._session_for(email, confirmed=bool(record["confirmed"]))

    async def get_user(self, *, access_token: str) -> AuthUserIdentity:
        email = self.tokens.get(access_token)
        if email is None:
            raise AuthenticationError("Invalid access token", code="invalid_token")
        record = self.users[email]
        return AuthUserIdentity(
            id=UUID(str(record["id"])),
            email=email,
            email_confirmed=bool(record["confirmed"]),
            display_name=str(record["display_name"]),
            providers=tuple(record.get("providers", ("email",))),  # type: ignore[arg-type]
        )

    async def verify_email(
        self,
        *,
        token_hash: str,
        type: str = "email",
    ) -> AuthSession:
        self._maybe_fail("verify_email")
        # token_hash encodes email in tests: "verify:<email>"
        if not token_hash.startswith("verify:"):
            raise AuthenticationError(
                "Invalid verification token",
                code="invalid_token",
            )
        email = token_hash.split(":", 1)[1].lower()
        record = self.users.get(email)
        if record is None:
            raise AuthenticationError("Unknown user", code="invalid_token")
        record["confirmed"] = True
        return self._session_for(email, confirmed=True)

    async def verify_email_otp(
        self,
        *,
        email: str,
        token: str,
        type: str = "email",
    ) -> AuthSession:
        self._maybe_fail("verify_email_otp")
        _ = type
        key = email.lower()
        record = self.users.get(key)
        if record is None or not (token.isdigit() and len(token) == 6):
            raise AuthenticationError("Invalid OTP", code="invalid_otp")
        if token != "123456" and token != str(record.get("otp", "123456")):
            raise AuthenticationError("Invalid OTP", code="invalid_otp")
        record["confirmed"] = True
        return self._session_for(key, confirmed=True)

    async def resend_signup_email(self, *, email: str) -> None:
        self._maybe_fail("resend_signup")
        _ = email

    async def list_mfa_factors(self, *, access_token: str) -> list[dict[str, object]]:
        email = self.tokens.get(access_token)
        if email is None:
            raise AuthenticationError("Invalid access token", code="invalid_token")
        factors = self.users[email].get("mfa_factors") or []
        return list(factors)  # type: ignore[arg-type]

    async def enroll_totp(
        self, *, access_token: str, friendly_name: str = "Authenticator"
    ) -> dict[str, object]:
        email = self.tokens.get(access_token)
        if email is None:
            raise AuthenticationError("Invalid access token", code="invalid_token")
        factor_id = str(uuid4())
        self.users[email]["pending_factor"] = {
            "id": factor_id,
            "friendly_name": friendly_name,
            "factor_type": "totp",
            "status": "unverified",
        }
        return {
            "factor_id": factor_id,
            "qr_code": "data:image/svg+xml,<svg></svg>",
            "secret": "JBSWY3DPEHPK3PXP",
            "uri": "otpauth://totp/QuantForg",
            "friendly_name": friendly_name,
        }

    async def challenge_mfa(
        self, *, access_token: str, factor_id: str
    ) -> dict[str, object]:
        _ = access_token
        return {"challenge_id": f"chal-{factor_id}", "factor_id": factor_id}

    async def verify_mfa(
        self,
        *,
        access_token: str,
        factor_id: str,
        challenge_id: str,
        code: str,
    ) -> AuthSession:
        _ = challenge_id
        email = self.tokens.get(access_token)
        if email is None:
            raise AuthenticationError("Invalid access token", code="invalid_token")
        if code != "654321":
            raise AuthenticationError("Invalid MFA code", code="invalid_mfa_code")
        factors = list(self.users[email].get("mfa_factors") or [])
        factors.append(
            {
                "id": factor_id,
                "factor_type": "totp",
                "status": "verified",
                "friendly_name": "Authenticator",
            }
        )
        self.users[email]["mfa_factors"] = factors
        self.users[email].pop("pending_factor", None)
        return self._session_for(email, confirmed=True)

    async def unenroll_mfa(self, *, access_token: str, factor_id: str) -> None:
        email = self.tokens.get(access_token)
        if email is None:
            raise AuthenticationError("Invalid access token", code="invalid_token")
        factors = [
            f
            for f in (self.users[email].get("mfa_factors") or [])
            if str(f.get("id")) != factor_id  # type: ignore[union-attr]
        ]
        self.users[email]["mfa_factors"] = factors

    async def get_authenticator_assurance_level(
        self, *, access_token: str
    ) -> dict[str, object]:
        factors = await self.list_mfa_factors(access_token=access_token)
        verified = any(str(f.get("status", "")).lower() == "verified" for f in factors)
        return {
            "current_level": "aal1",
            "next_level": "aal2" if verified else "aal1",
        }

    async def request_password_reset(self, *, email: str, redirect_to: str) -> None:
        self._maybe_fail("reset_request")
        _ = (email, redirect_to)

    async def update_password(
        self,
        *,
        access_token: str,
        new_password: str,
    ) -> AuthUserIdentity:
        self._maybe_fail("update_password")
        email = self.tokens.get(access_token)
        if email is None:
            raise AuthenticationError("Invalid access token", code="invalid_token")
        self.users[email]["password"] = new_password
        return await self.get_user(access_token=access_token)

    async def get_oauth_redirect(
        self,
        *,
        provider: OAuthProvider,
        redirect_to: str,
    ) -> OAuthRedirect:
        return OAuthRedirect(
            provider=provider,
            url=f"https://oauth.test/{provider.value}?redirect_to={redirect_to}",
        )

    async def exchange_oauth_code(
        self,
        *,
        code: str,
        redirect_to: str | None = None,
    ) -> AuthSession:
        self._maybe_fail("oauth")
        _ = redirect_to
        # code format: "oauth:<provider>:<email>"
        parts = code.split(":")
        if len(parts) != 3 or parts[0] != "oauth":
            raise AuthenticationError("Invalid OAuth code", code="oauth_failed")
        provider, email = parts[1], parts[2].lower()
        auth_id = uuid4()
        self.users[email] = {
            "id": auth_id,
            "password": "",
            "display_name": email.split("@", 1)[0],
            "confirmed": True,
            "providers": (provider,),
        }
        return self._session_for(email, confirmed=True)
