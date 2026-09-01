"""Regression: serialize MetaTrader5 IPC under parallel scan load.

Proves Terminal: Call failed is avoided by process-wide MT5 ops locking +
symbol_select session cache. Never fabricates market data.
"""

from __future__ import annotations

import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any

import pytest

from app.domain.institutional_trading.ai_scalping.asset_class import (
    broker_symbol_candidates,
)
from services.mt5_gateway.runtime import (
    MT5GatewayRuntime,
    _is_terminal_call_failed,
    call_mt5_bounded,
)
from tests.unit.test_mt5_gateway import _FakeBridge


class _ContendedBridge(_FakeBridge):
    """Fails symbol_select when concurrent MT5 ops overlap (no ops lock)."""

    def __init__(self) -> None:
        super().__init__(prelogged=True)
        self._inflight = 0
        self._guard = threading.Lock()
        self.select_calls = 0
        self.copy_calls = 0
        self.overlap_failures = 0
        self._fail_once: dict[str, int] = {}

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        _ = enable
        with self._guard:
            self.select_calls += 1
            self._inflight += 1
            overlapping = self._inflight > 1
        time.sleep(0.02)
        with self._guard:
            self._inflight -= 1
            if overlapping:
                self.overlap_failures += 1
                self._last_err = (-1, "Terminal: Call failed")
                return False
            remaining = self._fail_once.get(symbol.upper(), 0)
            if remaining > 0:
                self._fail_once[symbol.upper()] = remaining - 1
                self._last_err = (-1, "Terminal: Call failed")
                return False
            self.selected.append(symbol)
            self._last_err = (1, "ok")
            return True

    def last_error(self) -> Any:
        return getattr(self, "_last_err", (1, "fake"))

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        with self._guard:
            self.copy_calls += 1
            self._inflight += 1
            overlapping = self._inflight > 1
        time.sleep(0.01)
        with self._guard:
            self._inflight -= 1
            if overlapping:
                self.overlap_failures += 1
                self._last_err = (-1, "Terminal: Call failed")
                return None
        return super().copy_rates_from_pos(symbol, timeframe, start_pos, count)


@pytest.mark.unit
def test_xauusd_broker_candidates_include_weltrade_i() -> None:
    cands = broker_symbol_candidates("XAUUSD")
    assert cands[0] == "XAUUSD"
    assert "XAUUSD_I" in cands
    assert "GOLD" in cands


@pytest.mark.unit
def test_terminal_call_failed_detector() -> None:
    assert _is_terminal_call_failed((-1, "Terminal: Call failed")) is True
    assert _is_terminal_call_failed((1, "Success")) is False


@pytest.mark.unit
def test_symbol_select_cache_avoids_repeat_calls() -> None:
    bridge = _ContendedBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True
    rt.diagnostics.session_mode = "attached"

    first = rt.candles("XAUUSD_I", timeframe="H4", count=5)
    second = rt.candles("XAUUSD_I", timeframe="H1", count=5)
    assert first["symbol"] == "XAUUSD_I"
    assert second["timeframe"] == "H1"
    assert bridge.select_calls == 1
    assert "XAUUSD_I" in rt._selected_symbols


@pytest.mark.unit
def test_symbol_select_soft_retries_terminal_call_failed() -> None:
    bridge = _ContendedBridge()
    bridge._fail_once["XAUUSD"] = 1
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True

    out = rt.quote("XAUUSD")
    assert out["symbol"] == "XAUUSD"
    assert bridge.select_calls == 2
    assert float(out["bid"]) > 0


@pytest.mark.unit
def test_concurrent_candles_serialized_no_overlap_failures() -> None:
    bridge = _ContendedBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True

    symbols = ["XAUUSD_I", "EURUSD_I", "LTCUSD", "BTCUSD"]

    def _one(sym: str) -> dict[str, Any]:
        return rt.candles(sym, timeframe="H4", count=3)

    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = [pool.submit(_one, s) for s in symbols]
        results = [f.result(timeout=5) for f in as_completed(futs)]

    assert len(results) == 4
    assert all(r.get("items") for r in results)
    assert bridge.overlap_failures == 0
    assert bridge.copy_calls == 4


@pytest.mark.unit
def test_one_symbol_failure_does_not_corrupt_other() -> None:
    bridge = _ContendedBridge()

    def _select(symbol: str, enable: bool = True) -> bool:
        _ = enable
        bridge.select_calls += 1
        if symbol.upper() == "BADSYM":
            bridge._last_err = (10004, "No such symbol")
            return False
        bridge.selected.append(symbol)
        bridge._last_err = (1, "ok")
        return True

    bridge.symbol_select = _select  # type: ignore[method-assign]
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True

    with pytest.raises(RuntimeError, match="symbol_select failed for BADSYM"):
        rt.candles("BADSYM", timeframe="H4", count=2)
    ok = rt.candles("XAUUSD_I", timeframe="H4", count=2)
    assert ok["symbol"] == "XAUUSD_I"
    assert len(ok["items"]) >= 1


