"""XAUUSD sniper position capacity + execution lifecycle.

Cap stays at 2 per symbol. Does not send orders, raise risk, or force trades.
"""

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.application.services.mt5_position_truth import (
    apply_mt5_position_truth,
    force_sync_positions,
)
from app.application.services.signal_center_service import (
    _overlay_last_ite_cycle,
    _row_from_score,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.ai_scalping.config import AiScalpingConfig
from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
    may_add_scalping_trade,
)
from app.domain.institutional_trading.ai_scalping.portfolio_risk_engine_v2 import (
    BrokerComplianceSpec,
    build_portfolio_book,
    evaluate_portfolio_allocation,
)
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.operations.execution_chain_log import (
    bridge_abort_stage,
    execution_blocked_event,
)
from app.domain.institutional_trading.operations.fast_decision_path import (
    CandidateAction,
    DecisionState,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.gold_execution_readiness import (
    StageStatus,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
    count_quantforg_positions,
    live_capacity_tickets,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_BROKER = BrokerComplianceSpec(
    min_lot=Decimal("0.01"),
    lot_step=Decimal("0.01"),
    max_lot=Decimal("50"),
    contract_size=Decimal("100"),
)


def _account(*, open_n: int = 0) -> AccountRiskState:
    return AccountRiskState(
        equity=Decimal("5000"),
        balance=Decimal("5000"),
        free_margin=Decimal("5000"),
        open_positions=open_n,
    )


def _gold(
    ticket: int,
    *,
    side: str = "sell",
    profit: Decimal = Decimal("12"),
    volume: Decimal = Decimal("0.01"),
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol="XAUUSD_i",
        side=side,
        volume=volume,
        open_price=Decimal("4000"),
        current_price=Decimal("3995") if side == "sell" else Decimal("4005"),
        profit=profit,
        magic=QUANTFORG_MAGIC,
        comment="ite:v1:cap",
    )


def _alloc(*, positions: list[MT5Position] | None, open_n: int, direction: str = "SELL"):
    return evaluate_portfolio_allocation(
        account=_account(open_n=open_n),
        symbol="XAUUSD",
        stop_distance=Decimal("1.20"),
        positions=positions,
        new_direction=direction,
        new_confidence=80,
        quality_score=90,
        confidence=88,
        quality_reject=False,
        opportunity_score=75,
        sniper_passed=True,
        broker=_BROKER,
        config=AiScalpingConfig(max_positions_per_symbol=2, max_open_trades=10),
        log=False,
    )


def _ready(**overrides: object) -> GoldExecutionFacts:
    base = dict(
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
        force_shadow=False,
        gold_only=True,
        opportunity_score=80,
        opportunity_threshold=70,
    )
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


class _FakeAdapter:
    def __init__(self, rows: list[MT5Position]) -> None:
        self._rows = list(rows)
        self.client = SimpleNamespace(
            invalidate_positions_cache=lambda: None,
        )

    def list_positions(self) -> list[MT5Position]:
        return list(self._rows)


def test_zero_of_two_valid_take_reaches_risk_not_capacity_block() -> None:
    alloc = _alloc(positions=[], open_n=0)
    reason = alloc.rejection_reason or ""
    assert "MAX_POSITIONS_REACHED" not in reason
    assert "positions per symbol" not in reason.lower()


def test_one_of_two_independent_take_reaches_risk_not_capacity_block() -> None:
    alloc = _alloc(positions=[_gold(11)], open_n=1)
    reason = alloc.rejection_reason or ""
    assert "MAX_POSITIONS_REACHED" not in reason
    book = build_portfolio_book(account=_account(open_n=1), positions=[_gold(11)])
    assert book.positions_per_symbol.get("XAUUSD") == 1


def test_two_of_two_valid_take_is_max_positions_reached() -> None:
    positions = [_gold(21), _gold(22)]
    alloc = _alloc(positions=positions, open_n=2)
    assert alloc.allow is False
    assert alloc.approved_lots == Decimal("0")
    assert "MAX_POSITIONS_REACHED" in (alloc.rejection_reason or "")
    book = build_portfolio_book(account=_account(open_n=2), positions=positions)
    assert book.positions_per_symbol.get("XAUUSD") == 2
    assert book.open_positions == 2


def test_closed_position_frees_capacity() -> None:
    adapter = _FakeAdapter([])
    sync = force_sync_positions(adapter, symbol="XAUUSD_i", internal_positions=2)
    assert sync.quantforg_positions == 0
    account = apply_mt5_position_truth(_account(open_n=2), sync)
    assert account.open_positions == 0
    alloc = _alloc(positions=[], open_n=account.open_positions)
    assert "MAX_POSITIONS_REACHED" not in (alloc.rejection_reason or "")


def test_stale_closed_ticket_does_not_consume_capacity() -> None:
    closed = SimpleNamespace(
        ticket=77,
        symbol="XAUUSD_i",
        side="sell",
        volume=Decimal("0"),
        remaining_volume=Decimal("0"),
        magic=QUANTFORG_MAGIC,
        comment="ite:v1:stale",
        profit=Decimal("0"),
        open_price=Decimal("4000"),
        current_price=Decimal("4000"),
    )
    book = build_portfolio_book(
        account=_account(open_n=2),
        positions=[closed],  # type: ignore[list-item]
    )
    assert book.open_positions == 0
    assert book.positions_per_symbol.get("XAUUSD", 0) == 0
    assert count_quantforg_positions([closed], symbol="XAUUSD_i") == 0


def test_stale_account_count_does_not_inflate_live_book() -> None:
    live = [_gold(31)]
    book = build_portfolio_book(account=_account(open_n=2), positions=live)
    assert book.open_positions == 1
    alloc = _alloc(positions=live, open_n=2)
    assert "MAX_POSITIONS_REACHED" not in (alloc.rejection_reason or "")


def test_duplicate_ticket_counts_once() -> None:
    dup = [_gold(41), _gold(41)]
    book = build_portfolio_book(account=_account(open_n=2), positions=dup)
    assert book.open_positions == 1
    assert book.positions_per_symbol.get("XAUUSD") == 1
    alloc = _alloc(positions=dup, open_n=2)
    assert "MAX_POSITIONS_REACHED" not in (alloc.rejection_reason or "")


def test_profitable_scale_in_only_when_capacity_exists() -> None:
    one = may_add_scalping_trade(
        open_positions=1,
        max_open=2,
        new_confidence=90,
        best_open_confidence=80,
        new_direction="SELL",
        open_directions=("SELL",),
        open_profits=(Decimal("15"),),
        require_unrealized_profit=True,
        require_improvement=True,
        min_confidence_delta=5,
    )
    assert one.allow is True
    full = _alloc(
        positions=[_gold(51, profit=Decimal("15")), _gold(52, profit=Decimal("8"))],
        open_n=2,
    )
    assert full.allow is False
    assert "MAX_POSITIONS_REACHED" in (full.rejection_reason or "")


def test_losing_position_no_scale_in() -> None:
    d = may_add_scalping_trade(
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
    assert d.allow is False
    assert "average into losers" in d.reason.lower() or "unrealized" in d.reason.lower()


def test_buy_and_sell_independently_evaluated() -> None:
    buy_row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "BUY",
            "signal_action": "BUY",
            "trade_quality": 80,
            "ai_confidence": 78,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "BUY", "setup_state": "TAKE"},
        }
    )
    sell_row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 80,
            "ai_confidence": 78,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    assert buy_row["direction"] == "BUY"
    assert sell_row["direction"] == "SELL"
    assert buy_row["pipeline"]["final_decision"] == "TAKE"
    assert sell_row["pipeline"]["final_decision"] == "TAKE"


