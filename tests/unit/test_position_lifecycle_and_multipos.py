"""Position lifecycle, class-aware PME, halt semantics, multi-position caps.

Never sends a live order_send.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.mt5_position_truth import (
    apply_mt5_position_truth,
    force_sync_positions,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    AutoTradePolicy,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import AccountRiskState
from app.domain.institutional_trading.management.class_policy import (
    TRADE_CLASS_UNKNOWN,
    encode_execution_comment,
    proven_trade_class,
    resolve_class_management,
    trade_class_from_comment,
)
from app.domain.institutional_trading.management.config import DEFAULT_PME_CONFIG
from app.domain.institutional_trading.management.engine import PositionManagementEngine
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    OmsManageResult,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.policies import plan_action
from app.domain.institutional_trading.operations.decision_cycle import (
    consume_immediate_wakeup,
    note_cycle_event,
    reset_decision_cycle,
)
from app.domain.institutional_trading.operations.position_plan import (
    SCALP_MAX_OPEN_TRADES,
    build_position_plan,
    owned_count_from_rows,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)
from app.domain.institutional_trading.operations.trade_classifier import TradeClass
from app.domain.institutional_trading.phase_a.kill_state import (
    DurableHaltController,
    HaltKind,
    HaltMode,
)
from app.domain.institutional_trading.production_hardening.position_recovery import (
    persist_pme_state,
    recover_positions_from_mt5,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

OPENED = datetime(2026, 8, 20, 16, 0, tzinfo=UTC)


class _CapturingOms:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def modify_sltp(self, **kwargs: object) -> OmsManageResult:
        self.calls.append(kwargs)
        return OmsManageResult(outcome="success", message="modified", retcode=10009)

    def partial_close(self, **kwargs: object) -> OmsManageResult:
        return OmsManageResult(outcome="success", message="partial", retcode=10009)

    def close_position(self, **kwargs: object) -> OmsManageResult:
        return OmsManageResult(outcome="success", message="closed", retcode=10009)


def _pos(
    *,
    trade_class: str,
    ticket: int = 1,
    r_price: str = "4490",
    tp: str = "4526.421",
    hold_minutes: int = 5,
) -> ManagedPosition:
    return ManagedPosition(
        ticket=ticket,
        symbol="XAUUSD_i",
        side="buy",
        entry_price=Decimal("4485.127"),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal("0.01"),
        initial_stop=Decimal("4470.951"),
        risk_distance=Decimal("14.176"),
        opened_at=OPENED,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("4470.951"),
        current_tp=Decimal(tp),
        magic=QUANTFORG_MAGIC,
        comment="ite:v1:S:efe330dd625e",
        cycle_id="cycle-x",
        snapshot_id="snap-x",
        position_plan_id="plan-x",
        trade_class=trade_class,
        opportunity_score=82,
        management_profile=resolve_class_management(trade_class).profile_name,
    )


def _ctx(*, price: str, minutes: int = 5, **kwargs: object) -> PositionManageContext:
    payload = {
        "now": OPENED + timedelta(minutes=minutes),
        "current_price": Decimal(price),
        "atr": Decimal("5"),
        "mid_price": Decimal(price),
        "position_still_open": True,
        "user_id": uuid4(),
        "request_id": "pme-test",
        "connected": True,
    }
    payload.update(kwargs)
    return PositionManageContext(**payload)  # type: ignore[arg-type]


def _mt5_row(
    ticket: int,
    *,
    symbol: str = "XAUUSD_i",
    magic: int = QUANTFORG_MAGIC,
    comment: str = "ite:v1:S:abc",
    sl: str = "4470.95",
    tp: str = "4526.421",
) -> MT5Position:
    return MT5Position(
        ticket=ticket,
        symbol=symbol,
        side="buy",
        volume=Decimal("0.01"),
        open_price=Decimal("4485.127"),
        current_price=Decimal("4487.000"),
        stop_loss=Decimal(sl),
        take_profit=Decimal(tp),
        magic=magic,
        comment=comment,
    )


@pytest.fixture
def pme_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("QUANTFORG_DATA_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.domain.institutional_trading.production_hardening.position_recovery._state_path",
        lambda: tmp_path / "pme_recovery_state.json",
    )
    return tmp_path / "pme_recovery_state.json"


def test_scalp_class_survives_recovery(pme_path: Path) -> None:
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    comment = encode_execution_comment("ite:v1", "efe330dd625e", "SCALP")
    live = _mt5_row(557892348, comment=comment)
    engine.register(
        _pos(trade_class="SCALP", ticket=557892348)
    )
    persist_pme_state(engine)
    fresh = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    mt5 = SimpleNamespace(list_positions=lambda: [live])
    out = recover_positions_from_mt5(mt5_adapter=mt5, engine=fresh, symbol="XAUUSD_i")
    assert out["ok"] is True
    pos = fresh.get(557892348)
    assert pos is not None
    assert pos.trade_class == "SCALP"
    assert pos.cycle_id == "cycle-x"
    assert pos.snapshot_id == "snap-x"
    assert pos.position_plan_id == "plan-x"


def test_hold_class_survives_recovery(pme_path: Path) -> None:
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    pos = _pos(trade_class="HOLD", ticket=99)
    pos.comment = encode_execution_comment("ite:v1", "holdhashxxxx", "HOLD")
    engine.register(pos)
    persist_pme_state(engine)
    live = _mt5_row(99, comment=pos.comment)
    fresh = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    recover_positions_from_mt5(
        mt5_adapter=SimpleNamespace(list_positions=lambda: [live]),
        engine=fresh,
        symbol="XAUUSD_i",
    )
    restored = fresh.get(99)
    assert restored is not None
    assert restored.trade_class == "HOLD"


def test_unknown_class_is_explicit(pme_path: Path) -> None:
    live = _mt5_row(7, comment="ite:v1:efe330dd625e")
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    recover_positions_from_mt5(
        mt5_adapter=SimpleNamespace(list_positions=lambda: [live]),
        engine=engine,
        symbol="XAUUSD_i",
    )
    pos = engine.get(7)
    assert pos is not None
    assert proven_trade_class(pos.trade_class) == TRADE_CLASS_UNKNOWN
    assert pos.trade_class != "SCALP"
    assert pos.trade_class != "HOLD"


def test_break_even_follows_class_policy() -> None:
    scalp = _pos(trade_class="SCALP")
    # ~0.85R: SCALP BE at 0.8R; HOLD BE at 1.0R; UNKNOWN must not inherit SCALP
    price = "4497.20"
    scalp_plan = plan_action(scalp, _ctx(price=price), DEFAULT_PME_CONFIG)
    assert scalp_plan.kind is ManageActionKind.BREAK_EVEN

    hold = _pos(trade_class="HOLD")
    hold_plan = plan_action(hold, _ctx(price=price), DEFAULT_PME_CONFIG)
    assert hold_plan.kind is not ManageActionKind.BREAK_EVEN

    unknown = _pos(trade_class="")
    unknown.trade_class = ""
    unk_plan = plan_action(unknown, _ctx(price=price), DEFAULT_PME_CONFIG)
    assert unk_plan.kind is not ManageActionKind.BREAK_EVEN
    assert proven_trade_class(unknown.trade_class) == TRADE_CLASS_UNKNOWN


def test_scalp_profit_extension_defers_be_when_momentum_intact() -> None:
    scalp = _pos(trade_class="SCALP")
    plan = plan_action(
        scalp,
        _ctx(price="4497.20", ai_momentum=70),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.SKIP
    assert "Profit extension" in plan.reason


def test_scalp_be_fires_when_momentum_faded() -> None:
    scalp = _pos(trade_class="SCALP")
    plan = plan_action(
        scalp,
        _ctx(price="4497.20", minutes=0, ai_momentum=20),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.BREAK_EVEN
    assert plan.new_tp == scalp.current_tp


def test_tp_preserved_on_authorized_sl_modify() -> None:
    oms = _CapturingOms()
    engine = PositionManagementEngine(oms=oms)  # type: ignore[arg-type]
    pos = _pos(trade_class="SCALP")
    engine.register(pos)
    tp = pos.current_tp
    result = engine.evaluate(pos.ticket, _ctx(price="4497.20"))
    assert result.action is ManageActionKind.BREAK_EVEN
    assert result.record is not None
    assert result.record.old_tp == tp
    assert result.record.new_tp == tp
    assert pos.current_tp == tp
    assert oms.calls
    assert oms.calls[0]["take_profit"] == tp
    assert result.record.trade_class == "SCALP"
    assert result.record.cycle_id == "cycle-x"


def test_close_reason_is_explicit() -> None:
    pos = _pos(trade_class="SCALP")
    plan = plan_action(pos, _ctx(price="4485.200", minutes=30), DEFAULT_PME_CONFIG)
    assert plan.kind is ManageActionKind.TIME_STOP
    assert "Absolute max hold" in plan.reason or "Time stop" in plan.reason
    assert "scratch" in plan.reason.lower()


def test_abs_hold_does_not_flatten_meaningful_winner() -> None:
    """Winners past BE floor must not be time-stopped while losers run to SL."""
    pos = _pos(trade_class="SCALP")
    # ~0.85R favorable — past SCALP BE floor (0.80R)
    plan = plan_action(pos, _ctx(price="4497.20", minutes=30), DEFAULT_PME_CONFIG)
    assert plan.kind is not ManageActionKind.TIME_STOP
    assert plan.kind in {
        ManageActionKind.BREAK_EVEN,
        ManageActionKind.SKIP,
        ManageActionKind.TRAIL,
        ManageActionKind.PARTIAL_CLOSE,
    }


def test_broker_flat_releases_quantforg_capacity() -> None:
    adapter = SimpleNamespace(list_positions=lambda: [])
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    engine.register(_pos(trade_class="SCALP", ticket=1))
    account = AccountRiskState(
        equity=Decimal("116.95"),
        open_positions=1,
        already_in_trade=True,
        account_open_positions=1,
    )
    sync = force_sync_positions(
        adapter, symbol="XAUUSD_i", position_engine=engine
    )
    assert sync.quantforg_positions == 0
    updated = apply_mt5_position_truth(account, sync)
    assert updated.open_positions == 0
    assert updated.already_in_trade is False
    assert 1 not in engine._positions
    policy = AutoTradePolicy(enabled=True, run_state="running", max_open_positions=10)
    facts = AutoTradeLiveFacts(
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        risk_engine_pass=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol="XAUUSD_i",
        symbol_tradable=True,
        margin_available=True,
        no_broker_restrictions=True,
        open_positions=updated.open_positions,
        session="london",
        spread=Decimal("0.30"),
        news_blocked=False,
        daily_loss_exceeded=False,
        emergency_stop=False,
        ops_mode="LIVE",
        execution_enabled=True,
    )
    safety = evaluate_auto_trade_safety(policy, facts)
    assert safety.allowed is True


def test_stale_pme_disk_ticket_cannot_block(pme_path: Path) -> None:
    engine = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    stale = _pos(trade_class="HOLD", ticket=533737978)
    stale.symbol = "XAUUSD"
    engine.register(stale)
    persist_pme_state(engine)
    raw = json.loads(pme_path.read_text(encoding="utf-8"))
    assert any(row["ticket"] == 533737978 for row in raw["positions"])
    fresh = PositionManagementEngine(oms=_CapturingOms())  # type: ignore[arg-type]
    out = recover_positions_from_mt5(
        mt5_adapter=SimpleNamespace(list_positions=lambda: []),
        engine=fresh,
        symbol="XAUUSD_i",
    )
    assert out["ok"] is True
    assert fresh.get(533737978) is None
    persisted = json.loads(pme_path.read_text(encoding="utf-8"))
    assert persisted["positions"] == []
    assert 533737978 in (out.get("stale_disk_ignored") or [])


def test_operator_halt_survives_hydrate() -> None:
    ctrl = DurableHaltController()
    ctrl.set_mode(
        HaltMode.HALT_NEW_ENTRIES,
        actor="ops-lead",
        reason="desk halt",
        kind=HaltKind.OPERATOR_HALT,
    )
    restored = DurableHaltController()
    restored.hydrate(ctrl.to_persist())
    assert restored.mode is HaltMode.HALT_NEW_ENTRIES
    assert restored.kind is HaltKind.OPERATOR_HALT


def test_stale_pause_does_not_block_after_hydrate() -> None:
    restored = DurableHaltController()
    restored.hydrate(
        {
            "phase_a_halt_mode": "HALT_NEW_ENTRIES",
            "phase_a_halt_reason": "pause",
            "phase_a_halt_actor": "t",
        }
    )
    assert restored.mode is HaltMode.ACTIVE
    assert restored.new_entries_allowed() is True


def test_position_close_does_not_create_halt() -> None:
    ctrl = DurableHaltController()
    assert ctrl.mode is HaltMode.ACTIVE
    # PME flatten / broker close must not write halt.
    pos = _pos(trade_class="SCALP")
    plan = plan_action(pos, _ctx(price="4485.2", minutes=30), DEFAULT_PME_CONFIG)
    assert plan.kind in {ManageActionKind.TIME_STOP, ManageActionKind.EMERGENCY_EXIT}
    assert ctrl.mode is HaltMode.ACTIVE
    assert ctrl.new_entries_allowed() is True


def test_close_event_wakes_next_cycle() -> None:
    reset_decision_cycle()
    note_cycle_event("position_close")
    assert consume_immediate_wakeup() == "position_close"


def test_auto_trading_policy_stays_running_after_flat() -> None:
    policy = AutoTradePolicy(enabled=True, run_state="running", max_open_positions=10)
    assert policy.to_dict()["run_state"] == "running"
    assert policy.to_dict()["may_open_new_trades"] is True


def test_scalp_can_request_multiple_and_max_10() -> None:
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("0.20"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
    )
    assert 2 <= plan.target_count <= SCALP_MAX_OPEN_TRADES
    assert plan.effective_count <= 10
    assert plan.effective_count >= 2
    assert plan.blocking_reason is None or "risk" not in (plan.blocking_reason or "")


def test_hold_max_5() -> None:
    plan = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.HOLD,
        opportunity_score=99,
        confidence=99,
        aggregate_lots=Decimal("0.20"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
    )
    assert plan.effective_count <= 5
    assert plan.target_count <= 5


def test_target_reduced_by_broker_and_not_forced_to_one() -> None:
    fat = build_position_plan(
        cycle_id="c",
        snapshot_id="s",
        symbol="XAUUSD_i",
        direction="BUY",
        trade_class=TradeClass.SCALP,
        opportunity_score=92,
        confidence=90,
        aggregate_lots=Decimal("0.10"),
        current_quantforg_count=0,
        ite_config=ITEConfig(max_open_trades=10, trading_mode="scalping"),
        broker_allowed_count=4,
    )
    assert fat.effective_count == 4
    assert fat.effective_count != 1
    assert any("broker_allowed" in r for r in fat.reductions)


def test_unrelated_symbol_and_manual_do_not_consume_capacity() -> None:
    rows = [
        {"ticket": 1, "magic": 0, "comment": "manual", "symbol": "XAUUSD_i"},
        {
            "ticket": 2,
            "magic": QUANTFORG_MAGIC,
            "comment": "ite:v1:S:x",
            "symbol": "EURUSD",
        },
        {
            "ticket": 3,
            "magic": QUANTFORG_MAGIC,
            "comment": "ite:v1:S:y",
            "symbol": "XAUUSD_i",
        },
    ]
    assert owned_count_from_rows(rows, symbol="XAUUSD_i") == 1


def test_comment_marker_roundtrip() -> None:
    comment = encode_execution_comment("ite:v1", "deadbeefcafe", "HOLD")
    assert trade_class_from_comment(comment) == "HOLD"
    assert trade_class_from_comment("ite:v1:efe330dd625e") is None


def test_no_live_order_in_lifecycle_suite() -> None:
    needle = "order" + "_send("
    assert needle not in Path(__file__).read_text(encoding="utf-8")
