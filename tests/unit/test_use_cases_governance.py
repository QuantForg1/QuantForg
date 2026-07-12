"""Unit tests for signal, risk, audit, health, and version use cases."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.dto.audit import RecordAuditEventCommand
from app.application.dto.health import HealthStatus
from app.application.dto.risk import ValidateRiskProfileCommand
from app.application.dto.signal import CreateSignalRecordCommand
from app.application.use_cases.create_signal_record import CreateSignalRecordUseCase
from app.application.use_cases.get_health import GetHealthUseCase
from app.application.use_cases.get_version import GetVersionUseCase
from app.application.use_cases.record_audit_event import RecordAuditEventUseCase
from app.application.use_cases.validate_risk_profile import ValidateRiskProfileUseCase
from app.domain.entities.risk_profile import RiskProfile
from app.domain.entities.symbol import Symbol
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.signal import SignalDirection, SignalStatus
from app.domain.exceptions.base import NotFoundError
from tests.unit.fakes import FakeAppInfo, SharedUnitOfWorkFactory


@pytest.mark.unit
class TestCreateSignalRecordUseCase:
    @pytest.mark.asyncio
    async def test_creates_active_signal(self) -> None:
        factory = SharedUnitOfWorkFactory()
        symbol = Symbol.create(code="EURUSD", name="Euro Dollar")
        await factory.uow.symbols.add(symbol)

        result = await CreateSignalRecordUseCase(uow_factory=factory).execute(
            CreateSignalRecordCommand(
                symbol_id=symbol.id,
                direction=SignalDirection.BUY,
                confidence="0.8",
                notes="manual entry",
            )
        )

        assert result.status == SignalStatus.ACTIVE.value
        assert result.direction == "buy"
        assert result.confidence == "0.8"

    @pytest.mark.asyncio
    async def test_missing_symbol(self) -> None:
        factory = SharedUnitOfWorkFactory()
        with pytest.raises(NotFoundError):
            await CreateSignalRecordUseCase(uow_factory=factory).execute(
                CreateSignalRecordCommand(
                    symbol_id=uuid4(),
                    direction=SignalDirection.SELL,
                )
            )


@pytest.mark.unit
class TestValidateRiskProfileUseCase:
    @pytest.mark.asyncio
    async def test_valid_proposal(self) -> None:
        factory = SharedUnitOfWorkFactory()
        user_id = uuid4()
        profile = RiskProfile.create(
            user_id=user_id,
            max_risk_per_trade="2",
            max_daily_loss="5",
            max_open_positions=5,
            max_leverage=100,
        )
        await factory.uow.risk_profiles.add(profile)

        result = await ValidateRiskProfileUseCase(uow_factory=factory).execute(
            ValidateRiskProfileCommand(
                risk_profile_id=profile.id,
                proposed_risk_percent="1",
                proposed_leverage=50,
                current_open_positions=2,
            )
        )

        assert result.is_valid is True
        assert result.violations == ()

    @pytest.mark.asyncio
    async def test_collects_violations(self) -> None:
        factory = SharedUnitOfWorkFactory()
        profile = RiskProfile.create(
            user_id=uuid4(),
            max_risk_per_trade="1",
            max_daily_loss="3",
            max_open_positions=2,
            max_leverage=30,
        )
        await factory.uow.risk_profiles.add(profile)

        result = await ValidateRiskProfileUseCase(uow_factory=factory).execute(
            ValidateRiskProfileCommand(
                risk_profile_id=profile.id,
                proposed_risk_percent="2",
                proposed_leverage=100,
                current_open_positions=2,
            )
        )

        assert result.is_valid is False
        assert len(result.violations) >= 3


@pytest.mark.unit
class TestRecordAuditEventUseCase:
    @pytest.mark.asyncio
    async def test_records_event(self) -> None:
        factory = SharedUnitOfWorkFactory()
        actor = uuid4()
        result = await RecordAuditEventUseCase(uow_factory=factory).execute(
            RecordAuditEventCommand(
                action=AuditAction.LOGIN,
                outcome=AuditOutcome.SUCCESS,
                resource_type="user",
                resource_id=actor,
                actor_user_id=actor,
                ip_address="10.0.0.1",
                message="login ok",
            )
        )
        assert result.action == "login"
        assert result.outcome == "success"
        assert result.id in factory.uow.audit_logs.items


@pytest.mark.unit
class TestGetHealthAndVersionUseCases:
    @pytest.mark.asyncio
    async def test_health_all_ok(self) -> None:
        class _Ok:
            @property
            def name(self) -> str:
                return "dep"

            async def check(self) -> bool:
                return True

        use_case = GetHealthUseCase(app_info=FakeAppInfo(), probes=(_Ok(),))
        report = await use_case.execute()
        assert report.status == HealthStatus.HEALTHY
        assert report.dependencies[0].name == "dep"

    @pytest.mark.asyncio
    async def test_health_unhealthy(self) -> None:
        class _Fail:
            @property
            def name(self) -> str:
                return "dep"

            async def check(self) -> bool:
                return False

        use_case = GetHealthUseCase(app_info=FakeAppInfo(), probes=(_Fail(),))
        report = await use_case.execute()
        assert report.status == HealthStatus.UNHEALTHY

    def test_version(self) -> None:
        info = GetVersionUseCase(app_info=FakeAppInfo(app_version="9.9.9")).execute()
        assert info.version == "9.9.9"
        assert info.name == "QuantForg"
        assert info.environment == "testing"
