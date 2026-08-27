"""UTC daily-loss latch — accurate session, auto re-arm under cap.

Does not raise max_daily_loss_pct, bypass Risk, or send orders.
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
    assert utc_daily_loss_exceeded(
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=Decimal("3.0"),
    )
    assert not utc_daily_loss_exceeded(
        daily_pnl=Decimal("0"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=Decimal("3.0"),
    )


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
        daily_pnl=Decimal("-25.11"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=Decimal("3.0"),
        trusted=True,
    )
    assert plane.daily_loss_exceeded is True
    assert armed["daily_loss_exceeded"] is True
    assert armed["daily_loss_limit_pct"] == "3.0"
    cleared = sync_utc_daily_loss_lock(
        plane,
        daily_pnl=Decimal("0"),
        equity=Decimal("165.13"),
        balance=Decimal("165.13"),
        max_daily_loss_pct=Decimal("3.0"),
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
        max_daily_loss_pct=Decimal("3.0"),
        trusted=False,
    )
    assert out["daily_loss_exceeded"] is True
    assert out["source"] == "fail_closed"
    assert plane.daily_loss_exceeded is True


def test_cap_unchanged() -> None:
    assert AiScalpingConfig().allow_martingale is False
    from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG

    assert DEFAULT_ITE_CONFIG.max_daily_loss_pct == Decimal("3.0")
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
            "detail": "daily loss 15.21% exceeds 3.0%",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "SAFETY",
                "reason_code": "SAFETY_BLOCKED",
                "human_reason": "AutoTrading is disabled in MetaTrader 5",
            },
            "market_context_diagnostics": {
                "daily_loss_exceeded": True,
                "daily_loss_pct": "15.21",
                "daily_loss_limit_pct": "3.0",
            },
        },
    )
    assert over["first_blocker"] == "DAILY_LOSS_BLOCK"
    assert over["pipeline"]["final_decision"] == "TAKE"
    assert over["pipeline"]["risk"] == "BLOCK"
    assert over["pipeline"]["safety"] == "NOT_REACHED"
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["broker"] != "BLOCK"
    assert over["daily_loss_pct"] == "15.21"


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
            risk_reasons=("daily loss 15.21% exceeds 3.0%",),
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
            risk_reasons=("daily loss 15.21% exceeds 3.0%",),
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
    assert bridge_abort_stage("daily loss 15.21% exceeds 3.0%") == "RISK"


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
        max_daily_loss_pct=Decimal("3.0"),
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
