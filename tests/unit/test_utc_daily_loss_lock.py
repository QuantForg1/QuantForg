"""UTC daily-loss latch — accurate session, auto re-arm under cap.

Does not bypass Risk or send orders. Cap is ITE MAX_DAILY_LOSS_PCT (40.0).
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.config import (
    DEFAULT_ITE_CONFIG,
    MAX_DAILY_LOSS_PCT,
    coerce_max_daily_loss_pct,
)
from app.domain.institutional_trading.operations.daily_loss_lock import (
    sync_utc_daily_loss_lock,
    utc_daily_loss_exceeded,
    utc_daily_loss_pct,
    utc_daily_loss_resets_at,
    utc_session_day,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.gold_execution_readiness import (
    StageStatus,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_utc_session_day_is_iso_date() -> None:
    assert utc_session_day(datetime(2026, 8, 27, 23, 59, tzinfo=UTC)) == "2026-08-27"
    assert utc_session_day(datetime(2026, 8, 28, 0, 0, tzinfo=UTC)) == "2026-08-28"


def test_utc_loss_pct_matches_risk_engine_balance_base() -> None:
    pct = utc_daily_loss_pct(
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
    )
    assert pct == Decimal("15.21")
    cap = DEFAULT_ITE_CONFIG.max_daily_loss_pct
    assert cap == MAX_DAILY_LOSS_PCT == Decimal("40.0")
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=cap,
    )
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("0"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=cap,
    )


def test_daily_loss_boundary_3999_4000_4001() -> None:
    """Existing convention: block only when pct > cap (40.00% is still under)."""
    cap = MAX_DAILY_LOSS_PCT
    base = Decimal("100")
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("-39.99"),
        equity=base,
        balance=base,
        max_daily_loss_pct=cap,
    )
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("-40.00"),
        equity=base,
        balance=base,
        max_daily_loss_pct=cap,
    )
    assert utc_daily_loss_exceeded(
        daily_pnl=Decimal("-40.01"),
        equity=base,
        balance=base,
        max_daily_loss_pct=cap,
    )


def test_authoritative_cap_rejects_above_40() -> None:
    assert coerce_max_daily_loss_pct(Decimal("40.0")) == Decimal("40.0")
    with pytest.raises(ValueError, match=r"\(0, 40.0\]"):
        coerce_max_daily_loss_pct(Decimal("40.01"))
    with pytest.raises(ValueError, match=r"\(0, 40.0\]"):
        coerce_max_daily_loss_pct(Decimal("0"))


def test_lock_arms_when_utc_day_exceeds_and_clears_when_under() -> None:
    plane = SimpleNamespace(
        daily_loss_exceeded=False,
        flag_daily_loss=lambda now=None: setattr(plane, "daily_loss_exceeded", True),
        clear_daily_loss=lambda now=None, reason="": (
            setattr(plane, "daily_loss_exceeded", False) or True
        ),
    )
    armed = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("-40.01"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
    )
    assert plane.daily_loss_exceeded is True
    assert armed["daily_loss_exceeded"] is True
    assert armed["daily_loss_limit_pct"] == "40.0"
    cleared = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("0"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
        now=datetime(2026, 8, 28, 0, 1, tzinfo=UTC),
    )
    assert plane.daily_loss_exceeded is False
    assert cleared["daily_loss_exceeded"] is False
    assert cleared["lock_changed"] is True
    assert cleared["daily_loss_session_day"] == "2026-08-28"


def test_untrusted_deals_fail_closed_do_not_clear() -> None:
    plane = SimpleNamespace(
        daily_loss_exceeded=True,
        flag_daily_loss=lambda now=None: None,
        clear_daily_loss=lambda **k: False,
    )
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("0"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=False,
    )
    assert out["daily_loss_exceeded"] is True
    assert out["source"] == "fail_closed"
    assert plane.daily_loss_exceeded is True


def test_untrusted_deals_do_not_arm_durable_latch() -> None:
    plane = SimpleNamespace(
        daily_loss_exceeded=False,
        flag_daily_loss=lambda now=None: setattr(plane, "daily_loss_exceeded", True),
        clear_daily_loss=lambda **k: False,
    )
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("-99"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=False,
    )
    assert out["daily_loss_exceeded"] is True
    assert out["source"] == "fail_closed"
    assert plane.daily_loss_exceeded is False


def test_cap_unchanged() -> None:
    assert AiScalpingConfig().allow_martingale is False
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

    assert DEFAULT_ITE_CONFIG.max_daily_loss_pct == Decimal("40.0")
    resets = utc_daily_loss_resets_at(datetime(2026, 8, 27, 14, 0, tzinfo=UTC))
    assert resets.startswith("2026-08-28T00:00:00")


def test_overlay_daily_loss_is_risk_not_safety_or_broker() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 68,
            "ai_confidence": 58,
            "opportunity_score": 71,
            "opportunity_threshold": 70,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "SAFETY_BLOCKED",
            "detail": "daily loss 40.01% exceeds 40.0%",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "SAFETY",
                "reason_code": "SAFETY_BLOCKED",
                "human_reason": "AutoTrading is disabled in MetaTrader 5",
            },
            "market_context_diagnostics": {
                "daily_loss_exceeded": True,
                "daily_loss_pct": "40.01",
                "daily_loss_limit_pct": "40.0",
            },
        },
    )
    assert over["first_blocker"] == "DAILY_LOSS_BLOCK"
    assert over["pipeline"]["final_decision"] == "TAKE"
    assert over["pipeline"]["risk"] == "BLOCK"
    assert over["pipeline"]["safety"] == "NOT_REACHED"
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["broker"] != "BLOCK"
    assert over["daily_loss_pct"] == "40.01"


def test_gold_contract_daily_loss_is_risk_wait() -> None:
    out = evaluate_gold_execution_contract(
        GoldExecutionFacts(
            symbol="XAUUSD_I",
            direction="SELL",
            action="SELL",
            market_open=True,
            tradable=True,
            candles_ok=True,
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            quote_age_seconds=1.0,
            spread=Decimal("0.20"),
            structure_score=70,
            momentum_score=65,
            quality=80,
            confidence=75,
            pa_confluence=55,
            risk_reward=Decimal("1.20"),
            market_regime="TREND",
            volatility_ok=True,
            session_quality_ok=True,
            safety_allowed=True,
            kill_switch=False,
            execution_enabled=True,
            auto_running=True,
            account_leverage=Decimal("2000"),
            risk_eligible=False,
            risk_reasons=("daily loss 40.01% exceeds 40.0%",),
            approved_lots=Decimal("0"),
            min_lot_infeasible=False,
            portfolio_allow=True,
            optimizer_state="EXECUTE_NOW",
            oms_orders_allowed=True,
            gateway_connected=True,
            broker_connected=True,
            gold_only=True,
            opportunity_score=80,
            opportunity_threshold=70,
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "DAILY_LOSS_BLOCK"
    assert out.blocking_stage == "RISK"
    assert out.next_action == CandidateAction.WAIT_SAME_FOCUS.value
    assert out.stages["RISK"] == StageStatus.BLOCK.value
    assert out.stages["OMS"] == StageStatus.NOT_REACHED.value


def test_gold_contract_latch_alone_is_daily_loss_block() -> None:
    out = evaluate_gold_execution_contract(
        GoldExecutionFacts(
            symbol="XAUUSD_I",
            direction="SELL",
            action="SELL",
            market_open=True,
            tradable=True,
            candles_ok=True,
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            quote_age_seconds=1.0,
            spread=Decimal("0.20"),
            structure_score=70,
            momentum_score=65,
            quality=80,
            confidence=75,
            pa_confluence=55,
            risk_reward=Decimal("1.20"),
            market_regime="TREND",
            volatility_ok=True,
            session_quality_ok=True,
            safety_allowed=True,
            kill_switch=False,
            execution_enabled=True,
            auto_running=True,
            account_leverage=Decimal("2000"),
            risk_eligible=True,
            approved_lots=Decimal("0.01"),
            min_lot_infeasible=False,
            portfolio_allow=True,
            optimizer_state="EXECUTE_NOW",
            oms_orders_allowed=True,
            gateway_connected=True,
            broker_connected=True,
            gold_only=True,
            opportunity_score=80,
            opportunity_threshold=70,
            daily_loss_exceeded=True,
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "DAILY_LOSS_BLOCK"
    assert out.blocking_stage == "RISK"


def test_kill_switch_still_outranks_daily_loss() -> None:
    out = evaluate_gold_execution_contract(
        GoldExecutionFacts(
            symbol="XAUUSD_I",
            direction="SELL",
            action="SELL",
            market_open=True,
            tradable=True,
            candles_ok=True,
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            quote_age_seconds=1.0,
            spread=Decimal("0.20"),
            structure_score=70,
            momentum_score=65,
            quality=80,
            confidence=75,
            pa_confluence=55,
            risk_reward=Decimal("1.20"),
            market_regime="TREND",
            volatility_ok=True,
            session_quality_ok=True,
            safety_allowed=True,
            kill_switch=True,
            execution_enabled=True,
            auto_running=True,
            account_leverage=Decimal("2000"),
            risk_eligible=False,
            risk_reasons=("daily loss 40.01% exceeds 40.0%",),
            approved_lots=Decimal("0"),
            gold_only=True,
            opportunity_score=80,
            opportunity_threshold=70,
            oms_orders_allowed=True,
            gateway_connected=True,
            broker_connected=True,
            optimizer_state="EXECUTE_NOW",
        )
    )
    assert out.may_submit_oms is False
    assert out.blocking_stage == "SAFETY"
    assert "kill" in (out.fault_reason or "").lower()


def test_buy_sell_independent_and_no_martingale_scale_in() -> None:
    buy = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "trade_quality": 80,
            "ai_confidence": 78,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "BUY"},
        }
    )
    sell = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 80,
            "ai_confidence": 78,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL"},
        }
    )
    assert buy["pipeline"]["final_decision"] == "TAKE"
    assert sell["pipeline"]["final_decision"] == "TAKE"
    loser = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("SELL",),
        open_profits=(Decimal("-12.5"),),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=5,
    )
    assert loser.allow is False
    assert AiScalpingConfig().allow_martingale is False


def test_bridge_abort_daily_loss_is_risk() -> None:
    assert bridge_abort_stage("DAILY_LOSS_BLOCK") == "RISK"
    assert bridge_abort_stage("daily loss 40.01% exceeds 40.0%") == "RISK"


def test_wait_not_converted_when_daily_loss_latch_is_set() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "WAIT",
            "signal_action": "WAIT",
            "reject": True,
            "sniper_entry": {"passed": False, "action": "WAIT"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": None,
            "market_context_diagnostics": {"daily_loss_exceeded": True},
        },
    )
    assert over["pipeline"]["final_decision"] == "WAIT"
    assert over.get("first_blocker") != "DAILY_LOSS_BLOCK"


def test_cleared_lock_rearms_auto_without_restart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.domain.institutional_trading.operations.control_plane import (
        OperationsControlPlane,
    )
    from app.domain.institutional_trading.operations.models import OpsExecutionMode

    plane = OperationsControlPlane()
    plane.mode = OpsExecutionMode.LIVE
    plane.auto_trading_run_state = "paused"
    plane.auto_trading_enabled = True
    plane.kill_switch_armed = False
    plane.daily_loss_exceeded = True
    plane.audit.record = lambda **_: None  # type: ignore[method-assign]
    resumed: dict[str, bool] = {}

    def _resume(target: object, **kwargs: object) -> dict[str, object]:
        resumed["called"] = True
        setattr(target, "auto_trading_run_state", "running")
        setattr(target, "auto_trading_enabled", True)
        return {"resumed": True, "reason": kwargs.get("reason")}

    monkeypatch.setattr(
        "app.application.services.auto_trading_continuity.ensure_auto_trading_running",
        _resume,
    )
    sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("0"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
        now=datetime(2026, 8, 28, 0, 1, tzinfo=UTC),
    )
    assert plane.daily_loss_exceeded is False
    assert plane.kill_switch_armed is False
    assert resumed.get("called") is True
    assert plane.auto_trading_run_state == "running"


def test_winner_only_scale_in_and_capacity_cap() -> None:
    winner = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("SELL",),
        open_profits=(Decimal("12.5"),),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=5,
    )
    assert winner.allow is True
    full = may_add_scalping_trade(
        open_positions=2,
        max_open=2,
        new_confidence=99,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("SELL", "SELL"),
        open_profits=(Decimal("12.5"), Decimal("4.0")),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=5,
    )
    assert full.allow is False


def test_decision_to_mt5_handoff_does_not_require_execute_now() -> None:
    out = evaluate_gold_execution_contract(
        GoldExecutionFacts(
            symbol="XAUUSD_I",
            direction="SELL",
            action="SELL",
            market_open=True,
            tradable=True,
            candles_ok=True,
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            quote_age_seconds=1.0,
            spread=Decimal("0.20"),
            structure_score=70,
            momentum_score=65,
            quality=80,
            confidence=75,
            pa_confluence=55,
            risk_reward=Decimal("1.20"),
            market_regime="TREND",
            volatility_ok=True,
            session_quality_ok=True,
            safety_allowed=True,
            kill_switch=False,
            execution_enabled=True,
            auto_running=True,
            account_leverage=Decimal("2000"),
            risk_eligible=True,
            approved_lots=Decimal("0.01"),
            min_lot_infeasible=False,
            portfolio_allow=True,
            optimizer_state="EXECUTE_NOW",
            oms_orders_allowed=True,
            gateway_connected=True,
            broker_connected=True,
            gold_only=True,
            opportunity_score=80,
            opportunity_threshold=70,
        )
    )
    assert out.may_submit_oms is True
    assert out.execute_now_required is False
    assert out.fault_code == "NONE"
    assert out.stages["OMS"] == StageStatus.PASS.value
    assert out.stages["BROKER"] == StageStatus.PASS.value


def _live_safety_facts(**overrides: object) -> AutoTradeLiveFacts:
    from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts

    payload: dict[str, object] = {
        "gateway_connected": True,
        "broker_connected": True,
        "market_data_live": True,
        "risk_engine_pass": True,
        "account_trading_enabled": True,
        "mt5_autotrading_enabled": True,
        "symbol": "XAUUSD_I",
        "symbol_tradable": True,
        "margin_available": True,
        "no_broker_restrictions": True,
        "open_positions": 0,
        "session": "london",
        "broker_session_open": True,
        "spread": Decimal("0.20"),
        "news_blocked": False,
        "daily_loss_exceeded": False,
        "emergency_stop": False,
        "ops_mode": "LIVE",
        "execution_enabled": True,
    }
    payload.update(overrides)
    return AutoTradeLiveFacts(**payload)  # type: ignore[arg-type]


def test_daily_loss_keeps_scanning_mt5_autotrading_is_safety() -> None:
    from app.domain.institutional_trading.auto_trading import (
        AutoTradePolicy,
        evaluate_auto_trade_safety,
        safety_blocks_decision,
    )

    policy = AutoTradePolicy(enabled=True, run_state="running")
    daily = evaluate_auto_trade_safety(
        policy, _live_safety_facts(daily_loss_exceeded=True)
    )
    assert daily.allowed is False
    assert safety_blocks_decision(daily) is False
    assert any("daily loss" in r.lower() for r in daily.failed_reasons)

    still_over = sync_utc_daily_loss_lock(
        SimpleNamespace(
            daily_loss_exceeded=True,
            flag_daily_loss=lambda now=None: None,
            clear_daily_loss=lambda **k: False,
        ),
        daily_pnl=Decimal("-40.01"),
        equity=Decimal("100"),
        balance=Decimal("100"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
        floating_pnl=Decimal("0"),
    )
    assert still_over["daily_loss_exceeded"] is True
    assert still_over["daily_loss_lock"] == "EXCEEDED"
    assert still_over["daily_loss_base"] == "balance"
    assert still_over["rearm_state"] == "LOCKED"
    assert still_over["history_confidence"] == "trusted"

    at = evaluate_auto_trade_safety(
        policy, _live_safety_facts(mt5_autotrading_enabled=False)
    )
    assert at.allowed is False
    assert safety_blocks_decision(at) is True
    assert any("AutoTrading is disabled" in r for r in at.failed_reasons)


def test_take_handoff_is_not_executed_without_ticket() -> None:
    from app.domain.institutional_trading.operations.execution_chain_log import (
        build_execution_handoff,
        bridge_abort_stage,
    )

    handoff = build_execution_handoff(
        take=True,
        abort_reason="DAILY_LOSS_BLOCK",
        blocking_stage="RISK",
        forwarded_to_oms=False,
        mt5_ticket=None,
    )
    assert handoff["decision_take"] is True
    assert handoff["risk_entered"] is True
    assert handoff["risk_passed"] is False
    assert handoff["execution_confirmed"] is False
    assert handoff["mt5_ticket"] is None
    assert handoff["terminal_reason"] == "DAILY_LOSS_BLOCK"
    assert bridge_abort_stage("DAILY_LOSS_BLOCK") == "RISK"

    filled = build_execution_handoff(
        take=True,
        forwarded_to_oms=True,
        mt5_ticket=123456,
    )
    assert filled["oms_forwarded"] is True
    assert filled["execution_confirmed"] is True


def test_kill_switch_blocks_decision_ahead_of_daily_loss() -> None:
    from app.domain.institutional_trading.auto_trading import (
        AutoTradePolicy,
        evaluate_auto_trade_safety,
        safety_blocks_decision,
    )

    mixed = evaluate_auto_trade_safety(
        AutoTradePolicy(enabled=True, run_state="running"),
        _live_safety_facts(daily_loss_exceeded=True, emergency_stop=True),
    )
    assert safety_blocks_decision(mixed) is True
    assert mixed.allowed is False


def _sell_take_facts(**overrides: object) -> GoldExecutionFacts:
    base: dict[str, object] = {
        "symbol": "XAUUSD_I",
        "direction": "SELL",
        "action": "SELL",
        "market_open": True,
        "tradable": True,
        "candles_ok": True,
        "bid": Decimal("2400.10"),
        "ask": Decimal("2400.30"),
        "quote_age_seconds": 1.0,
        "spread": Decimal("0.20"),
        "structure_score": 70,
        "momentum_score": 65,
        "quality": 80,
        "confidence": 75,
        "pa_confluence": 55,
        "risk_reward": Decimal("1.20"),
        "market_regime": "TREND",
        "volatility_ok": True,
        "session_quality_ok": True,
        "safety_allowed": True,
        "kill_switch": False,
        "execution_enabled": True,
        "auto_running": True,
        "account_leverage": Decimal("2000"),
        "risk_eligible": True,
        "approved_lots": Decimal("0.01"),
        "min_lot_infeasible": False,
        "portfolio_allow": True,
        "optimizer_state": "EXECUTE_NOW",
        "oms_orders_allowed": True,
        "gateway_connected": True,
        "broker_connected": True,
        "gold_only": True,
        "opportunity_score": 80,
        "opportunity_threshold": 70,
    }
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


def test_wait_opportunity_is_not_relabeled_daily_loss() -> None:
    """Score 69 is WAIT. Daily-loss lock stays in diagnostics, not the abort."""
    out = evaluate_gold_execution_contract(
        _sell_take_facts(opportunity_score=69, daily_loss_exceeded=True)
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "OPPORTUNITY_SCORE_BELOW_THRESHOLD"
    assert out.blocking_stage != "RISK" or out.fault_code != "DAILY_LOSS_BLOCK"
    assert "DAILY_LOSS_BLOCK" not in (out.fault_code or "")


def test_direction_none_is_not_relabeled_daily_loss() -> None:
    out = evaluate_gold_execution_contract(
        _sell_take_facts(
            direction="NONE",
            action="NO_TRADE",
            daily_loss_exceeded=True,
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "DIRECTION_NONE"


def test_take_daily_loss_outranks_min_lot() -> None:
    out = evaluate_gold_execution_contract(
        _sell_take_facts(
            daily_loss_exceeded=True,
            min_lot_infeasible=True,
            approved_lots=Decimal("0"),
            risk_eligible=False,
            risk_reasons=(
                "MIN_LOT_INFEASIBLE",
                "daily loss 40.01% exceeds 40.0%",
            ),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "DAILY_LOSS_BLOCK"
    assert out.blocking_stage == "RISK"
    assert out.stages["OMS"] == StageStatus.NOT_REACHED.value


def test_mt5_autotrading_safety_not_relabeled_daily_loss() -> None:
    out = evaluate_gold_execution_contract(
        _sell_take_facts(
            safety_allowed=False,
            safety_reasons=("AutoTrading is disabled in MetaTrader 5",),
            daily_loss_exceeded=True,
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "SAFETY_BLOCKED"
    assert out.blocking_stage == "SAFETY"
    assert "autotrading" in (out.fault_reason or "").lower()


def test_take_under_cap_may_reach_oms_without_ticket() -> None:
    """TAKE + Risk PASS can authorize OMS. Ticket is still required for EXECUTED."""
    out = evaluate_gold_execution_contract(_sell_take_facts(daily_loss_exceeded=False))
    assert out.may_submit_oms is True
    assert out.fault_code == "NONE"
    assert out.stages["RISK"] == StageStatus.PASS.value
    assert out.stages["SAFETY"] == StageStatus.PASS.value
    handoff = __import__(
        "app.domain.institutional_trading.operations.execution_chain_log",
        fromlist=["build_execution_handoff"],
    ).build_execution_handoff(
        take=True,
        forwarded_to_oms=True,
        mt5_ticket=None,
    )
    assert handoff["oms_forwarded"] is True
    assert handoff["execution_confirmed"] is False
    assert handoff["mt5_ticket"] is None


def test_live_15_21_percent_clears_under_40_cap() -> None:
    plane = SimpleNamespace(
        daily_loss_exceeded=True,
        flag_daily_loss=lambda now=None: None,
        clear_daily_loss=lambda now=None, reason="": (
            setattr(plane, "daily_loss_exceeded", False) or True
        ),
    )
    out = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=MAX_DAILY_LOSS_PCT,
        trusted=True,
    )
    assert out["daily_loss_pct"] == "15.21"
    assert out["daily_loss_limit_pct"] == "40.0"
    assert out["daily_loss_exceeded"] is False
    assert out["daily_loss_lock"] == "CLEAR"
    assert out["rearm_state"] == "REARMED"
    assert plane.daily_loss_exceeded is False


def test_operator_cannot_set_daily_loss_above_hard_cap() -> None:
    from uuid import uuid4

    from app.domain.institutional_trading.operations.control_plane import (
        OperationsControlPlane,
    )
    from app.domain.institutional_trading.operations.models import OperatorIdentity

    plane = OperationsControlPlane()
    op = OperatorIdentity(
        user_id=uuid4(),
        role="owner",
        display_name="Daily Loss Cap Tester",
    )
    with pytest.raises(ValueError, match=r"\(0, 40.0\]"):
        plane.update_auto_trade_controls(
            op,
            max_daily_loss_pct=Decimal("40.01"),
            reason="reject above hard cap",
        )
    policy = plane.update_auto_trade_controls(
        op,
        max_daily_loss_pct=Decimal("40.0"),
        reason="set hard cap",
    )
    assert policy.max_daily_loss_pct == Decimal("40.0")
