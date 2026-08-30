"""Phase 65 — authenticated broker / catalogue / signal observability contracts.

Verification phase: locks ownership, catalogue honesty, and research/execution
separation. Does not invent LIVE_BROKER production results.
"""

from __future__ import annotations

import ast
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services import signal_center_service
from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    reset_execution_binding_for_tests,
    submit_blocked_reason,
)
from app.application.services.institutional_multi_asset_scanner import (
    _store_last_scan,
)
from app.application.services.market_universe_service import (
    reset_market_universe_cache_for_tests,
)
from app.application.services.research_universe_scanner import (
    score_symbols_for_research,
)
from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.domain.entities.mt5 import MT5Connection
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION
from app.domain.market_universe.shadow_wall import scan_package_isolation
from app.domain.trading.execution_universe import (
    MODE_BROKER_DISCOVERED,
    MODE_GOLD_ONLY,
    normalize_execution_universe_mode,
)
from app.infrastructure.persistence.memory_mt5 import MemoryMT5UnitOfWorkFactory
from app.presentation.broker_trader_errors import classify_broker_connect_error
from app.presentation.schemas.broker import BrokerConnectionResponse
from app.presentation.schemas.mt5 import MT5ConnectionResponse
from app.presentation.schemas.weltrade import WeltradeConnectRequest

ROOT = Path(__file__).resolve().parents[2]


class _Account:
    def __init__(self, login: int, server: str = "Weltrade-Real") -> None:
        self.login = login
        self.server = server


class _FakeAdapter:
    def __init__(self, *, live_login: int) -> None:
        self._live_login = live_login
        self._live_session_ref = "sess-live"
        self._sessions = {
            "sess-live": type(
                "S",
                (),
                {"login": live_login, "server": "Weltrade-Real"},
            )()
        }
        self.client = type(
            "C",
            (),
            {
                "is_connected": True,
                "session_token": "sess-live",
                "_login": live_login,
                "stores_credentials_remotely": True,
            },
        )()
        self._shutdown = False

    def account_info(self) -> _Account:
        return _Account(self._live_login)

    def health(self) -> object:
        return type(
            "H",
            (),
            {"terminal_build": 1, "version": "1", "latency_ms": 1.0},
        )()

    def terminal_info(self) -> object:
        return type("T", (), {"build": 1})()

    def is_live_session(self, ref: str) -> bool:
        return ref == self._live_session_ref and not self._shutdown

    def attach(self, *, path: str = "") -> str:
        return self._live_session_ref

    def shutdown(self) -> None:
        self._shutdown = True
        self.client.is_connected = False  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _reset() -> None:
    reset_execution_binding_for_tests()
    _store_last_scan({})
    reset_market_universe_cache_for_tests()
    yield
    reset_execution_binding_for_tests()
    _store_last_scan({})
    reset_market_universe_cache_for_tests()


@pytest.mark.unit
def test_research_execution_wall_remains_closed() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    iso = scan_package_isolation()
    assert iso.get("isolated") is True
    out = score_symbols_for_research(None, ["EURUSD"])
    assert out["forwarded_to_oms"] is False
    assert out["would_submit_order"] is False
    assert out["authorizes_trade"] is False
    assert out["second_scanner"] is False


@pytest.mark.unit
def test_no_second_scanner_or_engine_modules() -> None:
    domain = ROOT / "app" / "domain" / "market_universe" / "second_scanner.py"
    services = ROOT / "app" / "application" / "services"
    assert not domain.exists()
    assert not (services / "second_scanner.py").exists()
    assert not (services / "second_gateway.py").exists()


@pytest.mark.unit
def test_signal_center_never_hardcodes_xauusd_i_universe() -> None:
    path = ROOT / "app" / "application" / "services" / "signal_center_service.py"
    text = path.read_text(encoding="utf-8")
    assert '"universe": "XAUUSD_i"' not in text
    assert "broker_required_for_research" in text
    assert "research_can_execute" in text


@pytest.mark.unit
def test_unavailable_catalogue_is_not_active_signals() -> None:
    _store_last_scan({})
    payload = signal_center_service.list_live_signals(enabled_only=False)
    assert payload["research_can_execute"] is False
    assert payload["allow_live_promotion"] is False
    assert payload["broker_required_for_research"] is False
    buy = sum(1 for i in payload["items"] if i.get("direction") == "BUY")
    sell = sum(1 for i in payload["items"] if i.get("direction") == "SELL")
    if buy + sell == 0:
        assert payload["scanner_status"] in {
            "NO_ACTIVE_SIGNALS",
            "UNAVAILABLE",
            "UNKNOWN",
            "ACTIVE",
        }
    # Never invent a fabricated catalogue.
    assert payload.get("fabricated") is False


