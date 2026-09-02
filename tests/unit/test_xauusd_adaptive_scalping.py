"""XAUUSD adaptive scalping — reduce-only sizing, fail-closed, no martingale.

Does not send orders. Does not bypass Risk, Safety, OMS, or MT5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

import pytest

from app.application.services.autonomous_execution_context import (
    GATEWAY_UNAVAILABLE,
    MT5_UNAVAILABLE,
    RECONCILIATION_REQUIRED,
    build_autonomous_execution_context,
)
from app.domain.execution_intelligence.analytics import _trade_timeline
from app.domain.institutional_ai_decision.config import DecisionEngineV1Config
from app.domain.institutional_ai_decision.loss_protection import (
    evaluate_loss_protection,
)
from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
    adaptive_protection_scale,
    calculate_dynamic_lots_v2,
    check_portfolio_sizing_limits,
)
from app.domain.institutional_trading.operations.communication_fault import (
    should_blind_retry_order_submit,
)
from app.domain.institutional_trading.operations.decision_cycle import LatencyBudget
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.probability_selector import (
    ADAPTIVE_THRESHOLD_ENABLED,
    OPPORTUNITY_SCORE_THRESHOLD,
    evaluate_from_facts,
)
from app.domain.institutional_trading.phase_a.market_data_firewall import (
    MarketDataState,
    evaluate_market_data_firewall,
)
from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from app.domain.scalping_ai_v2 import ScalpCycleInput, ScalpingAiV2
from app.domain.scalping_ai_v2.hardening import classify_retry
from app.domain.trading.gold_only import (
    DISABLED_AUTONOMOUS_SYMBOL,
    GOLD_SYMBOL,
    DisabledAutonomousSymbolError,
    require_xauusd,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def gold_only(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )


def _size(**overrides: object) -> object:
    kwargs: dict[str, object] = {
        "equity": Decimal("5000"),
        "balance": Decimal("5000"),
        "free_margin": Decimal("4500"),
        "stop_distance": Decimal("2.00"),
        "atr": Decimal("4.00"),
        "mid_price": Decimal("2650"),
        "risk_pct": Decimal("0.50"),
        "contract_size": Decimal("100"),
        "min_lot": Decimal("0.01"),
        "lot_step": Decimal("0.01"),
        "max_lot": Decimal("50"),
        "quality_score": 92,
        "confidence": 90,
        "liquidity_score": 80,
        "spread_score": 80,
        "log": False,
    }
    kwargs.update(overrides)
    return calculate_dynamic_lots_v2(**kwargs)  # type: ignore[arg-type]


class TestXauusdOnly:
    def test_require_xauusd_accepts_gold(self, gold_only: None) -> None:
        _ = gold_only
        assert require_xauusd("XAUUSD_i") == "XAUUSD_I"
        assert GOLD_SYMBOL == "XAUUSD"

    def test_non_xauusd_rejected(self, gold_only: None) -> None:
        _ = gold_only
        with pytest.raises(DisabledAutonomousSymbolError) as ei:
            require_xauusd("EURUSD")
        assert ei.value.code == DISABLED_AUTONOMOUS_SYMBOL

    def test_gold_contract_rejects_fx(self, gold_only: None) -> None:
        _ = gold_only
        out = evaluate_gold_execution_contract(
            GoldExecutionFacts(
                symbol="EURUSD_i",
                direction="BUY",
                action="BUY",
                bid=Decimal("1.08"),
                ask=Decimal("1.0802"),
                quote_age_seconds=1.0,
                gold_only=True,
            )
        )
        assert out.may_submit_oms is False
        assert out.fault_code == DISABLED_AUTONOMOUS_SYMBOL


class TestAdaptiveSizing:
    def test_protection_scale_never_exceeds_one(self) -> None:
        scale, block, _notes = adaptive_protection_scale(consecutive_wins=12)
        assert block is None
        assert scale == Decimal("1")

    def test_daily_loss_hard_stop(self) -> None:
        scale, block, notes = adaptive_protection_scale(
            daily_loss_pct=Decimal("3.0"),
            max_daily_loss_pct=Decimal("3.0"),
        )
        assert scale == Decimal("0")
        assert block == "daily_loss_limit"
        assert notes

        d = _size(
            daily_loss_pct=Decimal("3.0"),
            max_daily_loss_pct=Decimal("3.0"),
        )
        assert d.valid is False
        assert d.final_lot == Decimal("0")
        assert d.method == "daily_loss_limit"

    def test_approaching_daily_loss_reduces_risk(self) -> None:
        base = _size(daily_loss_pct=Decimal("0"))
        caution = _size(daily_loss_pct=Decimal("1.0"), max_daily_loss_pct=Decimal("3"))
        defensive = _size(
            daily_loss_pct=Decimal("1.6"), max_daily_loss_pct=Decimal("3")
        )
        assert base.valid and caution.valid and defensive.valid
        assert caution.risk_pct < base.risk_pct
        assert defensive.risk_pct < caution.risk_pct
        assert defensive.final_lot <= caution.final_lot <= base.final_lot

    def test_drawdown_reduction(self) -> None:
        base = _size(current_drawdown_pct=Decimal("0"))
        reduced = _size(current_drawdown_pct=Decimal("5"))
        assert reduced.risk_pct < base.risk_pct
        assert reduced.final_lot <= base.final_lot

    def test_no_martingale_after_losses(self) -> None:
        healthy = _size(consecutive_losses=0, equity=Decimal("1000"))
        after_losses = _size(consecutive_losses=3, equity=Decimal("1000"))
        assert after_losses.risk_pct < healthy.risk_pct
        if after_losses.valid and healthy.valid:
            assert after_losses.final_lot <= healthy.final_lot
        cfg = AiScalpingConfig(allow_martingale=True)
        assert cfg.allow_martingale is False

    def test_no_revenge_sizing_after_equity_drop(self) -> None:
        healthy = _size(
            consecutive_losses=0,
            equity=Decimal("1000"),
            current_drawdown_pct=Decimal("0"),
        )
        revenge = _size(
            consecutive_losses=3,
            equity=Decimal("800"),
            current_drawdown_pct=Decimal("20"),
        )
        assert revenge.final_lot <= healthy.final_lot
        assert revenge.risk_pct < healthy.risk_pct

    def test_consecutive_wins_do_not_raise_risk_cap(self) -> None:
        base = _size(consecutive_wins=0, risk_pct=Decimal("0.50"))
        after_wins = _size(consecutive_wins=8, risk_pct=Decimal("0.50"))
        assert after_wins.risk_pct <= base.risk_pct
        assert after_wins.configured_max_risk_pct <= Decimal("0.50")
        if after_wins.valid and base.valid:
            assert after_wins.final_lot <= base.final_lot

    def test_maximum_risk_enforcement(self) -> None:
        d = _size(risk_pct=Decimal("0.50"), quality_score=99, confidence=99)
        assert d.risk_pct <= Decimal("0.50")
        assert d.configured_max_risk_pct <= Decimal("0.50")

    def test_never_hardcoded_five_lots(self) -> None:
        tiny = _size(equity=Decimal("100"), free_margin=Decimal("90"))
        assert tiny.final_lot < Decimal("5")
        large = _size(equity=Decimal("5000"))
        assert large.final_lot < Decimal("5") or large.risk_pct <= Decimal("0.50")


class TestFailClosed:
    def test_stale_market_data(self) -> None:
        stale = evaluate_market_data_firewall(
            symbol="XAUUSD",
            bid=2000.0,
            ask=2000.2,
            quote_age_seconds=200.0,
        )
        assert stale.state is MarketDataState.MARKET_DATA_STALE
        assert stale.allow_new_entry is False

    def test_abnormal_spread(self) -> None:
        loss = evaluate_loss_protection(
            DecisionEngineV1Config(),
            consecutive_losses=0,
            daily_drawdown_pct=Decimal("0"),
            spread=Decimal("9.0"),
            atr=Decimal("200"),
            price=Decimal("4000"),
        )
        assert not loss.passed
        assert not loss.spread_ok

    def test_invalid_stop_and_missing_atr(self) -> None:
        d = _size(stop_distance=Decimal("0"), atr=None)
        assert d.valid is False
        assert d.final_lot == Decimal("0")
        assert d.method == "no_stop"

    def test_invalid_lot_below_min(self) -> None:
        d = _size(
            equity=Decimal("181.53"),
            free_margin=Decimal("181.53"),
            stop_distance=Decimal("12.00"),
            atr=Decimal("12.00"),
        )
        assert d.valid is False
        assert d.final_lot == Decimal("0")
        assert d.method in {"below_min_lot", "min_lot_exceeds_risk_budget"}

    def test_insufficient_margin_cannot_force_size(self) -> None:
        d = _size(free_margin=Decimal("0.01"), mid_price=Decimal("2650"))
        assert d.final_lot < Decimal("5")
        if d.valid:
            assert d.final_lot <= Decimal("0.05")
        else:
            assert d.final_lot == Decimal("0")

    def test_broker_rejection_does_not_blind_retry(self) -> None:
        assert should_blind_retry_order_submit() is False
        unknown = classify_retry("broker_rejected")
        assert unknown["retry"] is False

    def test_mt5_disconnect_fail_closed(self) -> None:
        ctx = build_autonomous_execution_context(
            orchestrator={
                "last_cycle": {
                    "decision_action": "BUY",
                    "forwarded_to_oms": True,
                    "market_context_diagnostics": {"symbol": "XAUUSD_i"},
                }
            },
            gateway_connected=True,
            broker_connected=False,
        )
        assert ctx.mt5_status == MT5_UNAVAILABLE
        assert ctx.terminal_mode == "AUTONOMOUS_RECONCILIATION"

    def test_gateway_disconnect_fail_closed(self) -> None:
        ctx = build_autonomous_execution_context(
            orchestrator={
                "last_cycle": {
                    "decision_action": "BUY",
                    "forwarded_to_oms": True,
                    "market_context_diagnostics": {"symbol": "XAUUSD_i"},
                }
            },
            gateway_connected=False,
            broker_connected=True,
        )
        assert ctx.mt5_status == GATEWAY_UNAVAILABLE
        assert ctx.terminal_mode == "AUTONOMOUS_RECONCILIATION"

    def test_reconciliation_ambiguity_blocks_entry(self) -> None:
        plane = reset_phase_a_plane_for_tests()
        rec = plane.ambiguity.mark_unknown(
            decision_hash="abc",
            symbol="XAUUSD",
            side="BUY",
            reason="timeout_after_send",
        )
        assert rec.state.value == RECONCILIATION_REQUIRED
        gate = plane.evaluate_new_entry_gate(
            symbol="XAUUSD",
            bid=2000.0,
            ask=2000.1,
            quote_age_seconds=1.0,
        )
        assert gate["allow_new_entry"] is False

    def test_rapid_repeated_signals_do_not_duplicate(self) -> None:
        system = ScalpingAiV2()
        payload = ScalpCycleInput(
            side="buy",
            spread=Decimal("0.28"),
            atr=Decimal("4"),
            price=Decimal("2350"),
            regime="trend",
            session="london",
            trend="up",
            volatility="normal",
            liquidity_state="healthy",
            market_health="good",
            confidence=Decimal("72"),
            htf_bias="bullish",
            ltf_confirmation="bullish",
            bos=True,
            risk_engine_passed=True,
            safety_engine_passed=True,
            decision_approved=True,
            broker_connected=True,
            gateway_healthy=True,
            market_open=True,
            margin_available=True,
            equity=Decimal("10000"),
            run_state="running",
            kill_switch=False,
            execution_identity="xauusd-repeat-1",
            health={
                "execution_loop": True,
                "broker_connection": True,
                "gateway": True,
                "risk_engine": True,
                "safety_engine": True,
                "decision_engine": True,
            },
        )
        first = system.run_cycle(payload)
        second = system.run_cycle(payload)
        assert second["recommendation"] == "No Trade"
        assert any("Duplicate" in r for r in second["reasons"])
        _ = first

    def test_multiple_opportunities_still_require_threshold(self) -> None:
        weak = evaluate_from_facts(
            GoldExecutionFacts(
                symbol="XAUUSD_i",
                direction="BUY",
                opportunity_score=40,
                opportunity_threshold=OPPORTUNITY_SCORE_THRESHOLD,
            )
        )
        assert weak.opportunity_score < OPPORTUNITY_SCORE_THRESHOLD
        assert weak.eligible is False
        assert ADAPTIVE_THRESHOLD_ENABLED is False
        blocked, why = check_portfolio_sizing_limits(
            open_positions=5,
            max_open_positions=5,
            daily_loss_pct=Decimal("0"),
            max_daily_loss_pct=Decimal("3"),
            exposure_pct=Decimal("0"),
            max_exposure_pct=Decimal("10"),
        )
        assert blocked is True
        assert why is not None

    def test_no_forced_trading(self) -> None:
        from app.domain.institutional_trading.operations.fast_decision_path import (
            opportunity_window_snapshot,
            reset_fast_decision_path,
        )

        reset_fast_decision_path()
        snap = opportunity_window_snapshot()
        assert snap["forces_trades"] is False
        pipeline = (
            ROOT / "app/application/services/institutional_decision_pipeline.py"
        ).read_text(encoding="utf-8")
        assert "FORCE_FIRST_TRADE" not in pipeline
        assert "ALLOW_RISK_LOCK_OVERRIDE" not in pipeline


class TestLatencyAliases:
    def test_decision_to_oms_and_total(self) -> None:
        budget = LatencyBudget(
            market_ms=12.0,
            decision_to_risk_ms=3.0,
            risk_to_safety_ms=2.0,
            safety_to_plan_ms=1.0,
            plan_to_oms_ms=4.0,
            oms_to_gateway_ms=5.0,
            gateway_to_broker_ms=6.0,
        )
        payload = budget.to_dict()
        assert payload["decision_to_oms_ms"] == 10.0
        assert payload["oms_to_broker_ms"] == 11.0
        assert payload["total_execution_latency_ms"] == payload["total_cycle_ms"]

    def test_trade_timeline_spans(self) -> None:
        row = {
            "request_id": "r1",
            "signal_at": datetime(2026, 8, 26, 16, 0, 0, tzinfo=UTC),
            "decision_at": datetime(2026, 8, 26, 16, 0, 0, 12_000, tzinfo=UTC),
            "oms_at": datetime(2026, 8, 26, 16, 0, 0, 22_000, tzinfo=UTC),
            "submitted_at": datetime(2026, 8, 26, 16, 0, 0, 22_000, tzinfo=UTC),
            "broker_ack_at": datetime(2026, 8, 26, 16, 0, 0, 33_000, tzinfo=UTC),
            "filled_at": datetime(2026, 8, 26, 16, 0, 0, 40_000, tzinfo=UTC),
        }
        timeline = _trade_timeline(row)
        assert timeline["signal_to_decision_ms"] == 12.0
        assert timeline["decision_to_oms_ms"] == 10.0
        assert timeline["oms_to_broker_ms"] == 11.0
        assert timeline["total_execution_latency_ms"] == 18.0
