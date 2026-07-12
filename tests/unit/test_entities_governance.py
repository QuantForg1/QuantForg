"""Unit tests for RiskProfile, StrategyMetadata, and AuditLog."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.entities.audit_log import AuditLog
from app.domain.entities.risk_profile import RiskProfile
from app.domain.entities.strategy_metadata import StrategyMetadata
from app.domain.enums.audit import AuditAction, AuditOutcome
from app.domain.enums.risk import RiskLevel
from app.domain.enums.strategy import StrategyStatus, StrategyType
from app.domain.exceptions.base import ConflictError, ValidationError


@pytest.mark.unit
class TestRiskProfile:
    def test_create_and_update(self) -> None:
        profile = RiskProfile.create(
            user_id=uuid4(),
            risk_level=RiskLevel.CONSERVATIVE,
            max_risk_per_trade="0.5",
            max_daily_loss="2",
            max_open_positions=3,
            max_leverage=50,
        )
        assert profile.is_active
        profile.update_limits(max_risk_per_trade="1", max_daily_loss="3")
        assert str(profile.max_risk_per_trade) == "1%"

    def test_risk_cannot_exceed_daily(self) -> None:
        with pytest.raises(ValidationError):
            RiskProfile.create(
                user_id=uuid4(),
                max_risk_per_trade="10",
                max_daily_loss="5",
            )


@pytest.mark.unit
class TestStrategyMetadata:
    def test_publish_lifecycle(self) -> None:
        meta = StrategyMetadata.create(
            name="Trend Rider",
            slug="trend-rider",
            version="1.0.0",
            owner_user_id=uuid4(),
            strategy_type=StrategyType.TREND,
            parameter_schema={"lookback": "integer", "threshold": "number"},
            tags=["trend", "fx"],
        )
        assert meta.status == StrategyStatus.DRAFT
        meta.publish()
        assert meta.status == StrategyStatus.PUBLISHED
        meta.deprecate()
        meta.archive()
        with pytest.raises(ConflictError):
            meta.update_description("nope")

    def test_invalid_parameter_type(self) -> None:
        with pytest.raises(ValidationError):
            StrategyMetadata.create(
                name="Bad",
                slug="bad",
                version="0.1.0",
                owner_user_id=uuid4(),
                parameter_schema={"x": "object"},
            )


@pytest.mark.unit
class TestAuditLog:
    def test_record_immutable(self) -> None:
        entry = AuditLog.record(
            action=AuditAction.LOGIN,
            outcome=AuditOutcome.SUCCESS,
            resource_type="user",
            resource_id=uuid4(),
            actor_user_id=uuid4(),
            ip_address="127.0.0.1",
            message="User logged in",
        )
        assert entry.action == AuditAction.LOGIN
        with pytest.raises(ConflictError):
            entry.touch()

    def test_invalid_ip(self) -> None:
        with pytest.raises(ValidationError):
            AuditLog.record(
                action=AuditAction.SYSTEM,
                outcome=AuditOutcome.FAILURE,
                resource_type="system",
                ip_address="not-an-ip",
            )
