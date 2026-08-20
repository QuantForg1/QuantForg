"""Continuous live auto-scalping continuity — PME manage + trading_mode persist."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.application.services import ops_state_persistence as osp
from app.application.services.mt5_position_truth import force_sync_positions
from app.application.services.ops_state_persistence import (
    load_ops_state,
    save_ops_state,
)
from app.domain.entities.mt5_portfolio import MT5Position
from app.domain.institutional_trading.management.engine import PositionManagementEngine
from app.domain.institutional_trading.management.models import (
    ManagedPosition,
    PositionLifecycleState,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.production_hardening.position_recovery import (
    recover_positions_from_mt5,
)


@pytest.fixture(autouse=True)
def _no_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(osp, "_supabase_rest_config", lambda: None)
    monkeypatch.setattr(osp, "_load_postgres_state", lambda: {})
    monkeypatch.setattr(osp, "_save_postgres_state", lambda _state: False)


@pytest.mark.unit
def test_trading_mode_persisted_and_hydrated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    save_ops_state(
        {
            "ops_mode": "LIVE",
            "auto_trading_enabled": True,
            "auto_trading_run_state": "running",
            "trading_mode": "scalping",
            "max_open_positions": 3,
        }
    )
    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    plane = cp.get_control_plane()
    assert plane.mode is OpsExecutionMode.LIVE
    assert plane.trading_mode == "scalping"
    assert plane.max_open_trades == 10
    cp._GLOBAL_PLANE = None


@pytest.mark.unit
def test_missing_trading_mode_restored_for_live_desk(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "ops_state.json"
    monkeypatch.setenv("QUANTFORG_OPS_STATE_PATH", str(path))
    # Pre-fix state: LIVE running but trading_mode never persisted
    save_ops_state(
        {
            "ops_mode": "LIVE",
            "auto_trading_enabled": True,
            "auto_trading_run_state": "running",
        }
    )
    from app.domain.institutional_trading.operations import control_plane as cp

    cp._GLOBAL_PLANE = None
    plane = cp.get_control_plane()
    assert plane.trading_mode == "scalping"
    assert plane.max_open_trades >= 3
    state = load_ops_state()
    assert state.get("trading_mode") == "scalping"
    cp._GLOBAL_PLANE = None


@pytest.mark.unit
def test_force_sync_does_not_drop_other_symbols() -> None:
    class _Client:
        def __init__(self, rows: list[MT5Position]) -> None:
            self._rows = rows

        def invalidate_positions_cache(self) -> None:
            return None

        def list_positions(self) -> list[MT5Position]:
            return list(self._rows)

    class _Adapter:
        def __init__(self, rows: list[MT5Position]) -> None:
            self._client = _Client(rows)

        def list_positions(self) -> list[MT5Position]:
            return self._client.list_positions()

    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    engine.register(
        ManagedPosition(
            ticket=1,
            symbol="XAUUSD",
            side="buy",
            entry_price=Decimal("4000"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("3990"),
            risk_distance=Decimal("10"),
            opened_at=datetime.now(UTC),
            state=PositionLifecycleState.OPEN,
            current_stop=Decimal("3990"),
        )
    )
    engine.register(
        ManagedPosition(
            ticket=2,
            symbol="EURUSD",
            side="buy",
            entry_price=Decimal("1.1"),
            initial_volume=Decimal("0.01"),
            remaining_volume=Decimal("0.01"),
            initial_stop=Decimal("1.09"),
            risk_distance=Decimal("0.01"),
            opened_at=datetime.now(UTC),
            state=PositionLifecycleState.OPEN,
            current_stop=Decimal("1.09"),
        )
    )
    # Gold closed on MT5; EURUSD still open — gold-scoped sync must keep EURUSD
    sync = force_sync_positions(
        _Adapter([]),
        symbol="XAUUSD",
        internal_positions=1,
        position_engine=engine,
    )
    assert sync.mt5_positions == 0
    assert 1 not in engine._positions
    assert 2 in engine._positions


@pytest.mark.unit
def test_recover_registers_fill_with_broker_sl() -> None:
    engine = PositionManagementEngine(oms=SimpleNamespace())  # type: ignore[arg-type]
    row = MT5Position(
        ticket=77,
        symbol="XAUUSD",
        side="buy",
        volume=Decimal("0.02"),
        open_price=Decimal("4000"),
        current_price=Decimal("4001"),
        stop_loss=Decimal("3995"),
        take_profit=Decimal("4010"),
    )
    mt5 = SimpleNamespace(list_positions=lambda: [row])
    result = recover_positions_from_mt5(mt5_adapter=mt5, engine=engine, symbol="XAUUSD")
    assert result["ok"] is True
    assert result["registered"] == 1
    pos = engine.get(77)
    assert pos is not None
    assert pos.initial_stop == Decimal("3995")
    assert pos.current_tp == Decimal("4010")


@pytest.mark.unit
def test_safety_blocked_still_manages_open_positions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """max-open / SAFETY_BLOCKED must not skip PME — continuous scalping requires exits."""  # noqa: E501
    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )
    from app.domain.institutional_trading.decision_models import AccountRiskState
    from app.domain.institutional_trading.operations.models import OpsExecutionMode

    plane = MagicMock()
    plane.mode = OpsExecutionMode.LIVE
    plane.kill_switch_armed = False
    plane.daily_loss_exceeded = False
    plane.evaluate_auto_trading = MagicMock(
        return_value=SimpleNamespace(
            allowed=False,
            failed_reasons=("Open positions 1 at max 1",),
        )
    )

    runtime = InstitutionalIteRuntime(
        plane=plane,
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=MagicMock(),
        interval_seconds=5.0,
        mt5_adapter=MagicMock(),
    )
    runtime.tick_health = MagicMock(return_value={"health": "ok", "live_probes": {}})  # type: ignore[method-assign]
    managed: list[str] = []

    def _manage(**kwargs: Any) -> int:
        managed.append(str(kwargs.get("reason")))
        return 1

    runtime._sync_and_manage_open_positions = _manage  # type: ignore[method-assign]
    runtime._run_cycle = MagicMock()  # type: ignore[method-assign]

    monkeypatch.setattr(
        "app.application.services.institutional_ite_runtime.get_settings",
        lambda: SimpleNamespace(execution_enabled=True),
    )
    monkeypatch.setattr(
        "app.domain.institutional_trading.force_first_trade.is_force_first_trade_armed",
        lambda _settings=None: False,
    )

    sync = SimpleNamespace(
        mt5_positions=1,
        internal_positions=1,
        repaired=False,
        symbol="XAUUSD",
        tickets=(9,),
    )
    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.force_sync_positions",
        lambda *_a, **_k: sync,
    )
    monkeypatch.setattr(
        "app.application.services.mt5_position_truth.apply_mt5_position_truth",
        lambda account, _sync: account,
    )

    snapshot = SimpleNamespace(
        symbol="XAUUSD",
        spread=Decimal("0.3"),
        news=SimpleNamespace(blocked=False, reason=""),
        session=SimpleNamespace(session=SimpleNamespace(value="london")),
    )
    account = AccountRiskState(
        equity=Decimal("1000"),
        open_positions=1,
        already_in_trade=True,
        mid_price=Decimal("4000"),
        atr=Decimal("5"),
        market_open=True,
        free_margin=Decimal("500"),
    )
    result = runtime.run_auto_cycle(
        snapshot=snapshot,
        account=account,
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        risk_allowed=True,
    )
    assert result.abort_reason == "SAFETY_BLOCKED"
    assert managed == ["safety_blocked_manage"]
    runtime._run_cycle.assert_not_called()


@pytest.mark.unit
def test_min_lot_partial_advances_to_partial_for_trail() -> None:
    from app.domain.institutional_trading.management.config import DEFAULT_PME_CONFIG
    from app.domain.institutional_trading.management.models import PositionManageContext
    from app.domain.institutional_trading.management.policies import plan_action

    pos = ManagedPosition(
        ticket=1,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("4000"),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal("0.01"),
        initial_stop=Decimal("3990"),
        risk_distance=Decimal("10"),
        opened_at=datetime.now(UTC),
        state=PositionLifecycleState.BE_MOVED,
        current_stop=Decimal("4000"),
        be_moved=True,
    )
    ctx = PositionManageContext(
        now=datetime.now(UTC),
        current_price=Decimal("4020"),  # +2R
        atr=Decimal("5"),
    )
    plan = plan_action(pos, ctx, DEFAULT_PME_CONFIG)
    assert plan.kind.value == "partial_close"
    assert plan.volume == Decimal("0")
    assert plan.target_state is PositionLifecycleState.PARTIAL


@pytest.mark.unit
def test_failed_manage_does_not_fingerprint_block_retry() -> None:
    from app.domain.institutional_trading.management.config import DEFAULT_PME_CONFIG
    from app.domain.institutional_trading.management.models import (
        ManageActionKind,
        OmsManageResult,
        PositionManageContext,
    )

    class _FailOms:
        def modify_sltp(self, **kwargs: Any) -> OmsManageResult:
            return OmsManageResult(
                outcome="rejected", message="transient", retcode=10004
            )

        def partial_close(self, **kwargs: Any) -> OmsManageResult:
            return OmsManageResult(
                outcome="rejected", message="transient", retcode=10004
            )

        def close_position(self, **kwargs: Any) -> OmsManageResult:
            return OmsManageResult(
                outcome="rejected", message="transient", retcode=10004
            )

    engine = PositionManagementEngine(
        oms=_FailOms(), config=DEFAULT_PME_CONFIG  # type: ignore[arg-type]
    )
    pos = ManagedPosition(
        ticket=5,
        symbol="XAUUSD",
        side="buy",
        entry_price=Decimal("4000"),
        initial_volume=Decimal("0.1"),
        remaining_volume=Decimal("0.1"),
        initial_stop=Decimal("3990"),
        risk_distance=Decimal("10"),
        opened_at=datetime.now(UTC),
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal("3990"),
    )
    engine.register(pos)
    ctx = PositionManageContext(
        now=datetime.now(UTC),
        current_price=Decimal("4010"),  # +1R → BE
        atr=Decimal("5"),
    )
    first = engine.evaluate(5, ctx)
    assert first.action is ManageActionKind.BREAK_EVEN
    assert first.oms_result is not None and not first.oms_result.ok
    assert pos.last_manage_fingerprint is None
    second = engine.evaluate(5, ctx)
    assert second.record is None or second.record.outcome.value != "duplicate"
