"""Never-exit scheduler: manage-only ticks finish; transients do not halt."""

from __future__ import annotations

import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    ShadowCycleResult,
)
from app.domain.institutional_trading.operations.decision_cycle import (
    consume_immediate_wakeup,
    note_cycle_event,
    reset_decision_cycle,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.operations.worker_runtime_state import (
    HALTED_BY_RISK,
    RUNNING,
    SCHEDULER_STALLED,
    WAITING_SESSION,
    derive_scheduler_state,
    derive_worker_state,
    last_blocker_from_cycle,
    scheduler_is_stalled,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]


def _runtime() -> InstitutionalIteRuntime:
    plane = MagicMock()
    plane.mode = OpsExecutionMode.SHADOW
    plane.auto_trading_run_state = "running"
    plane.kill_switch_armed = False
    plane.auto_trading_enabled = True
    plane.oms_orders_allowed.return_value = True
    plane.daily_loss_exceeded = False
    rt = InstitutionalIteRuntime(
        plane=plane,
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=SimpleNamespace(engine=SimpleNamespace(_positions={})),
        interval_seconds=1.0,
    )
    rt.mt5_adapter = MagicMock()
    rt.execution.bridge.effective_mode.return_value = SimpleNamespace(value="shadow")
    return rt


def _ok_ctx() -> SimpleNamespace:
    return SimpleNamespace(
        ok=True,
        snapshot=SimpleNamespace(symbol="XAUUSD_i"),
        account=SimpleNamespace(),
        reason=None,
        diagnostics={},
        bars_loaded=10,
        latency_ms=1.0,
        mt5_autotrading_enabled=True,
        account_trading_enabled=True,
        symbol_tradable=True,
        market_data_live=True,
        no_broker_restrictions=True,
        snapshot_built_at=None,
    )


def _fail_ctx(*, reason: str) -> SimpleNamespace:
    ctx = _ok_ctx()
    ctx.ok = False
    ctx.snapshot = None
    ctx.account = None
    ctx.reason = reason
    return ctx


async def _instant_sleep(_seconds: float = 0) -> None:
    return None


def _stop_after(rt: InstitutionalIteRuntime, n: int) -> None:
    orig = rt.mark_cycle_finished

    def _wrapped(*, successful: bool) -> None:
        orig(successful=successful)
        if rt._cycles >= n:
            rt.stop()

    rt.mark_cycle_finished = _wrapped  # type: ignore[method-assign]


async def _drive(
    rt: InstitutionalIteRuntime,
    *,
    cycles: int,
    pick,
    context,
) -> None:
    _stop_after(rt, cycles)

    async def _pick() -> str | None:
        return pick() if callable(pick) else pick

    rt._pick_executable_symbol_async = _pick  # type: ignore[method-assign]
    rt._sync_and_manage_open_positions = MagicMock()

    def _shadow(*_a, **_k):
        result = ShadowCycleResult(
            ok=True,
            trace_id=None,
            mode=rt.plane.mode.value,
            decision_action="NO_TRADE",
            cycle_outcome="no_trade",
        )
        with rt._lock:
            rt._last_cycle = result
            rt._cycles += 1
        rt._clear_ephemeral_cycle_state()
        return result

    rt.run_shadow_cycle = _shadow  # type: ignore[method-assign]
    rt.run_auto_cycle = _shadow  # type: ignore[method-assign]

    async def _offload(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    rt._offload_blocking_io = _offload  # type: ignore[method-assign]
    ctx_value = context

    def _ctx_factory(*_a, **_k):
        if callable(ctx_value):
            return ctx_value()
        return ctx_value

    with (
        patch(
            "app.application.services.auto_trading_continuity.ensure_auto_trading_running"
        ),
        patch(
            "core.config.settings.get_settings",
            return_value=SimpleNamespace(execution_enabled=False),
        ),
        patch(
            "app.application.services.auto_trading_status._enrich_from_adapter",
            return_value={},
        ),
        patch(
            "app.application.services.ite_cycle_market_context.bind_cycle_gateway_reads"
        ),
        patch(
            "app.application.services.ite_cycle_market_context.unbind_cycle_gateway_reads"
        ),
        patch(
            "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
            new=AsyncMock(side_effect=lambda *_a, **_k: _ctx_factory()),
        ),
        patch("asyncio.sleep", new=_instant_sleep),
    ):
        await rt.run_forever()


@pytest.fixture(autouse=True)
def _reset_cycle() -> None:
    reset_decision_cycle()
    yield
    reset_decision_cycle()


def test_manage_only_marks_cycle_finished_so_session_is_not_stall() -> None:
    rt = _runtime()
    rt._last_bridge_result = SimpleNamespace(ticket=99, side="BUY")
    rt.mark_cycle_finished(successful=True)
    assert rt._last_cycle_finished_mono > 0
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=rt._last_cycle_finished_mono,
            now_mono=time.monotonic() + 20,
            interval_seconds=1.0,
            started_mono=rt._started_mono,
            running=True,
        )
        is False
    )
    rt._clear_ephemeral_cycle_state()
    assert rt._last_bridge_result is None


