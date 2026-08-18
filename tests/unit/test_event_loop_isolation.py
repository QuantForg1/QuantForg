"""Event-loop isolation — slow Gateway/ITE I/O must not starve liveness.

Does not change Safety, Risk, OMS, leverage, or execution policy.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import AsyncIterator
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.services.blocking_io_offload import (
    blocking_io_pool_size,
    get_blocking_io_executor,
    offload_blocking,
)
from app.application.services.institutional_ite_runtime import (
    InstitutionalIteRuntime,
    ShadowCycleResult,
)
from app.application.services.ite_cycle_market_context import (
    IteCycleMarketContext,
    build_ite_cycle_market_context,
)
from app.application.services.mt5_session_guard import (
    require_live_mt5_connection,
    reset_session_heal_lock_for_tests,
    session_heal_count,
)
from app.domain.exceptions.base import ServiceUnavailableError
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.routers.health import liveness
from tests.unit.test_mt5_session_consistency import FakeGatewayClient

pytestmark = [pytest.mark.unit]


@pytest.fixture(autouse=True)
def _reset_heal_lock() -> None:
    reset_session_heal_lock_for_tests()
    yield
    reset_session_heal_lock_for_tests()


def _probe_app() -> FastAPI:
    """Tiny ASGI app — real liveness handler, no ITE lifespan/middleware."""
    application = FastAPI()
    application.add_api_route("/health/live", liveness, methods=["GET"])

    @application.get("/api/v1/auth/me")
    async def _me() -> dict[str, str]:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    return application


@pytest.fixture
async def probe_client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=_probe_app())
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _liveness(client: AsyncClient) -> tuple[float, int]:
    t0 = time.perf_counter()
    res = await client.get("/health/live")
    return time.perf_counter() - t0, res.status_code


def _minimal_runtime() -> InstitutionalIteRuntime:
    runtime = InstitutionalIteRuntime(
        plane=MagicMock(),
        reliability=MagicMock(),
        probes=MagicMock(),
        guarded_submit=MagicMock(),
        guarded_manage=MagicMock(),
        execution=MagicMock(),
        position_management=MagicMock(),
    )
    runtime.plane.mode = OpsExecutionMode.LIVE
    runtime.probes.last_health_payload = None
    runtime.probes.mt5_adapter = None
    return runtime


@pytest.mark.unit
def test_blocking_io_pool_is_bounded() -> None:
    pool = get_blocking_io_executor()
    assert blocking_io_pool_size() == 5
    assert pool._max_workers == blocking_io_pool_size()
    assert blocking_io_pool_size() < 32


@pytest.mark.asyncio
async def test_slow_gateway_offload_does_not_block_health_live(
    probe_client: AsyncClient,
) -> None:
    def slow_gateway() -> str:
        time.sleep(0.8)
        return "ok"

    async def blocker() -> str:
        return await offload_blocking(slow_gateway)

    block_task = asyncio.create_task(blocker())
    await asyncio.sleep(0.05)
    elapsed, status = await _liveness(probe_client)
    assert status == 200
    assert elapsed < 0.4, f"liveness stalled {elapsed:.3f}s during Gateway I/O"
    assert await block_task == "ok"


@pytest.mark.asyncio
async def test_slow_scanner_does_not_block_auth_me(probe_client: AsyncClient) -> None:
    """Scanner catalogue I/O is offloaded; /auth/me stays responsive (401 unauth)."""

    def slow_catalogue(_adapter: object) -> tuple[dict[str, object], ...]:
        time.sleep(0.8)
        return ()

    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    adapter.copy_rates_from_pos.return_value = []

    async def scanner() -> None:
        with patch(
            "app.domain.institutional_trading.ai_scalping.universe_discovery.fetch_broker_symbol_rows",
            slow_catalogue,
        ):
            await build_ite_cycle_market_context(adapter)

    scan_task = asyncio.create_task(scanner())
    await asyncio.sleep(0.05)
    t0 = time.perf_counter()
    res = await probe_client.get("/api/v1/auth/me")
    elapsed = time.perf_counter() - t0
    assert res.status_code in {401, 403}
    assert elapsed < 0.5, f"/auth/me stalled {elapsed:.3f}s during scanner I/O"
    await scan_task


@pytest.mark.asyncio
async def test_concurrent_mt5_reads_do_not_block_liveness(
    probe_client: AsyncClient,
) -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient(delay_s=0.6)
    adapter = MT5Adapter(client=client)
    user_id = uuid4()

    async def book_read() -> None:
        await require_live_mt5_connection(factory, adapter, user_id)

    reads = [asyncio.create_task(book_read()) for _ in range(4)]
    await asyncio.sleep(0.05)
    elapsed, status = await _liveness(probe_client)
    assert status == 200
    assert elapsed < 0.4, f"liveness stalled {elapsed:.3f}s during MT5 reads"
    await asyncio.gather(*reads)


@pytest.mark.asyncio
async def test_execute_now_runs_cycle_off_the_event_loop(
    probe_client: AsyncClient,
) -> None:
    runtime = _minimal_runtime()
    cycle_threads: list[str] = []

    async def _pick() -> str:
        return "EURUSD_I"

    runtime._pick_executable_symbol_async = _pick  # type: ignore[method-assign]

    ctx = IteCycleMarketContext(
        ok=True,
        snapshot=SimpleNamespace(symbol="EURUSD_I"),
        account=SimpleNamespace(),
        reason="ok",
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
        diagnostics={},
    )

    async def _ctx(*_a: object, **_k: object) -> IteCycleMarketContext:
        return ctx

    def slow_cycle(**_kwargs: object) -> ShadowCycleResult:
        cycle_threads.append(threading.current_thread().name)
        time.sleep(0.8)
        result = ShadowCycleResult(
            ok=True, trace_id=None, mode="LIVE", detail="offload"
        )
        runtime._last_cycle = result
        return result

    runtime.run_auto_cycle = slow_cycle  # type: ignore[method-assign]

    with patch(
        "app.application.services.ite_cycle_market_context.build_ite_cycle_market_context",
        _ctx,
    ):
        cycle_task = asyncio.create_task(runtime.execute_now())
        await asyncio.sleep(0.08)
        elapsed, status = await _liveness(probe_client)
        assert status == 200
        assert elapsed < 0.4, f"liveness stalled {elapsed:.3f}s during execute_now"
        payload = await cycle_task

    assert payload.get("status") is not None or payload.get("success") is not None
    assert cycle_threads, "run_auto_cycle never ran"
    assert any(
        name.startswith("qf-blocking-io") for name in cycle_threads
    ), f"cycle ran on {cycle_threads} — expected bounded I/O pool"


@pytest.mark.asyncio
async def test_saturated_pool_does_not_deadlock_liveness(
    probe_client: AsyncClient,
) -> None:
    n = blocking_io_pool_size()
    count_lock = threading.Lock()
    n_entered = 0

    loop = asyncio.get_running_loop()
    aio_entered = asyncio.Event()

    def occupy() -> None:
        nonlocal n_entered
        with count_lock:
            n_entered += 1
            if n_entered >= n:
                loop.call_soon_threadsafe(aio_entered.set)
        time.sleep(0.5)

    tasks = [asyncio.create_task(offload_blocking(occupy)) for _ in range(n)]
    await asyncio.wait_for(aio_entered.wait(), timeout=2.0)
    elapsed, status = await _liveness(probe_client)
    assert status == 200
    assert elapsed < 0.4, f"liveness starved {elapsed:.3f}s while ITE pool was full"
    await asyncio.gather(*tasks)


@pytest.mark.asyncio
async def test_event_loop_ticker_survives_offloaded_sleep() -> None:
    ticks: list[float] = []

    async def ticker() -> None:
        for _ in range(12):
            ticks.append(time.perf_counter())
            await asyncio.sleep(0.04)

    await asyncio.gather(ticker(), offload_blocking(time.sleep, 0.5))
    assert len(ticks) >= 8, f"event loop starved — only {len(ticks)} ticks"


@pytest.mark.asyncio
async def test_session_guard_still_heals_stale_uuid() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    adapter = MT5Adapter(client=client)
    user_id = uuid4()
    from app.domain.entities.mt5 import MT5Connection

    stale = MT5Connection.create(
        user_id=user_id, login=16785006, server="Weltrade-Real"
    )
    stale.mark_connected(session_ref="stale-db-uuid-from-previous-worker")
    async with factory() as uow:
        await uow.connections.upsert_for_user(stale)
        await uow.commit()
    healed = await require_live_mt5_connection(factory, adapter, user_id)
    assert healed.session_ref != "stale-db-uuid-from-previous-worker"
    assert adapter.is_live_session(healed.session_ref)
    assert healed.connected is True


@pytest.mark.asyncio
async def test_real_disconnect_still_503_not_false_404() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient()
    client._connected = False
    adapter = MT5Adapter(client=client)
    with pytest.raises(ServiceUnavailableError) as exc:
        await require_live_mt5_connection(factory, adapter, uuid4())
    assert exc.value.code in {"MT5_UNAVAILABLE", "GATEWAY_UNAVAILABLE"}
    assert "No active MT5 connection" not in exc.value.message


@pytest.mark.asyncio
async def test_concurrent_heals_do_not_duplicate_gateway_attach() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    client = FakeGatewayClient(delay_s=0.2)
    adapter = MT5Adapter(client=client)
    user_id = uuid4()
    before = session_heal_count()
    results = await asyncio.gather(
        *[require_live_mt5_connection(factory, adapter, user_id) for _ in range(5)]
    )
    assert all(r.connected for r in results)
    assert session_heal_count() - before == 1
    assert client.attach_calls <= 1
