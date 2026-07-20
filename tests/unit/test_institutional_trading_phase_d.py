"""Phase D unit tests — Position Management Engine."""

from __future__ import annotations

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
from app.domain.institutional_trading.management.config import PositionManagementConfig
from app.domain.institutional_trading.management.models import (
    ManageActionKind,
    ManagedPosition,
    ManageOutcome,
    OmsManageResult,
    PositionLifecycleState,
    PositionManageContext,
)
from app.domain.institutional_trading.management.state_machine import (
    PositionStateMachine,
)

OPENED = datetime(2026, 7, 20, 14, 0, tzinfo=UTC)


def _pos(
    *,
    ticket: int = 100,
    side: str = "buy",
    entry: Decimal = Decimal("2300"),
    stop: Decimal = Decimal("2290"),
    volume: Decimal = Decimal("0.20"),
    state: PositionLifecycleState = PositionLifecycleState.OPEN,
    opened_at: datetime = OPENED,
) -> ManagedPosition:
    risk = abs(entry - stop)
    return ManagedPosition(
        ticket=ticket,
        symbol="XAUUSD",
        side=side,
        entry_price=entry,
        initial_volume=volume,
        remaining_volume=volume,
        initial_stop=stop,
        risk_distance=risk,
        opened_at=opened_at,
        state=state,
        current_stop=stop,
        current_tp=Decimal("2330"),
        be_moved=state != PositionLifecycleState.OPEN,
        partial_done=state
        in {PositionLifecycleState.PARTIAL, PositionLifecycleState.TRAILING},
        trailing_active=state is PositionLifecycleState.TRAILING,
    )


def _ctx(
    *,
    price: Decimal,
    now: datetime | None = None,
    atr: Decimal = Decimal("5"),
    spread: Decimal = Decimal("0.30"),
    **kwargs: object,
) -> PositionManageContext:
    base = dict(  # noqa: C408
        now=now or OPENED + timedelta(minutes=5),
        current_price=price,
        atr=atr,
        mid_price=price,
        spread=spread,
        market_open=True,
        connection_stable=True,
        position_still_open=True,
        user_id=uuid4(),
        request_id="pme-test",
        connected=True,
    )
    base.update(kwargs)
    return PositionManageContext(**base)  # type: ignore[arg-type]


def _svc(
    oms: RecordingOmsManagePort | None = None,
    *,
    config: PositionManagementConfig | None = None,
) -> tuple[InstitutionalPositionManagement, RecordingOmsManagePort]:
    port = oms or RecordingOmsManagePort()
    return InstitutionalPositionManagement.create(port, config=config), port


@pytest.mark.unit
class TestPositionStateMachine:
    def test_progressive_allowed(self) -> None:
        assert PositionStateMachine.can_transition(
            PositionLifecycleState.OPEN, PositionLifecycleState.BE_MOVED
        )
        assert PositionStateMachine.can_transition(
            PositionLifecycleState.BE_MOVED, PositionLifecycleState.PARTIAL
        )
        assert PositionStateMachine.can_transition(
            PositionLifecycleState.PARTIAL, PositionLifecycleState.TRAILING
        )

    def test_never_skip_states(self) -> None:
        assert not PositionStateMachine.can_transition(
            PositionLifecycleState.OPEN, PositionLifecycleState.PARTIAL
        )
        assert not PositionStateMachine.can_transition(
            PositionLifecycleState.OPEN, PositionLifecycleState.TRAILING
        )
        assert not PositionStateMachine.can_transition(
            PositionLifecycleState.BE_MOVED, PositionLifecycleState.TRAILING
        )

    def test_exit_from_any_active(self) -> None:
        for s in (
            PositionLifecycleState.OPEN,
            PositionLifecycleState.BE_MOVED,
            PositionLifecycleState.PARTIAL,
            PositionLifecycleState.TRAILING,
        ):
            assert PositionStateMachine.can_transition(s, PositionLifecycleState.EXITED)

    def test_exited_terminal(self) -> None:
        assert not PositionStateMachine.can_transition(
            PositionLifecycleState.EXITED, PositionLifecycleState.OPEN
        )


@pytest.mark.unit
class TestBreakEven:
    def test_break_even_at_1r(self) -> None:
        # 1R = 10 points; price at 2310 = 1.0R
        svc, oms = _svc()
        pos = _pos()
        svc.register(pos)
        result = svc.evaluate(100, _ctx(price=Decimal("2310")))
        assert result.action is ManageActionKind.BREAK_EVEN
        assert result.position.state is PositionLifecycleState.BE_MOVED
        assert result.position.be_moved is True
        # entry 2300 + 0.2R (2) = 2302
        assert result.position.current_stop == Decimal("2302.00")
        assert oms.calls[0]["method"] == "modify_sltp"
        assert len(svc.engine.journal.by_ticket(100)) >= 1

    def test_break_even_only_once(self) -> None:
        svc, oms = _svc()
        pos = _pos(state=PositionLifecycleState.BE_MOVED)
        pos.be_moved = True
        pos.current_stop = Decimal("2302")
        svc.register(pos)
        # Still at 1R — should not BE again; may NOOP until 2R
        result = svc.evaluate(100, _ctx(price=Decimal("2310")))
        assert result.action is ManageActionKind.NOOP
        assert oms.calls == []