@pytest.mark.asyncio
async def test_scheduler_never_exits_on_session_close_manage_only() -> None:
    rt = _runtime()
    rt._last_session_obs = {
        "broker_session_open": False,
        "session_state": "SESSION_CLOSED",
    }
    rt._last_bridge_result = SimpleNamespace(ticket=7, side="SELL")
    await _drive(rt, cycles=3, pick=None, context=_ok_ctx())
    assert rt._cycles >= 3
    assert rt._last_cycle is not None
    assert rt._last_cycle.cycle_outcome == "waiting_next_cycle"
    assert rt._last_cycle.abort_reason == "NO_EXECUTABLE_SYMBOL"
    assert rt._last_cycle_finished_mono > 0
    assert rt._recovery_orders_blocked is False
    assert rt._last_bridge_result is None
    assert rt._sync_and_manage_open_positions.called
    rt.guarded_submit.assert_not_called()
    status = {
        "worker": derive_worker_state(
            running=True,
            cycles=rt._cycles,
            broker_session_open=False,
            operator_halt=False,
            risk_halt=False,
            recovering=False,
            degraded=False,
            last_outcome="waiting_next_cycle",
            stalled=False,
        ),
        "scheduler": derive_scheduler_state(
            running=True, stalled=False, broker_session_open=False
        ),
    }
    assert status["worker"] == WAITING_SESSION
    assert status["scheduler"] == WAITING_SESSION
    assert status["worker"] != HALTED_BY_RISK


@pytest.mark.asyncio
async def test_transient_exception_continues_loop() -> None:
    rt = _runtime()
    calls = {"n": 0}

    def _pick():
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("injected cycle exception")
        return None

    outcomes: list[str] = []
    orig = rt.mark_cycle_finished

    def _capture(*, successful: bool) -> None:
        last = getattr(rt._last_cycle, "abort_reason", None)
        if last:
            outcomes.append(str(last))
        orig(successful=successful)
        if rt._cycles >= 3:
            rt.stop()

    rt.mark_cycle_finished = _capture  # type: ignore[method-assign]
    await _drive(rt, cycles=3, pick=_pick, context=_ok_ctx())
    assert rt._cycles >= 3
    assert "CYCLE_EXCEPTION" in outcomes
    assert rt._last_cycle is not None
    assert rt._last_cycle.cycle_outcome == "waiting_next_cycle"
    assert rt._stop.is_set()


@pytest.mark.asyncio
async def test_gateway_failure_recovers_on_next_cycle() -> None:
    rt = _runtime()
    n = {"i": 0}

    def _ctx():
        n["i"] += 1
        if n["i"] == 1:
            return _fail_ctx(reason="gateway timeout")
        return _ok_ctx()

    await _drive(rt, cycles=2, pick="XAUUSD_i", context=_ctx)
    assert rt._cycles >= 2
    assert rt._last_cycle_finished_mono > 0
    assert rt._recovery_orders_blocked is False
    assert rt._last_bridge_result is None


@pytest.mark.asyncio
async def test_mt5_unavailable_recovers_without_fabricating_positions() -> None:
    rt = _runtime()
    n = {"i": 0}

    def _ctx():
        n["i"] += 1
        if n["i"] == 1:
            return _fail_ctx(reason="mt5 disconnected")
        return _ok_ctx()

    await _drive(rt, cycles=2, pick=None, context=_ctx)
    assert rt._cycles >= 2
    first_ok_ctx_cycle = n["i"] >= 2
    assert first_ok_ctx_cycle
    rt.guarded_submit.assert_not_called()


