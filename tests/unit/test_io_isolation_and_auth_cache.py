"""16 Nov 2026 login timeouts: broker reads starved Supabase auth threads.

- Auth, broker reads and research run on separate bounded pools.
- Broker reads fail fast (503) when their pool is saturated.
- A verified user is reused briefly per token; logout evicts it.
- The Robot Control Center lists accounts even when broker evidence hangs.
"""

from __future__ import annotations

import asyncio
import base64
import json
import threading
import time
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.application.services import blocking_io_offload as io
from app.infrastructure.brokers.mt5.gateway_circuit import GatewayUnavailableError


def test_auth_runs_while_broker_reads_hang() -> None:
    release = threading.Event()

    async def scenario() -> float:
        hung = [
            asyncio.create_task(io.run_broker_read(release.wait, 5))
            for _ in range(io.BROKER_READ.workers)
        ]
        await asyncio.sleep(0.05)
        t0 = time.monotonic()
        assert await io.run_auth_io(lambda: "ok") == "ok"
        took = time.monotonic() - t0
        release.set()
        await asyncio.gather(*hung)
        return took

    assert asyncio.run(scenario()) < 0.5


def test_broker_reads_fail_fast_when_saturated() -> None:
    release = threading.Event()

    async def scenario() -> None:
        assert io.BROKER_READ.admit is not None
        hung = [
            asyncio.create_task(io.run_broker_read(release.wait, 5))
            for _ in range(io.BROKER_READ.admit - io.BROKER_READ.inflight)
        ]
        await asyncio.sleep(0.05)
        with pytest.raises(GatewayUnavailableError):
            await io.run_broker_read(lambda: None)
        release.set()
        await asyncio.gather(*hung, return_exceptions=True)

    asyncio.run(scenario())


def test_auth_adapter_uses_auth_pool() -> None:
    import inspect

    from app.infrastructure.auth import supabase_auth

    src = inspect.getsource(supabase_auth)
    assert "asyncio.to_thread(" not in src
    assert "run_auth_io(" in src


def _token(exp: float) -> str:
    body = base64.urlsafe_b64encode(json.dumps({"exp": exp}).encode()).decode()
    return f"h.{body.rstrip('=')}.s"


class _Auth:
    def __init__(self) -> None:
        self.calls = 0

    async def me(self, *, access_token: str) -> Any:
        self.calls += 1
        return SimpleNamespace(id=uuid4(), token=access_token)


def test_current_user_cached_per_token_and_evicted_on_logout() -> None:
    from app.presentation.dependencies import auth as dep

    svc = _Auth()
    tok = _token(time.time() + 3600)
    first = asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    again = asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    assert first is again and svc.calls == 1
    other = asyncio.run(dep.get_current_user(_token(time.time() + 3600) + "x", svc))  # type: ignore[arg-type]
    assert other is not first and svc.calls == 2
    dep.evict_cached_user(tok)
    asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    assert svc.calls == 3


def test_expired_token_is_not_served_from_cache() -> None:
    from app.presentation.dependencies import auth as dep

    svc = _Auth()
    tok = _token(time.time() - 1)
    asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    assert svc.calls == 2


def test_cache_ttl_expires(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.presentation.dependencies import auth as dep

    svc = _Auth()
    tok = _token(time.time() + 3600)
    asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    base = time.monotonic()
    monkeypatch.setattr(dep.time, "monotonic", lambda: base + dep._USER_CACHE_TTL_S + 1)
    asyncio.run(dep.get_current_user(tok, svc))  # type: ignore[arg-type]
    assert svc.calls == 2


def test_rcc_accounts_load_when_evidence_hangs(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.application.services import robot_control_service as rc
    from app.presentation.routers import robot_control as router

    acct = {"broker_account_id": str(uuid4()), "_login": "123", "state": "RUNNING"}
    monkeypatch.setattr(rc, "list_accounts", lambda **_: [dict(acct)])
    monkeypatch.setattr(rc, "recent_events", lambda **_: [])
    monkeypatch.setattr(router, "EVIDENCE_TIMEOUT_S", 0.2)
    monkeypatch.setattr(router, "_gateway_account", lambda: time.sleep(2))
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    user = SimpleNamespace(id=uuid4())
    t0 = time.monotonic()
    out = asyncio.run(router.my_robot_accounts(user, request))  # type: ignore[arg-type]
    assert time.monotonic() - t0 < 1.5
    assert out["broker_evidence"] == "unavailable"
    assert out["accounts"][0]["connection"]["state"] == rc.UNAVAILABLE


def test_unavailable_never_reports_connected() -> None:
    from app.application.services import robot_control_service as rc

    state = rc.connection_state(
        {"id": "a", "external_account_id": "1"},
        gateway_account=None,
        workers=[],
        evidence_available=False,
    )
    assert state["state"] == rc.UNAVAILABLE


def test_abandoned_hung_read_still_holds_capacity() -> None:
    release = threading.Event()

    async def scenario() -> None:
        base = io.BROKER_READ.inflight
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(io.run_broker_read(release.wait, 5), timeout=0.05)
        assert io.BROKER_READ.inflight == base + 1
        release.set()
        for _ in range(100):
            if io.BROKER_READ.inflight <= base:
                break
            await asyncio.sleep(0.01)
        assert io.BROKER_READ.inflight <= base

    asyncio.run(scenario())
