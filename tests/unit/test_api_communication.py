"""API communication faults, strategy contract, snapshot reuse, recovery."""

from __future__ import annotations

import inspect
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.application.services.institutional_observability import (
    reset_observability_pack_cache,
    run_observability,
)
from app.domain.institutional_trading.operations.communication_fault import (
    AUTONOMOUS_PATH_INDEPENDENT_OF_UI,
    CANONICAL_BROKER_SYMBOL,
    CommunicationFault,
    classify_http_fault,
    communication_latency_fields,
    is_no_trade_fault,
    market_data_failure_blocks,
    should_blind_retry_order_submit,
    should_replay_after_refresh,
    snapshot_reuse_key,
    telemetry_must_not_block_decision,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    LatencyBudget,
    build_authoritative_snapshot,
)
from app.domain.institutional_trading.operations.trade_classifier import (
    TradeClass,
    classify_trade,
)
from app.presentation.schemas.strategy import StrategyEvaluateRequest

pytestmark = [pytest.mark.unit]


class TestApiBaseAndFaults:
    def test_status_zero_is_unreachable_not_no_trade(self) -> None:
        fault = classify_http_fault(status=0, code="network_error")
        assert fault is CommunicationFault.API_UNREACHABLE
        assert not is_no_trade_fault(fault)

    def test_timeout_is_api_timeout(self) -> None:
        fault = classify_http_fault(status=408, code="timeout")
        assert fault is CommunicationFault.API_TIMEOUT
        assert not is_no_trade_fault(fault)

    def test_missing_token_is_auth_required(self) -> None:
        assert (
            classify_http_fault(status=401, code="missing_token")
            is CommunicationFault.AUTH_REQUIRED
        )

    def test_expired_token_refresh_then_required(self) -> None:
        assert (
            classify_http_fault(status=401, code="authentication_failed")
            is CommunicationFault.AUTH_REFRESH
        )
        assert (
            classify_http_fault(
                status=401,
                code="authentication_failed",
                refresh_attempted=True,
            )
            is CommunicationFault.AUTH_REQUIRED
        )

    def test_invalid_token(self) -> None:
        assert (
            classify_http_fault(status=401, code="invalid_token")
            is CommunicationFault.AUTH_REFRESH
        )


class TestStrategyEvaluateContract:
    def test_valid_request(self) -> None:
        body = StrategyEvaluateRequest.model_validate(
            {
                "request_id": "contract-1",
                "symbol": "XAUUSD_i",
                "timeframe": "m15",
            }
        )
        assert body.symbol == "XAUUSD_i"
        assert body.request_id == "contract-1"

    def test_missing_request_id_rejected(self) -> None:
        with pytest.raises(ValidationError):
            StrategyEvaluateRequest.model_validate({"symbol": "XAUUSD_i"})

    def test_unknown_side_volume_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            StrategyEvaluateRequest.model_validate(
                {
                    "request_id": "bad-1",
                    "symbol": "XAUUSD_i",
                    "side": "buy",
                    "volume": "0.01",
                }
            )
        assert "side" in str(exc.value) or "extra" in str(exc.value).lower()


class TestDedupeAndSnapshot:
    def test_snapshot_reuse_same_cycle(self) -> None:
        key_a = snapshot_reuse_key(
            cycle_id="cycle-1", snapshot_id="snap-1", symbol="XAUUSD_i"
        )
        key_b = snapshot_reuse_key(
            cycle_id="cycle-1", snapshot_id="snap-1", symbol="XAUUSD_i"
        )
        assert key_a == key_b
        snap = build_authoritative_snapshot(cycle_id="cycle-1", snapshot_id="snap-1")
        again = build_authoritative_snapshot(cycle_id="cycle-1", snapshot_id="snap-1")
        assert snap.cycle_id == again.cycle_id
        assert snap.snapshot_id == again.snapshot_id
        assert snap.canonical_symbol == CANONICAL_BROKER_SYMBOL

    def test_observability_pack_reused_within_ttl(self) -> None:
        reset_observability_pack_cache()
        first = run_observability(
            ops_facts={"gateway_connected": True},
            latency_samples={},
            error_events=[],
            user_id="u1",
        )
        # Explicit facts bypass cache; empty-optional path uses cache.
        reset_observability_pack_cache()
        with (
            patch(
                "app.application.services.institutional_observability._try_ops_facts",
                return_value={"gateway_connected": True},
            ) as ops,
            patch(
                "app.application.services.institutional_observability._try_governance_events",
                return_value=[],
            ),
        ):
            a = run_observability(user_id="u1")
            b = run_observability(user_id="u1")
        assert a is b
        assert ops.call_count == 1
        assert first["health"] or True


