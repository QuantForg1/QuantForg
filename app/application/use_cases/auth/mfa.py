"""MFA enrollment, challenge, verify, unenroll, and recovery codes."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.auth import AuthSessionDTO, MessageDTO
from app.application.use_cases.auth._profile import sync_profile_from_identity
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.exceptions.auth import AuthenticationError
from app.domain.exceptions.base import ValidationError
from app.domain.interfaces.auth import AuthProviderPort
from app.domain.interfaces.unit_of_work import UnitOfWorkFactory
from app.infrastructure.auth.mfa_recovery import (
    MfaRecoveryCodeStore,
    generate_recovery_codes,
)


@dataclass(frozen=True, slots=True)
class MfaStatusUseCase:
    auth: AuthProviderPort

    async def execute(self, *, access_token: str) -> dict[str, object]:
        factors = await self.auth.list_mfa_factors(access_token=access_token)
        aal = await self.auth.get_authenticator_assurance_level(
            access_token=access_token
        )
        verified = [
            f
            for f in factors
            if str(f.get("status", "")).lower() == "verified"
            and str(f.get("factor_type", "")).lower() == "totp"
        ]
        return {
            "enabled": bool(verified),
            "factors": factors,
            "aal": aal,
        }


@dataclass(frozen=True, slots=True)
class MfaEnrollUseCase:
    auth: AuthProviderPort
    audit: RecordAuditEventUseCase

    async def execute(
        self, *, access_token: str, actor_user_id: UUID | None
    ) -> dict[str, object]:
        payload = await self.auth.enroll_totp(access_token=access_token)
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth_mfa",
                actor_user_id=actor_user_id,
                message="MFA TOTP enrollment started",
            )
        )
        return payload


@dataclass(frozen=True, slots=True)
class MfaVerifyUseCase:
    auth: AuthProviderPort
    uow_factory: UnitOfWorkFactory
    audit: RecordAuditEventUseCase
    recovery: MfaRecoveryCodeStore | None = None

    async def execute(
        self,
        *,
        access_token: str,
        factor_id: str,
        challenge_id: str,
        code: str,
        actor_user_id: UUID | None,
        issue_recovery_codes: bool = False,
    ) -> AuthSessionDTO | dict[str, object]:
        if not (code.isdigit() and len(code) == 6):
            raise ValidationError("Enter a six-digit authenticator code", code="invalid_otp")
        challenge = challenge_id
        if not challenge:
            created = await self.auth.challenge_mfa(
                access_token=access_token, factor_id=factor_id
            )
            challenge = str(created.get("challenge_id") or "")
        from app.domain.interfaces.auth import AuthSession

        session = await self.auth.verify_mfa(
            access_token=access_token,
            factor_id=factor_id,
            challenge_id=challenge,
            code=code,
        )
        token = session.access_token or access_token
        identity = session.user or await self.auth.get_user(access_token=token)
        if not session.access_token:
            session = AuthSession(
                access_token=token,
                refresh_token=session.refresh_token,
                expires_in=session.expires_in or 3600,
                token_type=session.token_type or "bearer",
                user=identity,
            )
        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(uow, identity)
            await uow.commit()
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth_mfa",
                resource_id=user.id,
                actor_user_id=actor_user_id or user.id,
                message="MFA factor verified",
            )
        )
        dto = AuthSessionDTO.from_session(
            session, user, mfa_required=False, aal="aal2"
        )
        if issue_recovery_codes and self.recovery is not None:
            codes = generate_recovery_codes()
            self.recovery.replace_codes(user_id=user.id, codes=codes)
            return {"session": dto, "recovery_codes": codes}
        return dto


@dataclass(frozen=True, slots=True)
class MfaChallengeUseCase:
    auth: AuthProviderPort

    async def execute(self, *, access_token: str, factor_id: str) -> dict[str, object]:
        return await self.auth.challenge_mfa(
            access_token=access_token, factor_id=factor_id
        )


@dataclass(frozen=True, slots=True)
class MfaUnenrollUseCase:
    auth: AuthProviderPort
    audit: RecordAuditEventUseCase

    async def execute(
        self, *, access_token: str, factor_id: str, actor_user_id: UUID | None
    ) -> MessageDTO:
        await self.auth.unenroll_mfa(access_token=access_token, factor_id=factor_id)
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth_mfa",
                actor_user_id=actor_user_id,
                message="MFA factor removed",
            )
        )
        return MessageDTO(message="Two-factor authentication has been disabled.")


@dataclass(frozen=True, slots=True)
class MfaRecoveryGenerateUseCase:
    recovery: MfaRecoveryCodeStore
    audit: RecordAuditEventUseCase

    async def execute(self, *, user_id: UUID) -> dict[str, object]:
        codes = generate_recovery_codes()
        self.recovery.replace_codes(user_id=user_id, codes=codes)
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.UPDATE,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth_mfa_recovery",
                resource_id=user_id,
                actor_user_id=user_id,
                message="MFA recovery codes regenerated",
            )
        )
        return {"recovery_codes": codes}


@dataclass(frozen=True, slots=True)
class MfaRecoveryConsumeUseCase:
    auth: AuthProviderPort
    recovery: MfaRecoveryCodeStore
    uow_factory: UnitOfWorkFactory
    audit: RecordAuditEventUseCase

    async def execute(
        self, *, access_token: str, code: str, actor_user_id: UUID
    ) -> AuthSessionDTO:
        if not self.recovery.consume(user_id=actor_user_id, code=code):
            raise AuthenticationError(
                "Invalid or already-used recovery code",
                code="invalid_recovery_code",
            )
        identity = await self.auth.get_user(access_token=access_token)
        async with self.uow_factory() as uow:
            user = await sync_profile_from_identity(uow, identity)
            await uow.commit()
        await self.audit.execute(
            RecordAuditEventCommand(
                action=AuditAction.LOGIN,
                outcome=AuditOutcome.SUCCESS,
                resource_type="auth_mfa_recovery",
                resource_id=user.id,
                actor_user_id=user.id,
                message="MFA recovery code accepted",
            )
        )
        # Recovery proves possession; session remains current AAL until refresh.
        from app.domain.interfaces.auth import AuthSession

        return AuthSessionDTO.from_session(
            AuthSession(
                access_token=access_token,
                refresh_token="",
                expires_in=3600,
                token_type="bearer",
                user=identity,
            ),
            user,
            mfa_required=False,
            aal="aal2",
        )