@pytest.mark.unit
def test_genuine_failure_stays_safe_no_trade_shape() -> None:
    bridge = _ContendedBridge()

    def _always_fail(symbol: str, enable: bool = True) -> bool:
        _ = enable, symbol
        bridge.select_calls += 1
        bridge._last_err = (-1, "Terminal: Call failed")
        return False

    bridge.symbol_select = _always_fail  # type: ignore[method-assign]
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True
    with pytest.raises(RuntimeError, match="symbol_select failed"):
        rt.candles("XAUUSD", timeframe="H4", count=2)
    # Never invents candles
    assert bridge.copy_calls == 0


@pytest.mark.unit
def test_call_mt5_bounded_holds_ops_lock_in_worker() -> None:
    lock = threading.RLock()
    held = {"inside": False}

    def _fn() -> str:
        held["inside"] = lock._is_owned()  # type: ignore[attr-defined]
        return "ok"

    out = call_mt5_bounded(
        _fn, timeout_seconds=2.0, label="test", ops_lock=lock
    )
    assert out == "ok"
    assert held["inside"] is True


@pytest.mark.unit
def test_disconnect_clears_symbol_select_cache() -> None:
    bridge = _ContendedBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True
    rt.candles("XAUUSD_I", timeframe="M15", count=2)
    assert "XAUUSD_I" in rt._selected_symbols
    rt.disconnect()
    assert rt._selected_symbols == set()
    assert rt._symbol_name_by_upper == {}