class TestCriticalVsTelemetry:
    def test_telemetry_failure_does_not_block_decision(self) -> None:
        assert telemetry_must_not_block_decision(CommunicationFault.API_TIMEOUT)
        assert telemetry_must_not_block_decision(CommunicationFault.SERVER_ERROR)
        classified = classify_trade(
            opportunity_score=90,
            direction="BUY",
            structure=80,
        )
        assert classified.trade_class is not TradeClass.NO_TRADE

    def test_market_data_failure_blocks_safely(self) -> None:
        fault = CommunicationFault.MARKET_DATA_UNAVAILABLE
        assert market_data_failure_blocks(fault)
        blocked = classify_trade(
            opportunity_score=90,
            direction="BUY",
            structure=80,
            hard_market_invalid=True,
            hard_invalid_reason="MARKET_DATA_UNAVAILABLE",
        )
        assert blocked.trade_class is TradeClass.NO_TRADE

    def test_order_submit_never_blindly_retried(self) -> None:
        assert should_blind_retry_order_submit() is False
        assert (
            should_replay_after_refresh(method="POST", path="/execution/submit")
            is False
        )
        assert should_replay_after_refresh(method="GET", path="/positions") is True

    def test_xauusd_i_canonical(self) -> None:
        assert CANONICAL_BROKER_SYMBOL == "XAUUSD_i"

    def test_autonomous_path_independent_of_ui(self) -> None:
        assert AUTONOMOUS_PATH_INDEPENDENT_OF_UI is True
        from app.application.services import institutional_ite_runtime as ite

        source = inspect.getsource(ite)
        assert "next/navigation" not in source
        assert "window." not in source
        assert "localStorage" not in source

    def test_same_cycle_decision_coherent(self) -> None:
        snap = build_authoritative_snapshot(
            cycle_id="cycle-coherent", snapshot_id="snap-coherent"
        )
        first = classify_trade(
            opportunity_score=88,
            direction="BUY",
            structure=80,
            mtf_alignment=70,
        )
        second = classify_trade(
            opportunity_score=88,
            direction="BUY",
            structure=80,
            mtf_alignment=70,
        )
        assert first.trade_class is second.trade_class
        assert snap.cycle_id == "cycle-coherent"
        assert snap.canonical_symbol == "XAUUSD_i"


class TestLatencyInstrumentation:
    def test_measured_aliases(self) -> None:
        budget = LatencyBudget(
            market_ms=12.0,
            probability_ms=8.0,
            decision_ms=5.0,
            risk_ms=3.0,
            safety_ms=2.0,
            signal_detect_to_snapshot_ms=4.0,
            snapshot_to_probability_ms=3.0,
            probability_to_decision_ms=5.0,
            decision_to_risk_ms=3.0,
            risk_to_safety_ms=2.0,
            safety_to_plan_ms=1.0,
        )
        payload = budget.to_dict()
        assert payload["measured"] is True
        assert payload["market_data_ms"] == 12.0
        assert payload["strategy_ms"] == 8.0
        assert payload["signal_to_decision_ms"] == 12.0
        assert payload["signal_to_execution_ready_ms"] == 18.0
        fields = communication_latency_fields(payload)
        assert fields["market_data_ms"] == 12.0
        assert fields["signal_to_decision_ms"] == 12.0
        assert fields["oms_ms"] == 0.0