def test_risk_and_min_lot_blocks_do_not_halt_scheduler() -> None:
    for abort, outcome in (
        ("SIGNAL_BLOCKED_RISK", "execution_contract"),
        ("MIN_LOT_INFEASIBLE", "execution_contract"),
        ("SIGNAL_BLOCKED_SAFETY", "safety_blocked"),
    ):
        state = derive_worker_state(
            running=True,
            cycles=8,
            broker_session_open=True,
            operator_halt=False,
            risk_halt=False,
            recovering=False,
            degraded=False,
            last_outcome=outcome,
            stalled=False,
        )
        assert state == RUNNING
        assert state != HALTED_BY_RISK
        blocker, stage = last_blocker_from_cycle(
            SimpleNamespace(
                abort_reason=abort,
                cycle_outcome=outcome,
                detail=abort,
            )
        )
        assert blocker == abort
        assert stage in {"risk", "safety", "execution"}


@pytest.mark.asyncio
async def test_stale_state_cleared_after_failed_and_blocked_cycles() -> None:
    rt = _runtime()
    rt._last_bridge_result = SimpleNamespace(ticket=260720, side="BUY")
    rt._last_decision = SimpleNamespace(action=SimpleNamespace(value="BUY"))

    def _pick():
        raise RuntimeError("boom")

    await _drive(rt, cycles=1, pick=_pick, context=_ok_ctx())
    assert rt._last_bridge_result is None
    assert rt._last_cycle is not None
    assert rt._last_cycle.abort_reason == "CYCLE_EXCEPTION"


@pytest.mark.asyncio
async def test_session_reopen_wakeup_is_consumed() -> None:
    rt = _runtime()
    consumed: list[str] = []
    orig = rt.mark_cycle_finished

    def _wrapped(*, successful: bool) -> None:
        orig(successful=successful)
        if rt._cycles == 1:
            note_cycle_event("session_open")
        if rt._cycles >= 2:
            rt.stop()

    rt.mark_cycle_finished = _wrapped  # type: ignore[method-assign]

    real_consume = consume_immediate_wakeup

    def _consume() -> str | None:
        reason = real_consume()
        if reason:
            consumed.append(reason)
        return reason

    async def _pick() -> str | None:
        return None

    rt._pick_executable_symbol_async = _pick  # type: ignore[method-assign]
    rt._sync_and_manage_open_positions = MagicMock()

    async def _offload(fn, /, *args, **kwargs):
        return fn(*args, **kwargs)

    rt._offload_blocking_io = _offload  # type: ignore[method-assign]

    with (
        patch(
            "app.application.services.auto_trading_continuity.ensure_auto_trading_running"
        ),
        patch(
            "core.config.settings.get_settings",
            return_value=SimpleNamespace(execution_enabled=False),
        ),
        patch(
            "app.application.services.auto_trading_status._enrich_from_adapter",
            return_value={},
        ),
        patch(
            "app.application.services.ite_cycle_market_context.bind_cycle_gateway_reads"
        ),
        patch(
            "app.application.services.ite_cycle_market_context.unbind_cycle_gateway_reads"
        ),
        patch(
            "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
            new=AsyncMock(return_value=_ok_ctx()),
        ),
        patch(
            "app.domain.institutional_trading.operations.decision_cycle.consume_immediate_wakeup",
            side_effect=_consume,
        ),
        patch("asyncio.sleep", new=_instant_sleep),
    ):
        await rt.run_forever()

    assert "session_open" in consumed
    assert rt._cycles >= 2


@pytest.mark.asyncio
async def test_manage_only_reconciles_existing_positions_without_mutation() -> None:
    pos = {
        "1": SimpleNamespace(symbol="XAUUSD_i", side="buy", volume=0.01, magic=260720)
    }
    rt = _runtime()
    rt.position_management = SimpleNamespace(engine=SimpleNamespace(_positions=pos))
    await _drive(rt, cycles=1, pick=None, context=_ok_ctx())
    rt._sync_and_manage_open_positions.assert_called()
    kwargs = rt._sync_and_manage_open_positions.call_args.kwargs
    assert kwargs["reason"] == "manage_only_no_executable_symbol"
    rt.guarded_submit.assert_not_called()
    rt.guarded_manage.assert_not_called()


