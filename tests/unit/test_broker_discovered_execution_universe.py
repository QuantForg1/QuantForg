"""BROKER_DISCOVERED live execution universe — fail closed, no gold clamp.

Does not send orders. Does not arm FORCE_FIRST_TRADE. Does not weaken
Opportunity 70 / Edge 5 / research shadow isolation.
"""

from __future__ import annotations

import ast
import inspect
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.application.services.institutional_multi_asset_scanner import (
    resolve_scan_universe,
)
from app.domain.institutional_trading.operations.gold_execution_contract import (
    GoldExecutionFacts,
    evaluate_gold_execution_contract,
)
from app.domain.institutional_trading.operations.probability_selector import (
    OPPORTUNITY_SCORE_THRESHOLD,
)
from app.domain.market_universe.constants import (
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_OPPORTUNITY_THRESHOLD,
)
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    submit_order,
)
from app.domain.trading.execution_universe import (
    CATALOGUE_FIXTURE,
    CATALOGUE_INJECTED,
    CATALOGUE_LIVE_BROKER,
    CATALOGUE_MOCK,
    CATALOGUE_UNAVAILABLE,
    MODE_BROKER_DISCOVERED,
    MODE_FAIL_CLOSED,
    MODE_GOLD_ONLY,
    execution_symbol_allowed,
    execution_universe_diagnostics,
    live_execution_snapshot,
    live_execution_symbols,
    reset_broker_execution_universe_for_tests,
)
from app.domain.trading.gold_only import (
    autonomous_execution_symbols,
    gold_only_enabled,
    is_autonomous_execution_symbol,
)
from app.infrastructure.brokers.mt5 import MockMT5Client
from core.config.environments import production_settings, testing_settings

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

ROOT = Path(__file__).resolve().parents[2]

_LIVE_ROWS = (
    {
        "code": "EURUSD_i",
        "path": "Forex\\Majors",
        "trade_mode": 4,
        "digits": 5,
        "bid": 1.08,
        "ask": 1.0801,
    },
    {
        "code": "GBPUSD_i",
        "path": "Forex\\Majors",
        "trade_mode": 4,
        "digits": 5,
    },
    {
        "code": "BTCUSD",
        "path": "Crypto\\BTC",
        "trade_mode": 4,
        "digits": 2,
    },
    {
        "code": "XAUUSD_i",
        "path": "Metals\\XAUUSD",
        "trade_mode": 4,
        "digits": 3,
    },
    {
        "code": "DISABLEDX",
        "path": "Forex\\Majors",
        "trade_mode": 0,
        "digits": 5,
    },
    {
        "code": "ZZZUNK",
        "trade_mode": 4,
        "data_state": "UNSUPPORTED",
    },
)


class GatewayMT5Client:
    def __init__(
        self,
        rows: tuple[dict[str, object], ...] | list[dict[str, object]] = _LIVE_ROWS,
    ) -> None:
        self._rows = list(rows)

    def symbols(self) -> list[dict[str, object]]:
        return list(self._rows)


class _LiveAdapter:
    execution_enabled = False

    def __init__(
        self,
        rows: tuple[dict[str, object], ...] | list[dict[str, object]] = _LIVE_ROWS,
    ) -> None:
        self.client = GatewayMT5Client(rows)

    def symbols(self) -> list[dict[str, object]]:
        return self.client.symbols()


class _InjectedAdapter:
    execution_enabled = False

    def symbols(self) -> list[dict[str, object]]:
        return [{"code": "EURUSD_i", "trade_mode": 4, "path": "Forex\\Majors"}]


class FixtureMT5Adapter:
    execution_enabled = False
    client = SimpleNamespace()

    def symbols(self) -> list[dict[str, object]]:
        return [{"code": "EURUSD_i", "trade_mode": 4, "path": "Forex\\Majors"}]


class _DownAdapter:
    execution_enabled = False

    def __init__(self) -> None:
        self.client = type("GatewayMT5Client", (), {})()

    def symbols(self) -> list[dict[str, object]]:
        raise RuntimeError("gateway unreachable")