def test_take_remains_take_when_risk_capacity_blocks() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 68,
            "ai_confidence": 58,
            "opportunity_score": 75,
            "opportunity_threshold": 70,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "RISK_REJECTED",
            "mt5_ticket": None,
            "execution_blocked": {
                "stage": "RISK",
                "reason_code": "RISK_REJECTED",
                "human_reason": "Max positions per symbol (2 >= 2) for XAUUSD",
            },
            "market_context_diagnostics": {
                "capacity_used": 2,
                "capacity_max": 2,
                "capacity_available": 0,
                "capacity_label": "FULL",
            },
        },
    )
    assert over["first_blocker"] == "MAX_POSITIONS_REACHED"
    assert over["pipeline"]["final_decision"] == "TAKE"
    assert over["pipeline"]["setup_state"] == "TAKE"
    assert over["pipeline"]["decision"] == "SELL"
    assert over["pipeline"]["risk"] == "BLOCK"
    assert over["pipeline"]["safety"] == "NOT_REACHED"
    assert over["pipeline"]["optimizer"] == "NOT_REACHED"
    assert over["pipeline"]["oms"] == "NOT_REACHED"
    assert over["pipeline"]["broker"] == "NOT_REACHED"
    assert over["pipeline"]["mt5"] == "NOT_REACHED"
    assert over["capacity_used"] == 2
    assert over["capacity_max"] == 2
    assert over["capacity_available"] == 0