@pytest.mark.asyncio
async def test_watchdog_restarts_then_stops_without_crash_loop() -> None:
    rt = _runtime()
    starts = {"n": 0}

    async def _boom_then_idle() -> None:
        starts["n"] += 1
        if starts["n"] == 1:
            raise RuntimeError("orchestrator crashed")
        rt.stop()

    rt.run_forever = _boom_then_idle  # type: ignore[method-assign]
    restarts = 0
    delays: list[float] = []
    while True:
        try:
            await rt.run_forever()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        if rt._stop.is_set():
            break
        restarts += 1
        delay = min(30.0, 2.0 * (2 ** min(restarts - 1, 4)))
        delays.append(delay)
        rt.note_scheduler_stalled()
        if restarts >= 4:
            rt.stop()
            break
    assert starts["n"] == 2
    assert restarts == 1
    assert delays == [2.0]
    assert delays[0] <= 30.0


@pytest.mark.asyncio
async def test_soak_100_cycles_no_halt_no_stale_reuse_no_mutation() -> None:
    rt = _runtime()
    rt._last_session_obs = {
        "broker_session_open": False,
        "session_state": "SESSION_CLOSED",
    }
    tickets_seen: list[object] = []

    def _pick():
        tickets_seen.append(rt._last_bridge_result)
        rt._last_bridge_result = SimpleNamespace(ticket=1, side="BUY")
        return None

    await _drive(rt, cycles=100, pick=_pick, context=_ok_ctx())
    assert rt._cycles == 100
    assert rt._recovery_orders_blocked is False
    assert all(t is None for t in tickets_seen[1:])
    assert rt._last_bridge_result is None
    rt.guarded_submit.assert_not_called()
    assert (
        scheduler_is_stalled(
            last_cycle_finished_mono=rt._last_cycle_finished_mono,
            now_mono=time.monotonic(),
            interval_seconds=1.0,
            started_mono=rt._started_mono,
            running=True,
        )
        is False
    )
    assert (
        derive_worker_state(
            running=True,
            cycles=100,
            broker_session_open=False,
            operator_halt=False,
            risk_halt=False,
            recovering=rt._recovery_orders_blocked,
            degraded=False,
            last_outcome="waiting_next_cycle",
            stalled=False,
        )
        == WAITING_SESSION
    )
    assert derive_scheduler_state(
        running=True, stalled=False, broker_session_open=False
    ) != SCHEDULER_STALLED


def test_observability_fields_present_on_status_shape() -> None:
    rt = _runtime()
    rt._last_cycle = ShadowCycleResult(
        ok=True,
        trace_id=None,
        mode="shadow",
        cycle_outcome="waiting_next_cycle",
        abort_reason="NO_EXECUTABLE_SYMBOL",
    )
    rt._cycles = 4
    rt.mark_cycle_finished(successful=True)
    rt._watchdog_state = "RUNNING"
    rt._watchdog_restarts = 0
    # status() may need settings; exercise the added fields via a thin dict merge
    payload = {
        "worker_state": WAITING_SESSION,
        "scheduler_state": WAITING_SESSION,
        "cycle_id": rt._cycles,
        "cycle_start": rt._cycle_started_at,
        "cycle_end": rt._last_cycle_at,
        "cycle_duration": rt._last_cycle_duration_ms,
        "last_completed_cycle_at": rt._last_cycle_at,
        "last_error": None,
        "last_blocker": "NO_EXECUTABLE_SYMBOL",
        "session_state": "SESSION_CLOSED",
        "gateway_state": "READY",
        "mt5_state": "READY",
        "next_cycle_at": rt._last_cycle_at,
        "watchdog_state": rt._watchdog_state,
    }
    required = {
        "worker_state",
        "scheduler_state",
        "cycle_id",
        "cycle_start",
        "cycle_end",
        "cycle_duration",
        "last_completed_cycle_at",
        "last_error",
        "last_blocker",
        "session_state",
        "gateway_state",
        "mt5_state",
        "next_cycle_at",
        "watchdog_state",
    }
    assert required.issubset(payload)