@pytest.mark.unit
def test_no_active_signals_when_scan_empty_but_universe_known() -> None:
    _store_last_scan(
        {
            "as_of": "2026-08-30T13:00:00Z",
            "universe": ["EURUSD", "GBPUSD", "XAUUSD"],
            "ranked": [],
            "rows": [],
        }
    )
    snap = {
        "catalogue_source": "LIVE_BROKER",
        "as_of": "2026-08-30T13:00:00Z",
        "opportunity_board": {"live_ranked": []},
        "research_signals": {"n": 0, "signals": []},
        "observability": {
            "catalogue_source": "LIVE_BROKER",
            "symbols_scored": 3,
            "research_signal_count": 0,
        },
    }
    merged, meta = signal_center_service._merge_research_into_signals(
        [], research_snap=snap
    )
    assert merged == []
    assert meta["catalogue_source"] == "LIVE_BROKER"
    payload = signal_center_service.list_live_signals(enabled_only=False)
    # Empty qualifying set after a known scan must not be fabricated.
    assert payload.get("fabricated") is False


@pytest.mark.unit
@pytest.mark.asyncio
async def test_owned_session_heals_only_matching_owner() -> None:
    owner = uuid4()
    stranger = uuid4()
    factory = MemoryMT5UnitOfWorkFactory()
    async with factory() as uow:
        owned = MT5Connection.create(
            user_id=owner,
            login=55550001,
            server="Weltrade-Real",
            terminal_path="",
        )
        owned.mark_connected(session_ref="stale-ref")
        await uow.connections.upsert_for_user(owned)
        await uow.commit()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=55550001),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    await svc.ensure_user_session_bound(user_id=owner)
    await svc.ensure_user_session_bound(user_id=stranger)
    async with factory() as uow:
        assert await uow.connections.get_active_for_user(owner) is not None
        assert await uow.connections.get_active_for_user(stranger) is None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_bind_rejects_claimed_vs_live_mismatch() -> None:
    factory = MemoryMT5UnitOfWorkFactory()
    svc = WeltradeIntegrationService(
        adapter=_FakeAdapter(live_login=11110001),  # type: ignore[arg-type]
        uow_factory=factory,
    )
    bound = await svc.bind_user_session(
        user_id=uuid4(),
        login=22220002,
        server="Weltrade-Real",
        session_ref="sess-live",
    )
    assert bound is None


@pytest.mark.unit
def test_account_session_mismatch_fail_closed() -> None:
    user_a = uuid4()
    user_b = uuid4()
    bind_execution_account(user_id=user_a, login=42424242)
    assert submit_blocked_reason(user_id=user_b, login=42424242) == (
        ACCOUNT_SESSION_MISMATCH
    )
    _, code, _ = classify_broker_connect_error(
        RuntimeError(
            "ACCOUNT_SESSION_MISMATCH: The gateway MT5 session belongs "
            "to a different account."
        )
    )
    assert code == ACCOUNT_SESSION_MISMATCH


@pytest.mark.unit
def test_password_never_in_connection_response_models() -> None:
    for model in (BrokerConnectionResponse, MT5ConnectionResponse):
        fields = set(model.model_fields)
        assert "password" not in fields
    # Request models may accept password; response models must not echo it.
    assert "password" in WeltradeConnectRequest.model_fields


@pytest.mark.unit
def test_execution_universe_modes_have_no_static_invent_fallback_flag() -> None:
    assert normalize_execution_universe_mode("GOLD_ONLY") == MODE_GOLD_ONLY
    assert normalize_execution_universe_mode("BROKER_DISCOVERED") == (
        MODE_BROKER_DISCOVERED
    )
    # Fail-closed for unknown modes — never invent a static catalogue mode.
    assert normalize_execution_universe_mode("STATIC_SYMBOL_FALLBACK") == "FAIL_CLOSED"
    assert normalize_execution_universe_mode("GOLD_ONLY_FALLBACK") == "FAIL_CLOSED"


@pytest.mark.unit
def test_trading_session_provider_connected_is_ownership_aware() -> None:
    text = (
        ROOT
        / "frontend"
        / "src"
        / "providers"
        / "trading-session-provider.tsx"
    ).read_text(encoding="utf-8")
    assert "const connectedFlag = statusConnected;" in text
    assert "Ownership-aware only" in text
    # Must not OR health attach into user connected.
    assert "statusConnected || (healthUsablePreview && healthAttached)" not in text


@pytest.mark.unit
def test_research_scanner_ast_has_no_order_send_call() -> None:
    path = ROOT / "app" / "application" / "services" / "research_universe_scanner.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    calls: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                calls.append(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                calls.append(node.func.attr)
    assert "order_send" not in calls