def _broker_settings(**overrides: object) -> object:
    return testing_settings(
        execution_universe_mode="BROKER_DISCOVERED",
        gold_only_mode=False,
        multi_symbol_enabled=True,
        **overrides,
    )


@pytest.fixture
def broker_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _LiveAdapter()
    monkeypatch.setattr(
        "core.config.settings.get_settings",
        lambda: _broker_settings(),
    )
    monkeypatch.setattr(
        "core.di.container.get_container",
        lambda: SimpleNamespace(mt5_adapter=adapter),
    )
    reset_broker_execution_universe_for_tests()
    yield
    reset_broker_execution_universe_for_tests()


def _ready_fx(**overrides: object) -> GoldExecutionFacts:
    base: dict[str, object] = {
        "symbol": "EURUSD_i",
        "direction": "BUY",
        "action": "BUY",
        "market_open": True,
        "tradable": True,
        "candles_ok": True,
        "bid": Decimal("1.08000"),
        "ask": Decimal("1.08012"),
        "quote_age_seconds": 1.0,
        "spread": Decimal("0.00012"),
        "structure_score": 70,
        "momentum_score": 65,
        "quality": 80,
        "confidence": 75,
        "pa_confluence": 55,
        "risk_reward": Decimal("1.20"),
        "market_regime": "TREND",
        "volatility_ok": True,
        "session_quality_ok": True,
        "safety_allowed": True,
        "kill_switch": False,
        "execution_enabled": True,
        "auto_running": True,
        "account_leverage": Decimal("2000"),
        "risk_eligible": True,
        "approved_lots": Decimal("0.01"),
        "min_lot_infeasible": False,
        "portfolio_allow": True,
        "optimizer_state": "EXECUTE_NOW",
        "oms_orders_allowed": True,
        "gateway_connected": True,
        "broker_connected": True,
        "force_shadow": False,
        "gold_only": False,
        "opportunity_score": 80,
        "opportunity_threshold": 70,
    }
    base.update(overrides)
    return GoldExecutionFacts(**base)  # type: ignore[arg-type]


def test_gold_only_mode_preserves_xauusd_i_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.trading.gold_only.gold_only_enabled",
        lambda: True,
    )
    monkeypatch.setattr(
        "core.config.settings.get_settings",
        lambda: testing_settings(
            execution_universe_mode="GOLD_ONLY",
            gold_only_mode=True,
        ),
    )
    uni = autonomous_execution_symbols(
        broker_symbol_rows=tuple(_LIVE_ROWS),
        mt5_adapter=_LiveAdapter(),
    )
    assert len(uni) == 1
    assert "XAUUSD" in uni[0].upper()
    assert "EURUSD" not in {s.upper() for s in uni}
    scan = resolve_scan_universe(
        broker_symbol_rows=tuple(_LIVE_ROWS),
        mt5_adapter=_LiveAdapter(),
    )
    assert all("XAUUSD" in s.upper() for s in scan)


def test_broker_discovered_accepts_live_broker(broker_mode: None) -> None:
    adapter = _LiveAdapter()
    snap = live_execution_snapshot(mt5_adapter=adapter)
    assert snap["catalogue_source"] == CATALOGUE_LIVE_BROKER
    symbols = {s.upper() for s in live_execution_symbols(mt5_adapter=adapter)}
    assert "EURUSD_I" in symbols
    assert "GBPUSD_I" in symbols
    assert "BTCUSD" in symbols
    assert "XAUUSD_I" in symbols
    assert gold_only_enabled() is False
    assert is_autonomous_execution_symbol("EURUSD_i")
    assert execution_symbol_allowed("EURUSD_i")


def test_broker_discovered_rejects_mock(broker_mode: None) -> None:
    class _MockAdapter:
        client = MockMT5Client()
        execution_enabled = False

        def symbols(self) -> list[dict[str, object]]:
            return [{"code": "EURUSD_i", "trade_mode": 4, "path": "Forex\\Majors"}]

    snap = live_execution_snapshot(mt5_adapter=_MockAdapter())
    assert snap["catalogue_source"] == CATALOGUE_MOCK
    assert live_execution_symbols(mt5_adapter=_MockAdapter()) == ()
    assert snap["execution_unavailable_reason"] == "mock_mt5_client_not_live_broker"


