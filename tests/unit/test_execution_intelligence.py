"""Unit tests for Execution Intelligence — no order_send / no flag flips."""

from __future__ import annotations

import pytest

from app.application.services.execution_intelligence import ExecutionIntelligenceService
from app.domain.execution_intelligence.checklist import evaluate_checklist
from app.domain.execution_intelligence.lifecycle import LifecycleState
from app.domain.execution_intelligence.store import LifecycleStore


@pytest.mark.unit
class TestChecklist:
    def test_blocks_when_execution_disabled(self) -> None:
        result = evaluate_checklist(
            broker_connected=True,
            market_open=True,
            risk_passed=True,
            margin_sufficient=True,
            strategy_signal_valid=True,
            execution_enabled=False,
        )
        assert result["ready_for_execution"] is False
        assert result["blocked"] is True
        assert any("EXECUTION_ENABLED" in b for b in result["blockers"])

    def test_unavailable_facts(self) -> None:
        result = evaluate_checklist(
            broker_connected=None,
            market_open=None,
            risk_passed=True,
            margin_sufficient=True,
            strategy_signal_valid=True,
            execution_enabled=True,
        )
        assert result["ready_for_execution"] is False
        assert "broker_connected" in result["unknown_facts"]


@pytest.mark.unit
class TestLifecycleStore:
    def test_archive_on_terminal(self) -> None:
        store = LifecycleStore()
        store.create(
            user_id="u1",
            request_id="r1",
            symbol="EURUSD",
            side="buy",
            order_type="market",
            volume="0.1",
        )
        store.transition(
            user_id="u1",
            request_id="r1",
            to_state=LifecycleState.VALIDATED,
            reason="validated",
            source="test",
        )
        store.transition(
            user_id="u1",
            request_id="r1",
            to_state=LifecycleState.RISK_APPROVED,
            reason="risk ok",
            source="test",
        )
        store.transition(
            user_id="u1",
            request_id="r1",
            to_state=LifecycleState.SUBMITTED,
            reason="submitted",
            source="test",
        )
        result = store.transition(
            user_id="u1",
            request_id="r1",
            to_state=LifecycleState.FILLED,
            reason="filled",
            source="test",
        )
        assert result["ok"] is True
        store.transition(
            user_id="u1",
            request_id="r1",
            to_state=LifecycleState.CLOSED,
            reason="closed",
            source="test",
        )
        rec = store.get("u1", "r1")
        assert rec is not None
        assert rec["state"] == "Closed"
        assert rec["archived"] is True
        assert len(rec["history"]) >= 5


@pytest.mark.unit
class TestExecutionIntelligenceService:
    def setup_method(self) -> None:
        self.svc = ExecutionIntelligenceService(store=LifecycleStore())

    def test_ingest_attempts_and_analytics(self) -> None:
        attempts = [
            {
                "request_id": "a1",
                "symbol": "EURUSD",
                "side": "buy",
                "order_type": "market",
                "volume": "0.1",
                "outcome": "success",
                "message": "done",
                "retcode": 0,
                "latency_ms": 12.5,
                "submitted_at": "2024-01-01T10:00:00+00:00",
                "filled_at": "2024-01-01T10:00:01+00:00",
            },
            {
                "request_id": "a2",
                "symbol": "GBPUSD",
                "side": "sell",
                "order_type": "market",
                "volume": "0.2",
                "outcome": "failed",
                "message": "rejected",
                "retcode": 10006,
                "latency_ms": 40.0,
            },
        ]
        fills = [
            {"requested_price": "1.1000", "fill_price": "1.1002", "slippage": "0.0002"}
        ]
        self.svc.ingest_attempts(user_id="u1", attempts=attempts)
        analytics = self.svc.analytics(attempts=attempts, fills=fills)
        assert analytics["status"] == "available"
        assert analytics["metrics"]["fill_rate"] == pytest.approx(0.5)
        assert analytics["metrics"]["reject_rate"] == pytest.approx(0.5)
        assert analytics["metrics"]["average_slippage"] is not None
        items = self.svc.store.list_for_user("u1")
        assert len(items) == 2

    def test_post_trade_explainability(self) -> None:
        result = self.svc.post_trade(
            trades=[
                {
                    "symbol": "EURUSD",
                    "side": "buy",
                    "pnl": "25",
                    "entry_price": "1.1",
                    "exit_price": "1.105",
                    "slippage": "0.0001",
                }
            ]
        )
        assert result["status"] == "available"
        item = result["items"][0]
        assert item["explanation"]["reason"]
        assert item["explanation"]["data_source"]
        assert item["autonomous_trading"] is False

    def test_dashboard_never_enables_execution(self) -> None:
        dash = self.svc.dashboard(
            user_id="u1",
            attempts=[],
            decisions=[],
            fills=[],
            trades=[],
            checklist_facts={},
            broker_facts={
                "connected": False,
                "status": "disconnected",
                "latency_ms": None,
                "last_heartbeat_at": None,
                "last_disconnect_reason": None,
                "reconnect_events": [],
                "uptime_seconds": None,
            },
            execution_enabled=False,
        )
        assert dash["execution_enabled"] is False
        assert dash["autonomous_trading"] is False
        assert dash["checklist"]["blocked"] is True
