"""Broker ownership persistence, claim, and account-switch safety."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

import pytest

from app.application.services.account_execution_gate import (
    ACCOUNT_SWITCH_IN_PROGRESS,
    begin_account_switch,
    reset_execution_binding_for_tests,
    submit_blocked_reason,
)
from app.application.services.broker_secret_store import BrokerSecretStore
from app.application.services.live_account_risk_tracker import LiveAccountRiskTracker
from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.entities.mt5 import MT5Connection
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from app.infrastructure.brokers.mt5.gateway_client import GatewayMT5Client
from app.infrastructure.persistence.memory_broker import MemoryBrokerUnitOfWorkFactory
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.broker_trader_errors import classify_broker_connect_error

_SECRET = "unit-test-encryption-key-32chars!"


class _Gateway(GatewayMT5Client):
    def __init__(self) -> None:
        super().__init__(base_url="http://gateway.test:8765", token="tok")
        self._positions: list[dict[str, Any]] = []
        self._orders: list[dict[str, Any]] = []
        self._trade_mode = ""

    def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> dict[str, Any]:
        _ = auth, params
        if path == "/health":
            return {
                "status": "ok",
                "connected": self._connected,
                "session_mode": self._session_mode,
                "server": self._server or None,
            }
        if path == "/session/status":
            return {
                "connected": self._connected,
                "login": self._login,
                "server": self._server,
                "session_mode": self._session_mode,
                "health": {"connected": self._connected, "login_status": "ok"},
            }
        if path == "/session/attach":
            self._connected = True
            self._session_mode = "attached"
            return {
                "connected": True,
                "login": self._login,
                "server": self._server,
                "session_mode": "attached",
            }
        if path == "/session/connect":
            assert json_body is not None
            self._connected = True
            self._login = int(json_body["login"])
            self._server = str(json_body["server"])
            self._session_mode = "connected"
            return {
                "connected": True,
                "login": self._login,
                "server": self._server,
                "session_mode": "connected",
            }
        if path == "/session/disconnect":
            self._connected = False
            self._login = 0
            return {"connected": False}
        if path == "/account":
            body: dict[str, Any] = {
                "login": self._login,
                "balance": "1000",
                "equity": "1000",
                "margin": "0",
                "free_margin": "1000",
                "currency": "USD",
                "server": self._server,
                "name": "Desk",
                "leverage": 100,
            }
            if self._trade_mode:
                body["account_mode"] = self._trade_mode
            return body
        if path == "/positions":
            return {"items": list(self._positions)}
        if path == "/orders":
            return {"items": list(self._orders)}
        if path == "/history/deals":
            return {"items": []}
        if path == "/diagnostics":
            return {"connected": self._connected}
        if path == "/heartbeat":
            return {"ok": True, "ping_ms": 1}
        if path == "/symbols":
            return {"items": []}
        raise RuntimeError(f"unexpected {method} {path}")


def _service(
    client: _Gateway | None = None,
    *,
    with_secrets: bool = False,
) -> tuple[WeltradeIntegrationService, MemoryMT5UnitOfWorkFactory, _Gateway]:
    gateway = client or _Gateway()
    factory = MemoryMT5UnitOfWorkFactory()
    broker_factory = MemoryBrokerUnitOfWorkFactory() if with_secrets else None
    svc = WeltradeIntegrationService(
        adapter=MT5Adapter(client=gateway),
        uow_factory=factory,
        broker_uow_factory=broker_factory,
    )
    if with_secrets:
        svc._broker_secret_key_override = _SECRET
    return svc, factory, gateway


@pytest.fixture(autouse=True)
def _reset_gate() -> None:
    reset_execution_binding_for_tests()


@pytest.mark.unit
@pytest.mark.asyncio
async def test_connect_persists_ownership_across_a_new_service() -> None:
    svc, factory, gateway = _service()
    gateway._connected = True
    gateway._login = 10001
    gateway._server = "Weltrade-Real"
    gateway._session_mode = "attached"
    user = uuid4()
    result = await svc.connect(
        user_id=user,
        login=10001,
        password="",
        server="Weltrade-Real",
        account_type="live",
    )
    assert result["ok"] is True
    assert "unit-secret" not in json.dumps(result)
    async with factory() as uow:
        row = await uow.connections.get_active_for_user(user)
    assert row is not None and row.connected is True
    assert int(row.login) == 10001

    restarted = _Gateway()
    restarted._connected = True
    restarted._login = 10001
    restarted._server = "Weltrade-Real"
    restarted._session_mode = "attached"
    restarted._session_token = ""
    again = WeltradeIntegrationService(
        adapter=MT5Adapter(client=restarted),
        uow_factory=factory,
    )
    again.adapter._live_session_ref = None
    diag = await again.ensure_user_session_bound(user_id=user, role="owner")
    assert diag.get("adopted") is True
    async with factory() as uow:
        kept = await uow.connections.get_active_for_user(user)
    assert kept is not None and int(kept.login) == 10001


@pytest.mark.unit
@pytest.mark.asyncio
async def test_trader_claim_does_not_adopt_an_unowned_gateway() -> None:
    svc, factory, gateway = _service()
    gateway._connected = True
    gateway._login = 10001
    gateway._server = "Weltrade-Real"
    gateway._session_mode = "attached"
    stranger = uuid4()
    with pytest.raises(RuntimeError, match="OWNERSHIP_CLAIM_FAILED"):
        await svc.claim_live_session(user_id=stranger, role="trader")
    async with factory() as uow:
        assert await uow.connections.get_active_for_user(stranger) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owner_claim_persists_and_blocks_a_live_foreign_owner() -> None:
    svc, factory, gateway = _service()
    gateway._connected = True
    gateway._login = 10001
    gateway._server = "Weltrade-Real"
    gateway._session_mode = "attached"
    owner = uuid4()
    claimed = await svc.claim_live_session(user_id=owner, role="owner")
    assert claimed["owned"] is True
    assert claimed["ownership"] == "owned"
    assert "password" not in claimed
    other = uuid4()
    with pytest.raises(RuntimeError, match="OWNERSHIP_CLAIM_FAILED"):
        await svc.claim_live_session(user_id=other, role="owner")
    async with factory() as uow:
        assert await uow.connections.get_active_for_user(other) is None
        assert (await uow.connections.get_active_for_user(owner)) is not None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_switch_with_open_position_requires_confirmation() -> None:
    svc, factory, gateway = _service()
    gateway._connected = True
    gateway._login = 10001
    gateway._server = "Weltrade-Real"
    gateway._session_mode = "attached"
    gateway._positions = [
        {
            "ticket": 7,
            "symbol": "XAUUSD",
            "type": 0,
            "volume": "0.01",
            "price_open": "2300",
            "price_current": "2301",
            "sl": "2290",
            "tp": "2320",
            "profit": "1",
            "time": 1_700_000_000,
        }
    ]
    user = uuid4()
    await svc.connect(
        user_id=user,
        login=10001,
        password="",
        server="Weltrade-Real",
        account_type="live",
    )
    with pytest.raises(RuntimeError, match="OPEN_EXPOSURE"):
        await svc.connect(
            user_id=user,
            login=10002,
            password="desk-secret",
            server="Weltrade-Real",
            account_type="live",
            confirm_leave_exposure=False,
        )
    assert gateway._login == 10001
    switched = await svc.connect(
        user_id=user,
        login=10002,
        password="desk-secret",
        server="Weltrade-Real",
        account_type="live",
        confirm_leave_exposure=True,
    )
    assert switched["ok"] is True
    assert gateway._login == 10002
    assert "desk-secret" not in json.dumps(switched)
    async with factory() as uow:
        rows = await uow.connections.list_for_user(user)
        live = [row for row in rows if row.connected]
    assert len(live) == 1
    assert int(live[0].login) == 10002


@pytest.mark.unit
@pytest.mark.asyncio
async def test_password_login_can_transfer_a_foreign_row(
    caplog: pytest.LogCaptureFixture,
) -> None:
    svc, factory, gateway = _service(with_secrets=True)
    gateway._fail = False
    other = uuid4()
    owner = uuid4()
    async with factory() as uow:
        foreign = MT5Connection.create(
            user_id=other,
            login=10002,
            server="Weltrade-Real",
            terminal_path="",
        )
        foreign.mark_connected(session_ref="sess-held")
        await uow.connections.upsert_for_user(foreign)
        await uow.commit()
    caplog.set_level("INFO")
    result = await svc.connect(
        user_id=owner,
        login=10002,
        password="desk-secret",
        server="Weltrade-Real",
        account_type="live",
    )
    assert result["ok"] is True
    assert "desk-secret" not in caplog.text
    async with factory() as uow:
        foreign_row = await uow.connections.get_active_for_user(other)
        owner_row = await uow.connections.get_active_for_user(owner)
    assert foreign_row is None or foreign_row.connected is False
    assert owner_row is not None and int(owner_row.login) == 10002
    store = svc._secret_store()
    assert store is not None
    public = await store.public_selection(user_id=owner)
    assert public is not None
    dumped = json.dumps(public)
    assert "desk-secret" not in dumped
    assert "ciphertext" not in dumped
    loaded = await store.load_password(user_id=owner)
    assert loaded is not None
    assert loaded[3] == "desk-secret"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_concurrent_connects_do_not_interleave() -> None:
    svc, _factory, gateway = _service()
    gateway._connected = False
    order: list[tuple[str, int]] = []
    original = svc._connect_holding_lock

    async def _tracked(**kwargs: Any) -> dict[str, Any]:
        order.append(("start", int(kwargs["login"])))
        await asyncio.sleep(0.02)
        result = await original(**kwargs)
        order.append(("end", int(kwargs["login"])))
        return result

    svc._connect_holding_lock = _tracked  # type: ignore[method-assign]
    await asyncio.gather(
        svc.connect(
            user_id=uuid4(),
            login=10001,
            password="one",
            server="Weltrade-Demo",
            account_type="demo",
        ),
        svc.connect(
            user_id=uuid4(),
            login=10002,
            password="two",
            server="Weltrade-Demo",
            account_type="demo",
        ),
    )
    starts = [item for item in order if item[0] == "start"]
    assert len(starts) == 2
    assert order[0][0] == "start"
    assert order[1][0] == "end"
    assert order[0][1] == order[1][1]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_demo_selection_rejects_a_verified_live_account() -> None:
    svc, _factory, gateway = _service()
    gateway._trade_mode = "real"
    gateway._connected = True
    gateway._login = 10001
    gateway._server = "Weltrade-Real"
    gateway._session_mode = "attached"
    with pytest.raises(RuntimeError, match="ACCOUNT_MODE_MISMATCH"):
        await svc.connect(
            user_id=uuid4(),
            login=10001,
            password="",
            server="Weltrade-Real",
            account_type="demo",
        )


@pytest.mark.unit
def test_switch_hold_blocks_new_entries_until_released() -> None:
    user = uuid4()
    begin_account_switch()
    blocked = submit_blocked_reason(user_id=user, login=10001)
    assert blocked == ACCOUNT_SWITCH_IN_PROGRESS
    reset_execution_binding_for_tests()
    assert submit_blocked_reason(user_id=user, login=10001) is None


@pytest.mark.unit
def test_risk_baseline_is_keyed_by_login() -> None:
    tracker = LiveAccountRiskTracker()
    tracker.observe_equity(login=10001, equity=__import__("decimal").Decimal("50"))
    tracker.observe_equity(login=10002, equity=__import__("decimal").Decimal("80"))
    assert tracker.peak_for(10001) == __import__("decimal").Decimal("50")
    assert tracker.peak_for(10002) == __import__("decimal").Decimal("80")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_secret_store_round_trip_hides_ciphertext() -> None:
    factory = MemoryBrokerUnitOfWorkFactory()
    store = BrokerSecretStore(factory, secret_key=_SECRET)
    user = uuid4()
    assert await store.save_selection(
        user_id=user,
        login=10001,
        server="Weltrade-Real",
        environment="live",
        currency="USD",
        account_mode="real",
        trade_allowed=True,
        password="desk-secret",
    )
    public = await store.public_selection(user_id=user)
    assert public is not None
    assert public["has_encrypted_password"] is True
    blob = json.dumps(public)
    assert "desk-secret" not in blob
    assert "ciphertext" not in blob
    loaded = await store.load_password(user_id=user)
    assert loaded == (10001, "Weltrade-Real", "live", "desk-secret")


@pytest.mark.unit
def test_ownership_errors_are_trader_safe() -> None:
    _cls, code, message = classify_broker_connect_error(
        RuntimeError("OPEN_EXPOSURE: login 10001")
    )
    assert code == "OPEN_EXPOSURE"
    assert "10001" not in message
    _cls, code, message = classify_broker_connect_error(
        RuntimeError("OWNERSHIP_CLAIM_FAILED:login_owned_by_other_user")
    )
    assert code == "OWNERSHIP_HELD"
    assert "10001" not in message


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unreadable_exposure_does_not_switch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    svc, _factory, gateway = _service()
    gateway._connected = True
    gateway._login = 10001
    gateway._server = "Weltrade-Real"
    gateway._session_mode = "attached"

    def _boom() -> list[SimpleNamespace]:
        raise RuntimeError("positions unavailable")

    monkeypatch.setattr(svc.adapter, "list_positions", _boom)
    with pytest.raises(RuntimeError, match="EXPOSURE_UNVERIFIED"):
        await svc.connect(
            user_id=uuid4(),
            login=10002,
            password="desk-secret",
            server="Weltrade-Real",
            account_type="live",
            confirm_leave_exposure=True,
        )
    assert gateway._login == 10001