class _CaseSensitiveWeltradeBridge(_FakeBridge):
    """Weltrade-style catalogue: institutional suffix is lowercase ``_i``."""

    def __init__(self) -> None:
        super().__init__(prelogged=True)
        self.select_calls = 0
        self.selected_exact: list[str] = []
        self._last_err: Any = (1, "ok")

    def symbols_get(self) -> Any:
        from types import SimpleNamespace

        return [
            SimpleNamespace(name="XAUUSD_i", description="Gold", digits=3),
            SimpleNamespace(name="EURUSD_i", description="Euro", digits=5),
            SimpleNamespace(name="LTCUSD", description="Litecoin", digits=2),
        ]

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        _ = enable
        self.select_calls += 1
        # Only the exact catalogue spelling succeeds.
        if symbol in {"XAUUSD_i", "EURUSD_i", "LTCUSD"}:
            self.selected_exact.append(symbol)
            self.selected.append(symbol)
            self._last_err = (1, "ok")
            return True
        self._last_err = (-1, "Terminal: Call failed")
        return False

    def last_error(self) -> Any:
        return self._last_err

    def symbol_info_tick(self, symbol: str) -> Any:
        from types import SimpleNamespace

        if symbol not in {"XAUUSD_i", "EURUSD_i", "LTCUSD"}:
            return None
        return SimpleNamespace(bid=4300.1, ask=4300.2, time=1_700_000_000)

    def symbol_info(self, symbol: str) -> Any:
        from types import SimpleNamespace

        if symbol not in {"XAUUSD_i", "EURUSD_i", "LTCUSD"}:
            return None
        return SimpleNamespace(
            name=symbol,
            description="Gold",
            digits=3,
            point=0.001,
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            volume_limit=0.0,
            trade_stops_level=0,
            trade_freeze_level=0,
            filling_mode=2,
            trade_mode=4,
            trade_exemode=2,
            trade_calc_mode=0,
            order_mode=127,
            visible=True,
            select=True,
            currency_base="XAU",
            currency_profit="USD",
            currency_margin="USD",
            swap_mode=0,
            session_deals=0,
            session_buy_orders=0,
            session_sell_orders=0,
            time=1_700_000_000,
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        if symbol not in {"XAUUSD_i", "EURUSD_i", "LTCUSD"}:
            self._last_err = (-1, "Terminal: Call failed")
            return None
        return super().copy_rates_from_pos(symbol, timeframe, start_pos, count)


class _BareGoldCatalogueBridge(_FakeBridge):
    """Live Weltrade-style book: gold is unsuffixed ``XAUUSD``, not ``XAUUSD_I``."""

    def __init__(self) -> None:
        super().__init__(prelogged=True)
        self.select_calls = 0
        self.selected_exact: list[str] = []
        self._last_err: Any = (1, "ok")

    def symbols_get(self) -> Any:
        from types import SimpleNamespace

        return [SimpleNamespace(name="XAUUSD", description="Gold", digits=3)]

    def symbol_select(self, symbol: str, enable: bool = True) -> bool:
        _ = enable
        self.select_calls += 1
        if symbol == "XAUUSD":
            self.selected_exact.append(symbol)
            self.selected.append(symbol)
            self._last_err = (1, "ok")
            return True
        self._last_err = (-1, "Terminal: Call failed")
        return False

    def last_error(self) -> Any:
        return self._last_err

    def symbol_info_tick(self, symbol: str) -> Any:
        from types import SimpleNamespace

        if symbol != "XAUUSD":
            return None
        return SimpleNamespace(bid=4374.193, ask=4374.607, time=1_700_000_000)

    def symbol_info(self, symbol: str) -> Any:
        from types import SimpleNamespace

        if symbol != "XAUUSD":
            return None
        return SimpleNamespace(
            name="XAUUSD",
            description="Gold",
            digits=3,
            point=0.001,
            trade_contract_size=100.0,
            volume_min=0.01,
            volume_max=100.0,
            volume_step=0.01,
            volume_limit=0.0,
            trade_stops_level=0,
            trade_freeze_level=0,
            filling_mode=2,
            trade_mode=4,
            trade_exemode=2,
            trade_calc_mode=0,
            order_mode=127,
            visible=True,
            select=True,
            currency_base="XAU",
            currency_profit="USD",
            currency_margin="USD",
            swap_mode=0,
            session_deals=0,
            session_buy_orders=0,
            session_sell_orders=0,
            time=1_700_000_000,
        )

    def copy_rates_from_pos(
        self, symbol: str, timeframe: int, start_pos: int, count: int
    ) -> Any:
        if symbol != "XAUUSD":
            self._last_err = (-1, "Terminal: Call failed")
            return None
        return super().copy_rates_from_pos(symbol, timeframe, start_pos, count)


@pytest.mark.unit
def test_xauusd_uppercase_resolves_to_catalogue_exact_case() -> None:
    bridge = _CaseSensitiveWeltradeBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True

    quote = rt.quote("XAUUSD_I")
    candles = rt.candles("XAUUSD_I", timeframe="H4", count=3)

    assert quote["symbol"] == "XAUUSD_I"
    assert float(quote["bid"]) > 0
    assert candles["items"]
    assert bridge.selected_exact == ["XAUUSD_i"]
    assert "XAUUSD_i" in rt._selected_symbols
    # Cache: second request must not re-select.
    rt.quote("xauusd_i")
    assert bridge.select_calls == 1


@pytest.mark.unit
def test_wrong_case_does_not_fabricate_when_absent_from_catalogue() -> None:
    bridge = _CaseSensitiveWeltradeBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True
    with pytest.raises(RuntimeError, match="symbol_select failed"):
        rt.quote("NOTAREALSYM")


@pytest.mark.unit
def test_xauusd_i_resolves_to_unsuffixed_catalogue_gold() -> None:
    """OMS uppercases XAUUSD_i → XAUUSD_I; live book may only expose XAUUSD."""
    bridge = _BareGoldCatalogueBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True

    quote = rt.quote("XAUUSD_I")
    specs = rt.symbol_specs("XAUUSD_i")

    assert float(quote["bid"]) > 0
    assert quote["symbol"] == "XAUUSD"
    assert specs["code"] in {"XAUUSD", "XAUUSD_I"}
    assert bridge.selected_exact == ["XAUUSD"]
    assert "XAUUSD" in rt._selected_symbols
    with pytest.raises(RuntimeError, match="symbol_select failed"):
        rt.quote("NOTAREALSYM")


@pytest.mark.unit
def test_run_mt5_op_times_out_instead_of_holding_forever() -> None:
    from services.mt5_gateway.runtime import MT5CallTimeout

    bridge = _ContendedBridge()
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.settings.mt5_market_data_timeout_seconds = 0.1

    def _hang() -> str:
        time.sleep(2.0)
        return "never"

    with pytest.raises(MT5CallTimeout):
        rt._run_mt5_op(_hang, label="hung_op")


@pytest.mark.unit
def test_gateway_recovery_after_temporary_select_failure() -> None:
    bridge = _ContendedBridge()
    bridge._fail_once["XAUUSD_I"] = 1
    rt = MT5GatewayRuntime(bridge=bridge)
    rt.diagnostics.connected = True
    # Soft retry inside _ensure_symbol clears one transient Terminal: Call failed.
    out = rt.quote("XAUUSD_I")
    assert float(out["bid"]) > 0
    assert bridge.select_calls >= 2
