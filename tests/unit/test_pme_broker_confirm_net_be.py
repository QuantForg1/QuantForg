"""PME broker SL confirm, net BE, min-lot partial, exit-context proposals."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.application.services.institutional_oms_manage_adapter import (
    RecordingOmsManagePort,
)
from app.application.services.institutional_position_management import (
    InstitutionalPositionManagement,
)
from app.domain.institutional_trading.management.broker_confirm import (
    BrokerPositionSnapshot,
    confirm_sl_modification,
    stop_meets_plan,
)
from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.exit_context import (
    propose_reversal_exit,
)
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    ManageOutcome,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.r_math import (
    break_even_stop,
    net_break_even_stop,
)

OPENED = datetime(2026, 7, 20, 14, 0, tzinfo=UTC)


def _pos(
    *,
    side: str = "buy",
    entry: Decimal = Decimal("2300"),
    stop: Decimal = Decimal("2290"),
    volume: Decimal = Decimal("0.20"),
    state: PositionLifecycleState = PositionLifecycleState.OPEN,
) -> ManagedPosition:
    risk = abs(entry - stop)
    return ManagedPosition(
        ticket=100,
        symbol="XAUUSD",
        side=side,
        entry_price=entry,
        initial_volume=volume,
        remaining_volume=volume,
        initial_stop=stop,
        risk_distance=risk,
        opened_at=OPENED,
        state=state,
        current_stop=stop,
        current_tp=Decimal("2330"),
        be_moved=state != PositionLifecycleState.OPEN,
        partial_done=False,
    )


def _ctx(price: Decimal, **kwargs: object) -> PositionManageContext:
    base = dict(  # noqa: C408
        now=OPENED + timedelta(minutes=5),
        current_price=price,
        atr=Decimal("5"),
        mid_price=price,
        spread=Decimal("0.30"),
        market_open=True,
        connection_stable=True,
        position_still_open=True,
        user_id=uuid4(),
        request_id="pme-confirm-test",
        connected=True,
    )
    base.update(kwargs)
    return PositionManageContext(**base)  # type: ignore[arg-type]


@dataclass
class _Reader:
    snap: BrokerPositionSnapshot

    def read_position(self, ticket: int, *, symbol: str) -> BrokerPositionSnapshot:
        _ = (ticket, symbol)
        return self.snap


@pytest.mark.unit
@pytest.mark.trading_core
class TestBrokerConfirmPure:
    def test_buy_accepts_equal_or_better(self) -> None:
        assert stop_meets_plan(
            side="buy", planned_sl=Decimal("2302"), broker_sl=Decimal("2302")
        )
        assert stop_meets_plan(
            side="buy", planned_sl=Decimal("2302"), broker_sl=Decimal("2303")
        )
        assert not stop_meets_plan(
            side="buy", planned_sl=Decimal("2302"), broker_sl=Decimal("2300")
        )

    def test_sell_accepts_equal_or_better(self) -> None:
        assert stop_meets_plan(
            side="sell", planned_sl=Decimal("2298"), broker_sl=Decimal("2298")
        )
        assert stop_meets_plan(
            side="sell", planned_sl=Decimal("2298"), broker_sl=Decimal("2297")
        )
        assert not stop_meets_plan(
            side="sell", planned_sl=Decimal("2298"), broker_sl=Decimal("2300")
        )

    def test_unavailable_not_confirmed(self) -> None:
        r = confirm_sl_modification(
            side="buy",
            planned_sl=Decimal("2302"),
            planned_tp=None,
            snapshot=BrokerPositionSnapshot(
                ticket=1, available=False, reason="timeout"
            ),
        )
        assert r.confirmed is False
        assert "unavailable" in r.reason or "timeout" in r.reason


@pytest.mark.unit
@pytest.mark.trading_core
class TestBrokerConfirmEngine:
    def test_be_success_when_confirm_matches_buy(self) -> None:
        cfg = PositionManagementConfig(require_broker_sl_confirm=True)
        planned = Decimal("2302.00")
        reader = _Reader(
            BrokerPositionSnapshot(
                ticket=100,
                available=True,
                stop_loss=planned,
                take_profit=Decimal("2330"),
            )
        )
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(
            oms, config=cfg, broker_reader=reader
        )
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(Decimal("2310")))
        assert result.action is ManageActionKind.BREAK_EVEN
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.SUCCESS
        assert result.position.be_moved is True

    def test_be_not_locked_when_confirm_unavailable(self) -> None:
        cfg = PositionManagementConfig(require_broker_sl_confirm=True)
        reader = _Reader(
            BrokerPositionSnapshot(ticket=100, available=False, reason="timeout")
        )
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(
            oms, config=cfg, broker_reader=reader
        )
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(Decimal("2310")))
        assert result.action is ManageActionKind.BREAK_EVEN
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.BROKER_CONFIRM_FAILURE
        assert result.position.be_moved is False
        assert result.position.state is PositionLifecycleState.OPEN

    def test_be_rejected_when_broker_sl_worse_sell(self) -> None:
        cfg = PositionManagementConfig(require_broker_sl_confirm=True)
        # SELL entry 2300 stop 2310 → geometric BE = 2298
        pos = _pos(side="sell", entry=Decimal("2300"), stop=Decimal("2310"))
        reader = _Reader(
            BrokerPositionSnapshot(
                ticket=100,
                available=True,
                stop_loss=Decimal("2305"),  # worse (higher) than planned BE
                take_profit=Decimal("2270"),
            )
        )
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(
            oms, config=cfg, broker_reader=reader
        )
        svc.register(pos)
        result = svc.evaluate(100, _ctx(Decimal("2290")))
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.BROKER_CONFIRM_FAILURE
        assert result.position.be_moved is False

    def test_confirm_disabled_preserves_legacy_oms_ok(self) -> None:
        cfg = PositionManagementConfig(require_broker_sl_confirm=False)
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(oms, config=cfg)
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(Decimal("2310")))
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.SUCCESS
        assert result.position.be_moved is True

    def test_default_config_requires_broker_confirm_and_net_be(self) -> None:
        from app.domain.institutional_trading.management.config import (
            DEFAULT_PME_CONFIG,
        )

        assert DEFAULT_PME_CONFIG.require_broker_sl_confirm is True
        assert DEFAULT_PME_CONFIG.use_net_break_even is True
        assert DEFAULT_PME_CONFIG.live_reversal_exits_enabled is False


@pytest.mark.unit
@pytest.mark.trading_core
class TestNetBreakEven:
    def test_incomplete_costs_return_none(self) -> None:
        pos = _pos()
        cfg = PositionManagementConfig()
        sl, reason = net_break_even_stop(pos, cfg, spread=None)
        assert sl is None
        assert "incomplete" in reason

    def test_net_be_buy_pushes_above_geometric(self) -> None:
        pos = _pos()
        cfg = PositionManagementConfig()
        geo = break_even_stop(pos, cfg)
        net, reason = net_break_even_stop(
            pos,
            cfg,
            spread=Decimal("0.40"),
            commission=Decimal("0"),
            swap=Decimal("0"),
            contract_size=Decimal("100"),
        )
        assert reason == "net_be"
        assert net is not None
        assert net > geo

    def test_net_be_sell_pushes_below_geometric(self) -> None:
        pos = _pos(side="sell", entry=Decimal("2300"), stop=Decimal("2310"))
        cfg = PositionManagementConfig()
        geo = break_even_stop(pos, cfg)
        net, reason = net_break_even_stop(
            pos,
            cfg,
            spread=Decimal("0.40"),
            commission=Decimal("0"),
            swap=Decimal("0"),
            contract_size=Decimal("100"),
        )
        assert reason == "net_be"
        assert net is not None
        assert net < geo


@pytest.mark.unit
@pytest.mark.trading_core
class TestMinLotPartial:
    def test_zero_volume_partial_not_fictitious_success(self) -> None:
        cfg = PositionManagementConfig(
            min_volume=Decimal("0.01"), volume_step=Decimal("0.01")
        )
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(oms, config=cfg)
        pos = _pos(volume=Decimal("0.01"), state=PositionLifecycleState.BE_MOVED)
        pos.be_moved = True
        pos.current_stop = Decimal("2302")
        svc.register(pos)
        # At 2R with 0.01 lot, partial volume rounds to 0 → lifecycle advance only
        result = svc.evaluate(100, _ctx(Decimal("2320")))
        assert result.action is ManageActionKind.PARTIAL_CLOSE
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.SKIPPED
        assert result.skipped is True
        assert result.position.state is PositionLifecycleState.PARTIAL
        assert result.position.remaining_volume == Decimal("0.01")
        assert oms.calls == []


@pytest.mark.unit
@pytest.mark.trading_core
class TestSessionFlattenGate:
    def test_market_closed_noop_when_flatten_disabled(self) -> None:
        cfg = PositionManagementConfig(session_flatten_on_market_closed=False)
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(oms, config=cfg)
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(Decimal("2305"), market_open=False))
        assert result.action is ManageActionKind.NOOP
        assert oms.calls == []

    def test_market_closed_exits_when_flatten_enabled(self) -> None:
        cfg = PositionManagementConfig(session_flatten_on_market_closed=True)
        oms = RecordingOmsManagePort()
        svc = InstitutionalPositionManagement.create(oms, config=cfg)
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(Decimal("2305"), market_open=False))
        assert result.action is ManageActionKind.EMERGENCY_EXIT


@pytest.mark.unit
@pytest.mark.trading_core
class TestExitContextProposal:
    def test_buy_genuine_bearish_reversal(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            choch_against=True,
            htf_agrees_against=True,
        )
        assert p.structure_broken is True
        assert p.is_retracement is False

    def test_normal_retracement(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            ltf_only_noise=True,
            bos_against=False,
            choch_against=False,
        )
        assert p.is_retracement is True
        assert p.structure_broken is False

    def test_stale_data(self) -> None:
        p = propose_reversal_exit(
            position_side="sell",
            bos_against=True,
            htf_agrees_against=True,
            data_age_seconds=999,
        )
        assert p.stale_data is True
        assert p.structure_broken is False

    def test_conflicting_tf_no_exit(self) -> None:
        p = propose_reversal_exit(
            position_side="buy",
            bos_against=True,
            htf_agrees_against=False,
        )
        assert p.structure_broken is False