@pytest.mark.unit
class TestPartialClose:
    def test_partial_at_2r(self) -> None:
        svc, oms = _svc()
        pos = _pos(state=PositionLifecycleState.BE_MOVED)
        pos.be_moved = True
        pos.current_stop = Decimal("2302")
        svc.register(pos)
        # 2R = 2320
        result = svc.evaluate(100, _ctx(price=Decimal("2320")))
        assert result.action is ManageActionKind.PARTIAL_CLOSE
        assert result.position.state is PositionLifecycleState.PARTIAL
        assert result.position.remaining_volume == Decimal("0.10")
        assert oms.calls[0]["method"] == "partial_close"
        assert oms.calls[0]["volume"] == Decimal("0.10")
        assert oms.calls[0]["side"] == "sell"  # opposite of buy


@pytest.mark.unit
class TestAtrTrailing:
    def test_atr_trail_after_partial(self) -> None:
        svc, oms = _svc()
        pos = _pos(state=PositionLifecycleState.PARTIAL)
        pos.be_moved = True
        pos.partial_done = True
        pos.current_stop = Decimal("2302")
        pos.remaining_volume = Decimal("0.10")
        svc.register(pos)
        # atr 12 / 2325 ≈ 0.52% → NORMAL regime; trail SL = 2325 - 12 = 2313
        result = svc.evaluate(100, _ctx(price=Decimal("2325"), atr=Decimal("12")))
        assert result.action is ManageActionKind.TRAIL
        assert result.position.state is PositionLifecycleState.TRAILING
        assert result.position.current_stop == Decimal("2313.00")
        assert oms.calls[0]["method"] == "modify_sltp"

    def test_high_volatility_wider_trail(self) -> None:
        cfg = PositionManagementConfig(
            atr_high_pct=Decimal("0.1"),  # force high regime
            trail_atr_mult_high=Decimal("1.5"),
        )
        svc, oms = _svc(config=cfg)  # noqa: RUF059
        pos = _pos(state=PositionLifecycleState.PARTIAL)
        pos.be_moved = True
        pos.partial_done = True
        pos.current_stop = Decimal("2302")
        pos.remaining_volume = Decimal("0.10")
        svc.register(pos)
        # atr 10 on mid 2325 → high; trail = 2325 - 15 = 2310
        result = svc.evaluate(100, _ctx(price=Decimal("2325"), atr=Decimal("10")))
        assert result.action is ManageActionKind.TRAIL
        assert result.position.current_stop == Decimal("2310.00")

    def test_never_move_stop_backwards(self) -> None:
        svc, oms = _svc()
        pos = _pos(state=PositionLifecycleState.TRAILING)
        pos.be_moved = True
        pos.partial_done = True
        pos.trailing_active = True
        pos.current_stop = Decimal("2320")
        pos.remaining_volume = Decimal("0.10")
        svc.register(pos)
        # price drops so trail would be worse
        result = svc.evaluate(100, _ctx(price=Decimal("2322"), atr=Decimal("5")))
        # trail candidate 2322-5=2317 < 2320 → NOOP
        assert result.action is ManageActionKind.NOOP
        assert oms.calls == []
        assert pos.current_stop == Decimal("2320")


@pytest.mark.unit
class TestTimeStop:
    def test_time_stop_closes(self) -> None:
        cfg = PositionManagementConfig(
            time_stop_minutes=30,
            time_stop_min_r=Decimal("0.5"),
        )
        svc, oms = _svc(config=cfg)
        pos = _pos(opened_at=OPENED)
        svc.register(pos)
        late = OPENED + timedelta(minutes=31)
        # price barely moved (0.2R)
        result = svc.evaluate(100, _ctx(price=Decimal("2302"), now=late))
        assert result.action is ManageActionKind.TIME_STOP
        assert result.position.state is PositionLifecycleState.EXITED
        assert oms.calls[0]["method"] == "close_position"


