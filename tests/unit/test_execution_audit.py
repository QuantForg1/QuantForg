"""Unit tests for Execution Audit Engine (Phase 11)."""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.application.services.execution_audit import (
    ExecutionAuditService,
    sanitize_payload_dict,
)
from app.domain.entities.execution_audit import ExecutionAudit
from app.domain.enums.execution import ExecutionAuditStage
from app.domain.exceptions.base import ValidationError
from app.infrastructure.persistence.memory_execution_audit import (
    MemoryExecutionAuditUnitOfWorkFactory,
)


@pytest.mark.unit
class TestExecutionAuditEntity:
    def test_stage_enum_accepted(self) -> None:
        user_id = uuid4()
        for stage in ExecutionAuditStage:
            audit = ExecutionAudit.record(
                user_id=user_id,
                request_id="req-1",
                stage=stage,
                symbol="EURUSD",
                outcome="ok",
            )
            assert audit.stage is stage
            assert audit.to_dict()["stage"] == stage.value

    def test_invalid_stage_rejected(self) -> None:
        with pytest.raises((ValidationError, ValueError)):
            ExecutionAudit.record(
                user_id=uuid4(),
                request_id="req-1",
                stage="not_a_stage",
            )


@pytest.mark.unit
class TestSanitizePayload:
    def test_strips_secrets_from_nested_dicts(self) -> None:
        raw = {
            "symbol": "EURUSD",
            "password": "hunter2",
            "api_token": "abc",
            "nested": {
                "secret": "x",
                "ok": 1,
                "authorization": "Bearer xyz",
            },
            "items": [{"api_key": "k", "volume": "0.01"}],
        }
        cleaned = sanitize_payload_dict(raw)
        assert cleaned["symbol"] == "EURUSD"
        assert cleaned["password"] == "[redacted]"
        assert cleaned["api_token"] == "[redacted]"
        nested = cleaned["nested"]
        assert isinstance(nested, dict)
        assert nested["secret"] == "[redacted]"
        assert nested["ok"] == 1
        assert nested["authorization"] == "[redacted]"
        items = cleaned["items"]
        assert isinstance(items, list)
        assert isinstance(items[0], dict)
        assert items[0]["api_key"] == "[redacted]"
        assert items[0]["volume"] == "0.01"


@pytest.mark.unit
@pytest.mark.asyncio
class TestExecutionAuditService:
    async def test_record_list_and_timeline(self) -> None:
        factory = MemoryExecutionAuditUnitOfWorkFactory()
        svc = ExecutionAuditService(uow_factory=factory)
        user_id = uuid4()
        request_id = "timeline-req-1"

        first = await svc.record(
            user_id=user_id,
            request_id=request_id,
            stage=ExecutionAuditStage.VALIDATION,
            symbol="EURUSD",
            side="buy",
            volume="0.10",
            outcome="valid",
            payload_in={"password": "secret", "symbol": "EURUSD"},
        )
        second = await svc.record(
            user_id=user_id,
            request_id=request_id,
            stage=ExecutionAuditStage.RISK,
            symbol="EURUSD",
            side="buy",
            volume="0.10",
            outcome="allow",
        )
        await svc.record(
            user_id=user_id,
            request_id=request_id,
            stage=ExecutionAuditStage.SUBMIT,
            symbol="EURUSD",
            side="buy",
            volume="0.10",
            outcome="success",
            retcode=10009,
            latency_ms=12.5,
            gateway_latency_ms=4.0,
            cloudflare_latency_ms=None,
        )
        other = await svc.record(
            user_id=user_id,
            request_id="other-req",
            stage=ExecutionAuditStage.SAFETY,
            symbol="GBPUSD",
            outcome="allow",
        )

        listed = await svc.list_for_user(user_id, limit=50)
        assert len(listed) == 4
        assert listed[0].id == other.id

        timeline = await svc.get_timeline(user_id, request_id)
        assert [a.stage for a in timeline] == [
            ExecutionAuditStage.VALIDATION,
            ExecutionAuditStage.RISK,
            ExecutionAuditStage.SUBMIT,
        ]
        assert timeline[0].id == first.id
        assert timeline[1].id == second.id
        assert timeline[0].payload_in["password"] == "[redacted]"
        assert timeline[0].payload_in["symbol"] == "EURUSD"
        assert timeline[2].latency_ms == 12.5
        assert timeline[2].cloudflare_latency_ms is None

    async def test_idempotent_per_user_request_stage(self) -> None:
        factory = MemoryExecutionAuditUnitOfWorkFactory()
        svc = ExecutionAuditService(uow_factory=factory)
        user_id = uuid4()
        request_id = "idem-req-1"

        first = await svc.record(
            user_id=user_id,
            request_id=request_id,
            stage=ExecutionAuditStage.VALIDATION,
            symbol="EURUSD",
            outcome="valid",
        )
        duplicate = await svc.record(
            user_id=user_id,
            request_id=request_id,
            stage=ExecutionAuditStage.VALIDATION,
            symbol="EURUSD",
            outcome="valid-again",
        )
        assert duplicate.id == first.id
        listed = await svc.list_for_user(user_id, limit=50)
        assert len(listed) == 1
        assert listed[0].outcome == "valid"

        await svc.record(
            user_id=user_id,
            request_id=request_id,
            stage=ExecutionAuditStage.RISK,
            symbol="EURUSD",
            outcome="allow",
        )
        listed = await svc.list_for_user(user_id, limit=50)
        assert len(listed) == 2

    async def test_manage_cancel_history_stages(self) -> None:
        factory = MemoryExecutionAuditUnitOfWorkFactory()
        svc = ExecutionAuditService(uow_factory=factory)
        user_id = uuid4()
        manage_id = "manage-req-1"
        cancel_id = "cancel-req-1"

        await svc.record(
            user_id=user_id,
            request_id=manage_id,
            stage=ExecutionAuditStage.MANAGE,
            symbol="EURUSD",
            outcome="success",
            order_ticket=1001,
            deal_ticket=2001,
        )
        await svc.record(
            user_id=user_id,
            request_id=manage_id,
            stage=ExecutionAuditStage.HISTORY,
            symbol="EURUSD",
            outcome="recorded",
            order_ticket=1001,
            deal_ticket=2001,
        )
        await svc.record(
            user_id=user_id,
            request_id=cancel_id,
            stage=ExecutionAuditStage.CANCEL,
            symbol="EURUSD",
            outcome="success",
            order_ticket=1002,
        )
        await svc.record(
            user_id=user_id,
            request_id=cancel_id,
            stage=ExecutionAuditStage.HISTORY,
            symbol="EURUSD",
            outcome="recorded",
            order_ticket=1002,
        )

        manage_chain = await svc.get_timeline(user_id, manage_id)
        assert [a.stage for a in manage_chain] == [
            ExecutionAuditStage.MANAGE,
            ExecutionAuditStage.HISTORY,
        ]
        cancel_chain = await svc.get_timeline(user_id, cancel_id)
        assert [a.stage for a in cancel_chain] == [
            ExecutionAuditStage.CANCEL,
            ExecutionAuditStage.HISTORY,
        ]