def test_wait_is_not_converted_to_take_without_signal() -> None:
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "WAIT",
            "signal_action": "WAIT",
            "trade_quality": 50,
            "ai_confidence": 50,
            "reject": True,
            "reason": "WAIT_NO_SNIPER_TRIGGER",
            "sniper_entry": {"passed": False, "action": "WAIT"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": None,
            "market_context_diagnostics": {
                "capacity_used": 0,
                "capacity_max": 2,
                "capacity_available": 2,
            },
        },
    )
    assert over["pipeline"]["final_decision"] == "WAIT"
    assert over["pipeline"].get("execution_lifecycle") != "FILLED"


def test_gold_contract_max_positions_is_risk_wait() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            risk_eligible=False,
            approved_lots=Decimal("0"),
            risk_reasons=("MAX_POSITIONS_REACHED: 2/2 for XAUUSD",),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "MAX_POSITIONS_REACHED"
    assert out.blocking_stage == "RISK"
    assert out.next_action == CandidateAction.WAIT_SAME_FOCUS.value
    assert out.stages["RISK"] == StageStatus.BLOCK.value
    assert out.stages["SIZING"] == StageStatus.NOT_REACHED.value
    assert out.stages["OMS"] == StageStatus.NOT_REACHED.value
    assert out.direction == "SELL"


def test_min_lot_infeasible_remains_fail_closed() -> None:
    out = evaluate_gold_execution_contract(
        _ready(
            action="NO_TRADE",
            risk_eligible=False,
            approved_lots=Decimal("0"),
            min_lot_infeasible=True,
            risk_reasons=("MIN_LOT_INFEASIBLE",),
        )
    )
    assert out.may_submit_oms is False
    assert out.fault_code in {"MIN_LOT_CONSTRAINT", "MIN_LOT_INFEASIBLE"}
    assert out.blocking_stage == "RISK"


def test_kill_switch_blocks_execution() -> None:
    out = evaluate_gold_execution_contract(_ready(kill_switch=True))
    assert out.may_submit_oms is False
    assert out.blocking_stage == "SAFETY"
    assert "kill" in (out.fault_reason or "").lower()


def test_non_xauusd_rejected_before_oms() -> None:
    out = evaluate_gold_execution_contract(_ready(symbol="EURUSD_I"))
    assert out.may_submit_oms is False
    assert out.blocking_stage == "MARKET"
    assert out.stages["OMS"] == StageStatus.NOT_REACHED.value


def test_no_martingale_or_revenge_sizing() -> None:
    cfg = AiScalpingConfig(allow_martingale=True, allow_grid=True)
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
    assert cfg.allow_unlimited_averaging is False
    assert cfg.max_positions_per_symbol == 2


def test_bridge_abort_maps_max_positions_to_risk() -> None:
    assert bridge_abort_stage("MAX_POSITIONS_REACHED") == "RISK"
    assert (
        bridge_abort_stage("Max positions per symbol (2 >= 2) for XAUUSD") == "RISK"
    )


def test_execution_blocked_event_identity_fields() -> None:
    ev = execution_blocked_event(
        stage="RISK",
        reason_code="MAX_POSITIONS_REACHED",
        human_reason="2/2 XAUUSD",
        correlation_id="trace-cap",
        symbol="XAUUSD_i",
        direction="SELL",
        signal_id="trace-cap",
    )
    assert ev["symbol"] == "XAUUSD_i"
    assert ev["direction"] == "SELL"
    assert ev["signal_id"] == "trace-cap"
    assert ev["stage"] == "RISK"


def test_cap_unchanged_at_two() -> None:
    assert AiScalpingConfig().max_positions_per_symbol == 2
    tickets = live_capacity_tickets(
        [_gold(1), _gold(2)], symbol="XAUUSD_i"
    )
    assert len(tickets) == 2
    assert DecisionState.WAITING.value


def test_no_second_quality_80_gate_in_overlay() -> None:
    """Quality 68 TAKE must stay TAKE; capacity is Risk, not Eligibility."""
    row = _row_from_score(
        {
            "symbol": "XAUUSD_I",
            "direction": "SELL",
            "signal_action": "SELL",
            "trade_quality": 68,
            "ai_confidence": 58,
            "opportunity_score": 75,
            "opportunity_threshold": 70,
            "reject": False,
            "sniper_entry": {"passed": True, "action": "SELL", "setup_state": "TAKE"},
        }
    )
    over = _overlay_last_ite_cycle(
        row,
        {
            "forwarded_to_oms": False,
            "abort_reason": "MAX_POSITIONS_REACHED",
            "execution_blocked": {
                "stage": "RISK",
                "reason_code": "MAX_POSITIONS_REACHED",
                "human_reason": "MAX_POSITIONS_REACHED: 2/2 for XAUUSD",
            },
        },
    )
    assert over["first_blocker"] != "ELIGIBILITY_FAILED"
    assert over["pipeline"]["broker"] != "BLOCK"
    assert over["pipeline"]["final_decision"] == "TAKE"
