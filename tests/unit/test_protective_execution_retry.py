"""A rejected protective close or stop change must reach the broker again.

A new entry with the same request id stays an idempotent replay. An
in-flight, filled, or ambiguous attempt is not sent again.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import uuid4

import pytest

from app.application.dto.execution import ExecutionSubmitCommand
from app.application.services.institutional_execution_engine import PipelineResult
from app.application.use_cases.execution_gateway import SubmitExecutionUseCase
from app.domain.entities.execution_gateway import (
    ExecutionAttempt,
    ExecutionResult,
    protective_retry_allowed,
)
from app.domain.entities.execution_safety import ExecutionDecisionRecord
from app.domain.enums.execution import ExecutionDecision, ExecutionOutcome
from app.domain.exceptions.base import ValidationError
from tests.unit.test_execution_gateway import _connect, _wire


def _allow(
    *,
    kind: str = "close",
    position: object = 9,
    outcome: ExecutionOutcome = ExecutionOutcome.RETRY,
    order_ticket: object = None,
    deal_ticket: object = None,
    message: str = "Broker requote / timeout — retry the order",
) -> bool:
    return protective_retry_allowed(
        oms_kind=kind,
        position=position,
        outcome=outcome,
        order_ticket=order_ticket,
        deal_ticket=deal_ticket,
        message=message,
    )


class _Engine:
    def __init__(self, adapter: Any) -> None:
        self.gateway = type("Gateway", (), {"adapter": adapter})()
        self.calls: list[dict[str, Any]] = []
        self.steps: list[Any] = []

    def run_submit(self, **kwargs: Any) -> tuple[PipelineResult, Any]:
        self.calls.append(kwargs)
        step = self.steps.pop(0)
        if step == "timeout":
            raise TimeoutError("gateway timed out")
        pipeline, with_decision = step
        decision = None
        if with_decision:
            decision = ExecutionDecisionRecord.record(
                user_id=kwargs["user_id"],
                request_id=kwargs["request_id"],
                decision=ExecutionDecision.RETRY,
                symbol="XAUUSD",
                side="sell",
                order_type="market",
                volume=Decimal("0.01"),
                rejection_reasons=["prior protective attempt"],
                request_fingerprint="same-close",
            )
        return pipeline, decision


def _pipeline(
    outcome: str,
    message: str,
    result: ExecutionResult | None = None,
) -> PipelineResult:
    return PipelineResult(
        request_id="scripted",
        action="manage",
        outcome=outcome,
        message=message,
        stages=[],
        execution_result=result,
    )


def _filled() -> ExecutionResult:
    return ExecutionResult(
        outcome=ExecutionOutcome.SUCCESS,
        retcode=10009,
        message="filled",
        order_ticket=55,
        deal_ticket=66,
        volume=Decimal("0.01"),
        price=Decimal("2300"),
        symbol="XAUUSD",
        request_id="filled",
    )


def _command(**overrides: Any) -> ExecutionSubmitCommand:
    payload: dict[str, Any] = {
        "user_id": uuid4(),
        "request_id": "m1-exit-9",
        "symbol": "XAUUSD",
        "side": "sell",
        "volume": "0.01",
        "position": 9,
        "oms_kind": "close",
    }
    payload.update(overrides)
    return ExecutionSubmitCommand(**payload)


async def _use_case() -> tuple[SubmitExecutionUseCase, _Engine, Any]:
    mt5_factory, exec_factory, adapter, _gateway, audit, _client, _engine = _wire(
        execution_enabled=True
    )
    user_id = uuid4()
    await _connect(mt5_factory, adapter, audit, user_id)
    engine = _Engine(adapter)
    use_case = SubmitExecutionUseCase(
        mt5_uow_factory=mt5_factory,
        execution_uow_factory=exec_factory,
        engine=engine,  # type: ignore[arg-type]
        audit=audit,
    )
    return use_case, engine, user_id


@pytest.mark.unit
@pytest.mark.trading_core
class TestProtectiveRetryPredicate:
    def test_rejected_close_and_stop_change_may_retry(self) -> None:
        assert _allow() is True
        assert _allow(kind="partial_close", outcome=ExecutionOutcome.FAILED) is True
        assert _allow(kind="sltp", message="Invalid stops") is True
        assert _allow(kind="modify_sltp", position="9") is True

    def test_entries_fills_and_ambiguous_results_stay_put(self) -> None:
        assert _allow(kind="", position=0) is False
        assert _allow(kind="close", position=0) is False
        assert _allow(kind="reverse", position=9) is False
        assert _allow(outcome=ExecutionOutcome.SUCCESS) is False
        assert _allow(outcome=ExecutionOutcome.PREPARED) is False
        assert _allow(outcome=ExecutionOutcome.DISABLED) is False
        assert _allow(outcome=ExecutionOutcome.CANCELLED) is False
        assert _allow(order_ticket=55) is False
        assert _allow(deal_ticket=66) is False
        assert _allow(order_ticket="not-a-ticket") is False
        assert _allow(message="ambiguous; do not auto-retry") is False


@pytest.mark.unit
@pytest.mark.trading_core
class TestProtectiveRetryUseCase:
    @pytest.mark.asyncio
    async def test_rejected_close_is_sent_again(self) -> None:
        use_case, engine, user_id = await _use_case()
        engine.steps.append((_pipeline("retry", "requote"), True))
        engine.steps.append((_pipeline("success", "filled", _filled()), False))
        command = _command(user_id=user_id)
        with pytest.raises(ValidationError) as first:
            await use_case.execute(command)
        assert first.value.details["code"] == "execution_pipeline_rejected"
        async with use_case.execution_uow_factory() as uow:
            stored = await uow.attempts.get_by_request_id(user_id, command.request_id)
        assert stored is not None
        assert stored.outcome is ExecutionOutcome.RETRY

        second = await use_case.execute(command)

        assert len(engine.calls) == 2
        assert engine.calls[1]["existing_decision"] is None
        assert all(
            row.request_id != command.request_id
            for row in engine.calls[1]["recent_decisions"]
        )
        assert second.idempotent_replay is False
        assert second.outcome == "success"
        assert second.id == stored.id
        assert second.order_ticket == 55

    @pytest.mark.asyncio
    async def test_failed_entry_is_not_sent_again(self) -> None:
        use_case, engine, user_id = await _use_case()
        engine.steps.append((_pipeline("rejected", "broker rejected"), False))
        command = _command(
            user_id=user_id,
            request_id="entry-1",
            side="buy",
            position=0,
            oms_kind="",
        )
        with pytest.raises(ValidationError):
            await use_case.execute(command)
        replay = await use_case.execute(command)
        assert len(engine.calls) == 1
        assert replay.idempotent_replay is True
        assert replay.outcome == "failed"

    @pytest.mark.asyncio
    async def test_filled_close_is_not_sent_again(self) -> None:
        use_case, engine, user_id = await _use_case()
        engine.steps.append((_pipeline("success", "filled", _filled()), False))
        command = _command(user_id=user_id, request_id="m1-exit-filled")
        first = await use_case.execute(command)
        second = await use_case.execute(command)
        assert len(engine.calls) == 1
        assert first.order_ticket == 55
        assert second.idempotent_replay is True
        assert second.order_ticket == first.order_ticket

    @pytest.mark.asyncio
    async def test_ambiguous_close_is_not_sent_again(self) -> None:
        use_case, engine, user_id = await _use_case()
        engine.steps.append("timeout")
        command = _command(user_id=user_id, request_id="m1-exit-ambiguous")
        with pytest.raises(ValidationError) as exc:
            await use_case.execute(command)
        assert exc.value.details["code"] == "execution_transport_ambiguous"
        replay = await use_case.execute(command)
        assert len(engine.calls) == 1
        assert replay.idempotent_replay is True
        assert "do not auto-retry" in replay.message

    @pytest.mark.asyncio
    async def test_in_flight_close_is_not_sent_again(self) -> None:
        use_case, engine, user_id = await _use_case()
        async with use_case.execution_uow_factory() as uow:
            await uow.attempts.add(
                ExecutionAttempt(
                    user_id=user_id,
                    request_id="m1-exit-inflight",
                    symbol="XAUUSD",
                    side="sell",
                    order_type="market",
                    volume=Decimal("0.01"),
                    outcome=ExecutionOutcome.PREPARED,
                    retcode=0,
                    message="in_flight",
                )
            )
            await uow.commit()
        with pytest.raises(ValidationError) as exc:
            await use_case.execute(
                _command(user_id=user_id, request_id="m1-exit-inflight")
            )
        assert exc.value.details["code"] == "execution_in_flight"
        assert engine.calls == []
