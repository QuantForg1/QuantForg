"""Unit tests for RC1 ops telemetry aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from app.application.services.execution_audit import ExecutionAuditService
from app.application.services.rc1_ops_telemetry import Rc1OpsTelemetryService
from app.domain.enums.execution import ExecutionAuditStage
from app.infrastructure.persistence.memory_execution_audit import (
    MemoryExecutionAuditUnitOfWorkFactory,
)


class _FakeSettings:
    mt5_gateway_base_url = ""
    railway_public_domain = ""
    supabase_configured = False
    database_url = ""


@pytest.mark.unit
@pytest.mark.asyncio
class TestRc1OpsTelemetry:
    async def test_aggregates_from_audits_without_inventing_pnl(self) -> None:
        factory = MemoryExecutionAuditUnitOfWorkFactory()
        audit = ExecutionAuditService(uow_factory=factory)
        user_id = uuid4()
        await audit.record(
            user_id=user_id,
            request_id="t-1",
            stage=ExecutionAuditStage.VALIDATION,
            symbol="EURUSD",
            volume="0.10",
            outcome="valid",
            latency_ms=3.0,
        )
        await audit.record(
            user_id=user_id,
            request_id="t-1",
            stage=ExecutionAuditStage.RISK,
            symbol="EURUSD",
            volume="0.10",
            outcome="reject",
        )
        await audit.record(
            user_id=user_id,
            request_id="t-2",
            stage=ExecutionAuditStage.SUBMIT,
            symbol="EURUSD",
            volume="0.20",
            outcome="success",
            retcode=10009,
            latency_ms=40.0,
            gateway_latency_ms=8.0,
        )
        await audit.record(
            user_id=user_id,
            request_id="t-3",
            stage=ExecutionAuditStage.SUBMIT,
            symbol="GBPUSD",
            volume="0.10",
            outcome="failed",
            retcode=10006,
            latency_ms=50.0,
            gateway_latency_ms=12.0,
        )

        svc = Rc1OpsTelemetryService(
            execution_audit_uow_factory=factory,
            settings=_FakeSettings(),
            health_service=None,
        )
        out = await svc.collect()

        assert out["daily_orders"] == 2
        assert out["execution_success_pct"] == 50.0
        assert out["execution_reject_pct"] == 50.0
        assert out["risk_reject_pct"] == 100.0
        assert out["daily_volume"] == 0.3
        assert out["daily_pnl"] is None
        assert out["avg_broker_latency_ms"] == 45.0
        assert out["avg_gateway_latency_ms"] == 10.0
        assert out["avg_validation_time_ms"] == 3.0
        assert isinstance(out["alerts"], list)
        assert out["collected_at"]
        # Ensure timestamp parses
        datetime.fromisoformat(str(out["collected_at"]).replace("Z", "+00:00"))
        assert datetime.now(UTC)
