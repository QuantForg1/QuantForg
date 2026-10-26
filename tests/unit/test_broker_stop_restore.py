"""A confirmed naked broker stop is restored or flattened.

An empty book and an unreadable stop stay unknown. Neither one closes
the position. This file never sends a live order.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.application.services.institutional_ops_guards import (
    GuardedOmsManagePort,
    _sl_tightens,
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
from app.domain.institutional_trading.management.policies import (
    broker_stop_fields,
    plan_action,
)
from app.domain.institutional_trading.operations.quantforg_position_cap import (
    QUANTFORG_MAGIC,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

OPENED = datetime(2026, 10, 27, 12, 0, tzinfo=UTC)


class _CapturingOms:
    def __init__(self, *, ok: bool = True) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.ok = ok

    def modify_sltp(self, **kwargs: object) -> OmsManageResult:
        self.calls.append(("modify", kwargs))
        if self.ok:
            return OmsManageResult(outcome="success", message="modified", retcode=10009)
        return OmsManageResult(outcome="failed", message="rejected", retcode=10004)

    def partial_close(self, **kwargs: object) -> OmsManageResult:
        self.calls.append(("partial", kwargs))
        return OmsManageResult(outcome="success", message="partial", retcode=10009)

    def close_position(self, **kwargs: object) -> OmsManageResult:
        self.calls.append(("close", kwargs))
        if self.ok:
            return OmsManageResult(outcome="success", message="closed", retcode=10009)
        return OmsManageResult(outcome="failed", message="rejected", retcode=10004)


class _Plane:
    def pme_modifications_allowed(self) -> bool:
        return False

    def pme_protective_allowed(self) -> bool:
        return True


def _pos(
    *,
    side: str = "buy",
    current: str = "4470",
    initial: str = "4460",
    price_entry: str = "4485",
) -> ManagedPosition:
    return ManagedPosition(
        ticket=77,
        symbol="XAUUSD",
        side=side,
        entry_price=Decimal(price_entry),
        initial_volume=Decimal("0.01"),
        remaining_volume=Decimal("0.01"),
        initial_stop=Decimal(initial),
        risk_distance=Decimal("25"),
        opened_at=OPENED,
        state=PositionLifecycleState.OPEN,
        current_stop=Decimal(current),
        current_tp=Decimal("4520") if side == "buy" else Decimal("4400"),
        magic=QUANTFORG_MAGIC,
    )


def _ctx(**kwargs: object) -> PositionManageContext:
    payload: dict[str, object] = {
        "now": OPENED + timedelta(minutes=2),
        "current_price": Decimal("4490"),
        "atr": Decimal("5"),
        "mid_price": Decimal("4490"),
        "position_still_open": True,
        "user_id": uuid4(),
        "request_id": "pme-restore",
        "connected": True,
    }
    payload.update(kwargs)
    return PositionManageContext(**payload)  # type: ignore[arg-type]


def test_unknown_stop_does_not_restore_or_flatten() -> None:
    plan = plan_action(_pos(), _ctx(broker_stop_missing=False), DEFAULT_PME_CONFIG)
    assert plan.kind is not ManageActionKind.RESTORE_STOP
    assert plan.kind is not ManageActionKind.EMERGENCY_EXIT


def test_buy_restores_current_stop_when_it_still_protects() -> None:
    plan = plan_action(
        _pos(current="4470", initial="4460"),
        _ctx(current_price=Decimal("4490"), broker_stop_missing=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.RESTORE_STOP
    assert plan.new_sl == Decimal("4470")
    assert plan.target_state is None


def test_sell_restores_current_stop_when_it_still_protects() -> None:
    plan = plan_action(
        _pos(side="sell", current="4510", initial="4520", price_entry="4490"),
        _ctx(current_price=Decimal("4480"), broker_stop_missing=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.RESTORE_STOP
    assert plan.new_sl == Decimal("4510")


def test_falls_back_to_initial_stop_when_current_is_through() -> None:
    plan = plan_action(
        _pos(current="4495", initial="4460"),
        _ctx(current_price=Decimal("4490"), broker_stop_missing=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.RESTORE_STOP
    assert plan.new_sl == Decimal("4460")


def test_flattens_when_price_has_traded_through_both_stops() -> None:
    plan = plan_action(
        _pos(current="4495", initial="4492"),
        _ctx(current_price=Decimal("4490"), broker_stop_missing=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.EMERGENCY_EXIT
    assert plan.target_state is PositionLifecycleState.EXITED


def test_flattens_when_no_positive_local_stop_exists() -> None:
    plan = plan_action(
        _pos(current="0", initial="0"),
        _ctx(broker_stop_missing=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.EMERGENCY_EXIT


def test_restore_runs_before_a_discretionary_structure_exit() -> None:
    plan = plan_action(
        _pos(),
        _ctx(broker_stop_missing=True, structure_broken=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.RESTORE_STOP


def test_daily_loss_still_flattens_before_a_restore() -> None:
    plan = plan_action(
        _pos(),
        _ctx(broker_stop_missing=True, daily_loss_exceeded=True),
        DEFAULT_PME_CONFIG,
    )
    assert plan.kind is ManageActionKind.DAILY_SHUTDOWN


def test_empty_book_and_unreadable_stop_are_not_naked() -> None:
    assert broker_stop_fields(None) == (None, False)
    garbage = SimpleNamespace(stop_loss="not-a-price", sl="0")
    assert broker_stop_fields(garbage) == (None, False)
    naked = SimpleNamespace(stop_loss=0, sl=0)
    assert broker_stop_fields(naked) == (None, True)
    present = SimpleNamespace(stop_loss=0, sl="4470.5")
    assert broker_stop_fields(present) == (Decimal("4470.5"), False)


def test_engine_restores_without_changing_state_or_fingerprint() -> None:
    oms = _CapturingOms()
    engine = PositionManagementEngine(oms=oms)  # type: ignore[arg-type]
    position = engine.register(_pos())
    assert position.last_manage_fingerprint is None
    result = engine.evaluate(77, _ctx(broker_stop_missing=True))
    assert result.action is ManageActionKind.RESTORE_STOP
    assert result.position.state is PositionLifecycleState.OPEN
    assert result.position.current_stop == Decimal("4470")
    assert result.position.last_manage_fingerprint is None
    assert oms.calls[0][0] == "modify"
    assert oms.calls[0][1]["current_stop_loss"] == Decimal("0")
    assert oms.calls[0][1]["stop_loss"] == Decimal("4470")
    assert oms.calls[0][1]["take_profit_changed"] is False
    engine.evaluate(77, _ctx(broker_stop_missing=True))
    assert len(oms.calls) == 2
    assert result.position.state is PositionLifecycleState.OPEN


def test_failed_restore_retries_and_does_not_flatten() -> None:
    oms = _CapturingOms(ok=False)
    engine = PositionManagementEngine(oms=oms)  # type: ignore[arg-type]
    position = engine.register(_pos())
    result = engine.evaluate(77, _ctx(broker_stop_missing=True))
    assert result.action is ManageActionKind.RESTORE_STOP
    assert result.position.state is PositionLifecycleState.OPEN
    assert result.position.last_manage_fingerprint is None
    assert position.current_stop == Decimal("4470")
    again = engine.evaluate(77, _ctx(broker_stop_missing=True))
    assert again.action is ManageActionKind.RESTORE_STOP
    assert len(oms.calls) == 2


def test_engine_flattens_when_the_local_stop_no_longer_protects() -> None:
    oms = _CapturingOms()
    engine = PositionManagementEngine(oms=oms)  # type: ignore[arg-type]
    engine.register(_pos(current="0", initial="0"))
    result = engine.evaluate(77, _ctx(broker_stop_missing=True))
    assert result.action is ManageActionKind.EMERGENCY_EXIT
    assert result.position.state is PositionLifecycleState.EXITED
    assert oms.calls[0][0] == "close"


def test_explicit_zero_stop_is_protective_and_a_missing_current_is_not() -> None:
    assert _sl_tightens(
        {
            "current_stop_loss": Decimal("0"),
            "stop_loss": Decimal("4470"),
            "side": "buy",
            "take_profit_changed": False,
        }
    )
    assert _sl_tightens(
        {
            "current_stop_loss": Decimal("0"),
            "stop_loss": Decimal("4510"),
            "side": "sell",
            "take_profit_changed": False,
        }
    )
    assert not _sl_tightens(
        {
            "current_stop_loss": None,
            "stop_loss": Decimal("4470"),
            "side": "buy",
            "take_profit_changed": False,
        }
    )
    assert not _sl_tightens(
        {
            "current_stop_loss": Decimal("0"),
            "stop_loss": Decimal("4470"),
            "side": "buy",
            "take_profit_changed": True,
        }
    )


def test_kill_switch_allows_installing_a_stop_on_a_naked_position() -> None:
    inner = _CapturingOms()
    guard = GuardedOmsManagePort(inner=inner, plane=_Plane())  # type: ignore[arg-type]
    installed = guard.modify_sltp(
        current_stop_loss=Decimal("0"),
        stop_loss=Decimal("4470"),
        side="buy",
        take_profit_changed=False,
    )
    assert installed.outcome == "success"
    assert len(inner.calls) == 1
    blocked = guard.modify_sltp(
        current_stop_loss=None,
        stop_loss=Decimal("4470"),
        side="buy",
        take_profit_changed=False,
    )
    assert blocked.outcome == "disabled"
    assert len(inner.calls) == 1
    widen = guard.modify_sltp(
        current_stop_loss=Decimal("4470"),
        stop_loss=Decimal("4460"),
        side="buy",
        take_profit_changed=False,
    )
    assert widen.outcome == "disabled"
    assert len(inner.calls) == 1
