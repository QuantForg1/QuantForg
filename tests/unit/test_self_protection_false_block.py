"""False SELF_PROTECTION must not latch a valid XAUUSD TAKE.

Does not send live orders. Does not lower Opportunity 70, Sniper, Risk 40%,
or max positions. Does not convert WAIT into TAKE.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
)
from app.domain.institutional_trading.ai_scalping.live_health import (
    LiveHealthMonitor,
    get_live_health_monitor,
)
from app.domain.institutional_trading.config import MAX_DAILY_LOSS_PCT
from app.domain.institutional_trading.decision_models import TradeDirection
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.models import (
    BridgeAbortReason,
    ExecutionMode,
)
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
    build_execution_handoff,
)
from app.domain.institutional_trading.phase_a.plane import reset_phase_a_plane_for_tests
from tests.unit.test_institutional_trading_phase_c import (
    _account,
    _bridge,
    _buy_decision,
    _ctx,
    _sell_decision,
)
from tests.unit.test_xauusd_sniper_v2_lifecycle import _dir, _sniper, _snap

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def test_valid_take_with_hwm_drawdown_reaches_oms() -> None:
    """Lifetime peak 4% above equity is not a Safety latch. Risk 40% still owns loss."""
    decision, snap, acct = _sell_decision()
    acct = _account(equity=Decimal("9600"), peak_equity=Decimal("10000"))
    oms = RecordingOmsPort()
    get_live_health_monitor().reset()
    reset_phase_a_plane_for_tests()
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.abort_reason is not BridgeAbortReason.SELF_PROTECTION
    assert oms.calls, f"expected OMS submit, abort={result.abort_reason}"


def test_stale_hwm_drawdown_and_spread_record_do_not_permanently_block() -> None:
    mon = LiveHealthMonitor()
    mon.record_drawdown(Decimal("8.50"))
    mon.record_abnormal_spread("spread wide vs history")
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is True
    assert why == "ok"
    snap = mon.snapshot()
    assert snap["allow_new_entries"] is True
    assert snap["block_reason"] is None


def test_expired_emergency_rearms_without_execute_now() -> None:
    mon = LiveHealthMonitor(emergency_window_seconds=30)
    mon.record_flash_move("Flash crash protection")
    assert mon.allow_new_entries()[0] is False
    mon._emergencies.clear()
    ok, why = mon.allow_new_entries()
    assert ok is True
    assert why == "ok"


def test_genuine_kill_switch_is_safety_block() -> None:
    decision, snap, acct = _buy_decision()
    oms = RecordingOmsPort()
    integ = _bridge(oms, mode=ExecutionMode.LIVE)
    integ.bridge.kill_switch.arm()
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.abort_reason is BridgeAbortReason.KILL_SWITCH
    assert oms.calls == []
    assert bridge_abort_stage("KILL_SWITCH") == "SAFETY"
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "BUY",
                "signal_action": "BUY",
                "reject": False,
                "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
            }
        ),
        {
            "forwarded_to_oms": False,
            "abort_reason": "KILL_SWITCH",
            "mt5_ticket": None,
        },
    )
    assert over["pipeline"]["safety"] == "BLOCK"
    assert over["pipeline"]["oms"] == "NOT_REACHED"


def test_genuine_gateway_disconnect_is_safety_block() -> None:
    decision, snap, acct = _buy_decision()
    oms = RecordingOmsPort()
    get_live_health_monitor().reset()
    get_live_health_monitor().update_dependencies(gateway_ok=False)
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    ctx = _ctx(decision, snap, acct)
    object.__setattr__(ctx, "gateway_connected", False)
    object.__setattr__(ctx, "connected", False)
    result = integ.execute(decision, ctx)
    assert result.abort_reason is BridgeAbortReason.SELF_PROTECTION
    assert oms.calls == []
    comment = str(getattr(getattr(result, "journal_entry", None), "comment", "") or "")
    assert "gateway" in comment.lower() or "critical" in comment.lower()


def test_latency_failure_is_execution_health_not_generic_safety() -> None:
    decision, snap, acct = _buy_decision()
    oms = RecordingOmsPort()
    get_live_health_monitor().reset()
    get_live_health_monitor().update_dependencies(latency_ms=5000.0)
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(mode=ExecutionMode.LIVE, decision_ttl_seconds=30),
    )
    result = integ.execute(decision, _ctx(decision, snap, acct))
    assert result.abort_reason is BridgeAbortReason.HEALTH_DEGRADED
    assert oms.calls == []
    assert bridge_abort_stage("HEALTH_DEGRADED") == "EXECUTION_HEALTH"
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "BUY",
                "signal_action": "BUY",
                "reject": False,
                "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
            }
        ),
        {
            "forwarded_to_oms": False,
            "abort_reason": "HEALTH_DEGRADED",
            "detail": "New entries paused: critical:latency",
            "mt5_ticket": None,
        },
    )
    assert over["pipeline"]["safety"] == "READY"
    assert over["pipeline"]["execution_stage"] == "EXECUTION_HEALTH"
    assert over["pipeline"]["oms"] == "NOT_REACHED"


def test_reject_burst_is_not_infrastructure_health() -> None:
    mon = LiveHealthMonitor(reject_burst_threshold=3, reject_window_seconds=120)
    mon.record_reject(symbol="XAUUSD_I")
    mon.record_reject(symbol="XAUUSD_I")
    mon.record_reject(symbol="XAUUSD_I")
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is False
    assert "EXECUTION_REJECT_BURST" in why
    assert mon.snapshot()["health"]["all_ok"] is True
    over = _overlay_last_ite_cycle(
        _row_from_score(
            {
                "symbol": "XAUUSD_I",
                "direction": "SELL",
                "signal_action": "SELL",
                "reject": False,
                "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
            }
        ),
        {
            "forwarded_to_oms": False,
            "abort_reason": "SELF_PROTECTION",
            "detail": why,
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "SAFETY",
                "reason_code": "SELF_PROTECTION",
                "human_reason": why,
            },
        },
    )
    assert over["first_blocker"] == "EXECUTION_REJECT_BURST"
    assert over["pipeline"]["safety"] == "READY"
    assert over["pipeline"]["blocker_category"] == "EXECUTION_REJECT_BURST"


def test_unset_monitor_allows_new_entries() -> None:
    mon = LiveHealthMonitor()
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is True
    assert why == "ok"
    get_live_health_monitor().reset()
    ok2, _ = get_live_health_monitor().allow_new_entries()
    assert ok2 is True


def test_recovered_gateway_allows_without_execute_now() -> None:
    mon = LiveHealthMonitor()
    mon.update_dependencies(gateway_ok=False)
    assert mon.allow_new_entries()[0] is False
    mon.update_dependencies(
        gateway_ok=True,
        broker_ok=True,
        mt5_ok=True,
        oms_ok=True,
        market_data_ok=True,
        latency_ms=40,
    )
    ok, why = mon.allow_new_entries(symbol="XAUUSD_I")
    assert ok is True
    assert why == "ok"


def test_daily_loss_40_percent_still_enforced() -> None:
    assert MAX_DAILY_LOSS_PCT == Decimal("40.0")
    assert bridge_abort_stage("DAILY_LOSS_BLOCK") == "RISK"


def test_max_positions_two_and_winner_only_scale_in_preserved() -> None:
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.max_positions_per_symbol == 2
    assert cfg.pyramid_winners_only is True
    assert cfg.allow_martingale is False
    assert cfg.max_open_trades >= 2


def test_take_without_oms_forward_is_not_executed() -> None:
    handoff = build_execution_handoff(take=True, forwarded_to_oms=False)
    assert handoff["execution_confirmed"] is False
    assert handoff["oms_entered"] is False


def test_oms_forward_without_ticket_is_not_executed() -> None:
    handoff = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=None
    )
    assert handoff["execution_confirmed"] is False


def test_real_ticket_required_for_executed() -> None:
    handoff = build_execution_handoff(
        take=True, forwarded_to_oms=True, mt5_ticket=424242
    )
    assert handoff["execution_confirmed"] is True
    assert handoff["oms_entered"] is True


def test_wait_paths_remain_wait() -> None:
    out = _sniper(_snap(), _dir(TradeDirection.NONE, buy=16, sell=18))
    assert out.passed is False
    assert out.action == "WAIT"
    wait_fvg = _sniper(
        _snap(),
        _dir(TradeDirection.SELL, buy=16, sell=42),
        momentum=0,
        pa_score=20,
        min_momentum=65,
    )
    assert wait_fvg.action == "WAIT"
    assert wait_fvg.passed is False