def test_broker_discovered_rejects_fixture(broker_mode: None) -> None:
    snap = live_execution_snapshot(mt5_adapter=FixtureMT5Adapter())
    assert snap["catalogue_source"] == CATALOGUE_FIXTURE
    assert live_execution_symbols(mt5_adapter=FixtureMT5Adapter()) == ()


def test_broker_discovered_rejects_injected(broker_mode: None) -> None:
    snap = live_execution_snapshot(mt5_adapter=_InjectedAdapter())
    assert snap["catalogue_source"] == CATALOGUE_INJECTED
    assert live_execution_symbols(mt5_adapter=_InjectedAdapter()) == ()
    scan = resolve_scan_universe(
        broker_symbol_rows=tuple(_LIVE_ROWS),
        mt5_adapter=_InjectedAdapter(),
    )
    assert scan == ()


def test_missing_gateway_credentials_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "core.config.settings.get_settings",
        lambda: testing_settings(
            execution_universe_mode="BROKER_DISCOVERED",
            gold_only_mode=False,
            mt5_gateway_base_url="",
            mt5_gateway_caller_token="",
        ),
    )
    monkeypatch.setattr(
        "core.di.container.get_container",
        lambda: (_ for _ in ()).throw(RuntimeError("no di")),
    )
    reset_broker_execution_universe_for_tests()
    snap = live_execution_snapshot(mt5_adapter=None)
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["execution_unavailable_reason"] == "gateway_credentials_unavailable"
    assert snap["catalogue_symbol_count"] == 0
    assert live_execution_symbols(mt5_adapter=None) == ()