@pytest.mark.unit
class TestEmergencyAndShutdown:
    def test_emergency_structure_break(self) -> None:
        svc, oms = _svc()
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(price=Decimal("2305"), structure_broken=True))
        assert result.action is ManageActionKind.EMERGENCY_EXIT
        assert result.position.state is PositionLifecycleState.EXITED
        assert oms.calls[0]["method"] == "close_position"

    def test_daily_shutdown_kill_switch(self) -> None:
        svc, oms = _svc()  # noqa: RUF059
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(price=Decimal("2305"), kill_switch_armed=True))
        assert result.action is ManageActionKind.DAILY_SHUTDOWN
        assert result.position.state is PositionLifecycleState.EXITED

    def test_daily_loss_exceeded(self) -> None:
        svc, oms = _svc()  # noqa: RUF059
        svc.register(_pos())
        result = svc.evaluate(
            100, _ctx(price=Decimal("2305"), daily_loss_exceeded=True)
        )
        assert result.action is ManageActionKind.DAILY_SHUTDOWN


@pytest.mark.unit
class TestSafety:
    def test_duplicate_protection(self) -> None:
        svc, oms = _svc()
        svc.register(_pos())
        ctx = _ctx(price=Decimal("2310"))
        first = svc.evaluate(100, ctx)
        assert first.action is ManageActionKind.BREAK_EVEN
        # Force same fingerprint by resetting state but keeping fingerprint
        pos = svc.engine.get(100)
        assert pos is not None
        pos.state = PositionLifecycleState.OPEN
        pos.be_moved = False
        pos.current_stop = Decimal("2290")
        # last fingerprint still set → duplicate
        second = svc.evaluate(100, ctx)
        assert second.record is not None
        assert second.record.outcome is ManageOutcome.DUPLICATE
        assert len(oms.calls) == 1

    def test_never_manage_exited(self) -> None:
        svc, oms = _svc()
        pos = _pos(state=PositionLifecycleState.EXITED)
        pos.exit_reason = "done"
        svc.register(pos)
        result = svc.evaluate(100, _ctx(price=Decimal("2320")))
        assert result.skipped
        assert oms.calls == []

    def test_manually_closed_local_exit(self) -> None:
        svc, oms = _svc()
        svc.register(_pos())
        result = svc.evaluate(
            100, _ctx(price=Decimal("2305"), position_still_open=False)
        )
        assert result.action is ManageActionKind.SKIP
        assert result.position.state is PositionLifecycleState.EXITED
        assert oms.calls == []

    def test_mt5_modification_failure(self) -> None:
        oms = RecordingOmsManagePort(
            result=OmsManageResult(
                outcome="rejected",
                message="invalid stops",
                retcode=10016,
                oms_status="rejected",
                gateway_status="ok",
            )
        )
        svc, _ = _svc(oms)
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(price=Decimal("2310")))
        assert result.action is ManageActionKind.BREAK_EVEN
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.MT5_FAILURE
        assert result.position.state is PositionLifecycleState.OPEN  # unchanged

    def test_gateway_failure(self) -> None:
        oms = RecordingOmsManagePort(
            result=OmsManageResult(
                outcome="gateway_failure",
                message="unreachable",
                retcode=10031,
                oms_status="failed",
                gateway_status="failed",
            )
        )
        svc, _ = _svc(oms)
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(price=Decimal("2310")))
        assert result.record is not None
        assert result.record.outcome is ManageOutcome.GATEWAY_FAILURE

    def test_journal_persistence_fields(self) -> None:
        svc, _ = _svc()
        svc.register(_pos())
        result = svc.evaluate(100, _ctx(price=Decimal("2310")))
        row = result.record.to_dict() if result.record else {}
        for key in (
            "ticket",
            "action",
            "from_state",
            "to_state",
            "reason",
            "timestamp",
            "latency_ms",
            "outcome",
            "old_sl",
            "new_sl",
            "fingerprint",
        ):
            assert key in row

    def test_state_transition_sequence(self) -> None:
        svc, oms = _svc()
        svc.register(_pos())
        # BE at 1R
        r1 = svc.evaluate(100, _ctx(price=Decimal("2310")))
        assert r1.position.state is PositionLifecycleState.BE_MOVED
        # Partial at 2R
        r2 = svc.evaluate(100, _ctx(price=Decimal("2320")))
        assert r2.position.state is PositionLifecycleState.PARTIAL
        # Trail
        r3 = svc.evaluate(100, _ctx(price=Decimal("2325"), atr=Decimal("12")))
        assert r3.position.state is PositionLifecycleState.TRAILING
        assert [c["method"] for c in oms.calls] == [
            "modify_sltp",
            "partial_close",
            "modify_sltp",
        ]

    def test_metrics_snapshot(self) -> None:
        svc, _ = _svc()
        svc.register(_pos())
        svc.evaluate(100, _ctx(price=Decimal("2310")))
        snap = svc.engine.metrics.snapshot()
        assert snap["be_success"] == 1
        assert snap["evaluations"] >= 1