def test_gateway_unavailable_fail_closed(broker_mode: None) -> None:
    snap = live_execution_snapshot(mt5_adapter=_DownAdapter())
    assert snap["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert snap["execution_unavailable_reason"] == "gateway_unavailable"
    assert live_execution_symbols(mt5_adapter=_DownAdapter()) == ()


def test_empty_broker_catalogue_is_live_not_unavailable(broker_mode: None) -> None:
    adapter = _LiveAdapter(rows=())
    snap = live_execution_snapshot(mt5_adapter=adapter)
    assert snap["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert snap["catalogue_source"] != CATALOGUE_UNAVAILABLE
    assert snap["execution_unavailable_reason"] == "empty_catalogue"
    assert snap["catalogue_symbol_count"] == 0
    assert live_execution_symbols(mt5_adapter=adapter) == ()


@pytest.mark.parametrize("symbol", ("EURUSD_i", "GBPUSD_i", "BTCUSD"))
def test_broker_discovered_symbol_reaches_eligibility(
    broker_mode: None, symbol: str
) -> None:
    adapter = _LiveAdapter()
    live = {s.upper() for s in live_execution_symbols(mt5_adapter=adapter)}
    assert symbol.upper() in live
    scan = resolve_scan_universe(mt5_adapter=adapter)
    assert any(s.upper() == symbol.upper() for s in scan)
    out = evaluate_gold_execution_contract(_ready_fx(symbol=symbol))
    assert out.fault_code != "DISABLED_AUTONOMOUS_SYMBOL"
    assert "XAUUSD" not in (out.fault_reason or "")


def test_unsupported_and_disabled_symbols_rejected(broker_mode: None) -> None:
    adapter = _LiveAdapter()
    symbols = {s.upper() for s in live_execution_symbols(mt5_adapter=adapter)}
    assert "DISABLEDX" not in symbols
    assert "ZZZUNK" not in symbols
    diag = execution_universe_diagnostics(mt5_adapter=adapter)
    assert int(diag["execution_rejected_count"] or 0) >= 2


def test_unknown_symbols_are_not_automatically_executable(broker_mode: None) -> None:
    assert is_autonomous_execution_symbol("NOTAREALPAIR") is False
    assert execution_symbol_allowed("NOTAREALPAIR") is False


def test_xauusd_i_remains_executable_when_broker_exposes_it(broker_mode: None) -> None:
    adapter = _LiveAdapter()
    live = live_execution_symbols(mt5_adapter=adapter)
    assert any(s.upper() == "XAUUSD_I" for s in live)
    gold = evaluate_gold_execution_contract(
        _ready_fx(
            symbol="XAUUSD_i",
            bid=Decimal("2400.10"),
            ask=Decimal("2400.30"),
            spread=Decimal("0.20"),
        )
    )
    assert gold.fault_code != "DISABLED_AUTONOMOUS_SYMBOL"


def test_no_gold_only_clamp_in_broker_discovered(broker_mode: None) -> None:
    adapter = _LiveAdapter()
    uni = resolve_scan_universe(mt5_adapter=adapter)
    assert any("EURUSD" in s.upper() for s in uni)
    src = inspect.getsource(resolve_scan_universe)
    assert "live_execution_symbols" in src


def test_gold_specs_not_applied_to_non_gold(broker_mode: None) -> None:
    wide = evaluate_gold_execution_contract(
        _ready_fx(spread=Decimal("3.00"), account_leverage=Decimal("2001"))
    )
    assert wide.fault_code != "SPREAD_UNACCEPTABLE"
    assert wide.fault_code != "LEVERAGE_POLICY_EXCEEDED"
    missing = evaluate_gold_execution_contract(
        _ready_fx(spread=None, bid=Decimal("1.08"), ask=Decimal("1.0801"))
    )
    assert missing.may_submit_oms is False
    assert missing.fault_code == "NOT_EXECUTABLE"


def test_risk_rejection_still_blocks(broker_mode: None) -> None:
    out = evaluate_gold_execution_contract(
        _ready_fx(risk_eligible=False, risk_reasons=("RISK_REJECTED",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code not in {"NONE", "DISABLED_AUTONOMOUS_SYMBOL"}


def test_safety_rejection_still_blocks(broker_mode: None) -> None:
    out = evaluate_gold_execution_contract(
        _ready_fx(safety_allowed=False, safety_reasons=("SAFETY_BLOCKED",))
    )
    assert out.may_submit_oms is False
    assert out.fault_code == "SAFETY_BLOCKED"


def test_oms_rejection_still_blocks(broker_mode: None) -> None:
    out = evaluate_gold_execution_contract(_ready_fx(oms_orders_allowed=False))
    assert out.may_submit_oms is False
    assert out.fault_code == "OMS_NOT_READY"


def test_research_shadow_cannot_submit(broker_mode: None) -> None:
    with pytest.raises(ResearchExecutionBlocked):
        submit_order(symbol="EURUSD_i", side="BUY", volume="0.01")


def test_no_second_gateway_scanner_or_engine() -> None:
    ite = (
        ROOT / "app/application/services/institutional_ite_runtime.py"
    ).read_text(encoding="utf-8")
    scanner = (
        ROOT / "app/application/services/institutional_multi_asset_scanner.py"
    ).read_text(encoding="utf-8")
    universe = (ROOT / "app/domain/trading/execution_universe.py").read_text(
        encoding="utf-8"
    )
    assert ite.count("run_institutional_multi_asset_scan(") == 1
    assert scanner.count("async def run_institutional_multi_asset_scan") == 1
    assert "GatewayMT5Client(" not in universe
    tree = ast.parse(universe)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            assert node.func.id != "GatewayMT5Client"


def test_no_hardcoded_execution_allowlist_in_broker_mode(broker_mode: None) -> None:
    src = (
        ROOT / "app/domain/trading/execution_universe.py"
    ).read_text(encoding="utf-8")
    live_fn = inspect.getsource(live_execution_symbols)
    assert "DEFAULT_SCALPING_UNIVERSE" not in live_fn
    assert "EURUSD" not in live_fn
    snap = live_execution_snapshot(mt5_adapter=_LiveAdapter())
    assert snap["catalogue_source"] == CATALOGUE_LIVE_BROKER
    live_src = src.split("def live_execution_symbols")[1].split("def ")[0]
    assert "EURUSD" not in live_src


def test_opportunity_edge_and_force_first_trade_frozen() -> None:
    assert OPPORTUNITY_SCORE_THRESHOLD == 70
    assert FROZEN_OPPORTUNITY_THRESHOLD == 70
    assert FROZEN_DIRECTIONAL_EDGE == 5
    from app.domain.institutional_trading.ai_scalping.config import (
        DEFAULT_AI_SCALPING_CONFIG,
    )
    from app.domain.institutional_trading.force_first_trade import (
        is_force_first_trade_armed,
    )

    assert int(DEFAULT_AI_SCALPING_CONFIG.direction_edge_margin) == 5
    settings = testing_settings()
    assert bool(getattr(settings, "force_first_trade", False)) is False
    assert is_force_first_trade_armed(settings) is False


def test_research_authorizes_trade_false() -> None:
    from app.application.services.market_universe_service import build_snapshot

    snap = build_snapshot(broker_rows=list(_LIVE_ROWS))
    assert snap["authorizes_trade"] is False
    assert snap["catalogue_source"] != CATALOGUE_LIVE_BROKER or snap.get(
        "authorizes_trade"
    ) is False


def test_catalogue_source_must_be_live_broker_for_execution(broker_mode: None) -> None:
    live = live_execution_snapshot(mt5_adapter=_LiveAdapter())
    assert live["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert live_execution_symbols(mt5_adapter=_LiveAdapter())
    dead = live_execution_snapshot(mt5_adapter=_InjectedAdapter())
    assert dead["catalogue_source"] != CATALOGUE_LIVE_BROKER
    assert live_execution_symbols(mt5_adapter=_InjectedAdapter()) == ()


def test_invalid_production_mode_fail_closed() -> None:
    settings = production_settings(
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        execution_universe_mode="NOT_A_MODE",
    )
    assert str(settings.execution_universe_mode).upper() == MODE_FAIL_CLOSED
    assert settings.gold_only_mode is False


def test_production_broker_discovered_lifts_gold_lock() -> None:
    settings = production_settings(
        secret_key="a-real-production-secret-key-with-enough-entropy-here",
        postgres_password="a-real-production-password-here",
        execution_universe_mode="BROKER_DISCOVERED",
        gold_only_mode=True,
        multi_symbol_enabled=False,
    )
    assert str(settings.execution_universe_mode).upper() == MODE_BROKER_DISCOVERED
    assert settings.gold_only_mode is False
    assert settings.multi_symbol_enabled is True
    assert bool(getattr(settings, "force_first_trade", False)) is False


def test_observability_distinguishes_unavailable_from_empty_live(
    monkeypatch: pytest.MonkeyPatch,
    broker_mode: None,
) -> None:
    monkeypatch.setattr(
        "core.di.container.get_container",
        lambda: (_ for _ in ()).throw(RuntimeError("no di")),
    )
    reset_broker_execution_universe_for_tests()
    diag = execution_universe_diagnostics(mt5_adapter=None)
    assert diag["execution_universe_mode"] == MODE_BROKER_DISCOVERED
    assert diag["catalogue_source"] == CATALOGUE_UNAVAILABLE
    assert diag["catalogue_symbol_count"] == 0
    assert diag["execution_unavailable_reason"]
    live = execution_universe_diagnostics(mt5_adapter=_LiveAdapter())
    assert live["catalogue_source"] == CATALOGUE_LIVE_BROKER
    assert int(live["catalogue_symbol_count"] or 0) >= 4
    assert live["execution_unavailable_reason"] is None


def test_gold_only_mode_constant_unchanged() -> None:
    assert MODE_GOLD_ONLY == "GOLD_ONLY"
    assert MODE_BROKER_DISCOVERED == "BROKER_DISCOVERED"
