"""Read-only gateway bars must keep a recorded spread and must not invent one."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from services.mt5_gateway.runtime import MT5GatewayRuntime, serialize_rate_bars
from services.mt5_gateway.symbol_specs import serialize_symbol_specs


def _ohlc(time_value: int, spread: int | None = None) -> dict[str, Any]:
    row: dict[str, Any] = {
        "time": time_value,
        "open": 1.0,
        "high": 1.2,
        "low": 0.9,
        "close": 1.1,
    }
    if spread is not None:
        row["spread"] = spread
    return row


def _symbol(**extra: Any) -> SimpleNamespace:
    base = dict(
        name="XAUUSD",
        description="Gold",
        digits=3,
        point=0.001,
        trade_contract_size=100.0,
        volume_min=0.01,
        volume_max=1000.0,
        volume_step=0.01,
        volume_limit=0.0,
        trade_tick_size=0.001,
        trade_tick_value=0.1,
        trade_stops_level=0,
        trade_freeze_level=0,
        filling_mode=1,
        order_mode=127,
        trade_mode=4,
        trade_exemode=2,
        trade_calc_mode=2,
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
    base.update(extra)
    return SimpleNamespace(**base)


class _AccountBridge:
    available = True

    def __init__(self, info: SimpleNamespace) -> None:
        self._info = info

    def account_info(self) -> SimpleNamespace:
        return self._info

    def last_error(self) -> tuple[int, str]:
        return (1, "ok")


def _account_info(**extra: Any) -> SimpleNamespace:
    base = dict(
        login=1,
        balance=1.0,
        equity=1.0,
        margin=0.0,
        margin_free=1.0,
        margin_level=0.0,
        profit=0.0,
        leverage=1,
        currency="USD",
        server="desk",
        name="desk",
        company="desk",
        trade_mode=2,
        trade_allowed=True,
    )
    base.update(extra)
    return SimpleNamespace(**base)


@pytest.mark.unit
class TestSerializeRateBars:
    def test_recorded_spread_is_kept(self) -> None:
        items = serialize_rate_bars([_ohlc(1_700_000_000, 184)])
        assert items[0]["spread_points"] == 184
        assert items[0]["open"] == "1.0"
        assert items[0]["forming"] is True
        assert items[0]["closed"] is False

    def test_missing_spread_is_null_not_zero(self) -> None:
        items = serialize_rate_bars([_ohlc(1_700_000_000)])
        assert "spread" not in items[0]
        assert items[0]["spread_points"] is None
        assert items[0]["spread_points"] != 0

    def test_recorded_zero_spread_stays_zero(self) -> None:
        items = serialize_rate_bars([_ohlc(1_700_000_000, 0)])
        assert items[0]["spread_points"] == 0

    def test_only_the_last_bar_is_forming(self) -> None:
        items = serialize_rate_bars(
            [
                _ohlc(1_700_000_000, 180),
                _ohlc(1_700_000_060, 190),
            ]
        )
        assert len(items) == 2
        assert items[0]["closed"] is True
        assert items[0]["forming"] is False
        assert items[1]["closed"] is False
        assert items[1]["forming"] is True

    def test_numpy_spread_field_round_trips(self) -> None:
        numpy = pytest.importorskip("numpy")
        rates = numpy.array(
            [(1_700_000_000, 1.0, 1.2, 0.9, 1.1, 184)],
            dtype=[
                ("time", "i8"),
                ("open", "f8"),
                ("high", "f8"),
                ("low", "f8"),
                ("close", "f8"),
                ("spread", "i4"),
            ],
        )
        items = serialize_rate_bars(rates)
        assert items[0]["spread_points"] == 184
        assert items[0]["forming"] is True

    def test_numpy_without_spread_is_null(self) -> None:
        numpy = pytest.importorskip("numpy")
        rates = numpy.array(
            [(1_700_000_000, 1.0, 1.2, 0.9, 1.1)],
            dtype=[
                ("time", "i8"),
                ("open", "f8"),
                ("high", "f8"),
                ("low", "f8"),
                ("close", "f8"),
            ],
        )
        items = serialize_rate_bars(rates)
        assert items[0]["spread_points"] is None


@pytest.mark.unit
class TestSymbolPathAndCommission:
    def test_path_round_trips(self) -> None:
        specs = serialize_symbol_specs(_symbol(path=r"Standard\Metals\XAUUSD"))
        assert specs["path"] == r"Standard\Metals\XAUUSD"

    def test_missing_path_is_null(self) -> None:
        specs = serialize_symbol_specs(_symbol())
        assert specs["path"] is None
        assert specs["path"] != ""

    def test_blank_path_is_null(self) -> None:
        specs = serialize_symbol_specs(_symbol(path="  "))
        assert specs["path"] is None

    def test_missing_commission_is_null_not_zero(self) -> None:
        specs = serialize_symbol_specs(_symbol())
        assert specs["commission"] is None
        assert specs["commission"] != "0"
        assert specs["commission"] != 0
        assert specs["commission_source"] == "not_exposed_by_symbol_info"

    def test_recorded_commission_attribute_is_not_rewritten(self) -> None:
        specs = serialize_symbol_specs(_symbol(commission=0))
        assert specs["commission"] == "0"
        assert specs["commission_source"] == "symbol_info"


@pytest.mark.unit
class TestAccountGroup:
    def test_missing_group_is_null(self) -> None:
        runtime = MT5GatewayRuntime(bridge=_AccountBridge(_account_info()))
        runtime.diagnostics.connected = True
        account = runtime.account()
        assert account["group"] is None
        assert "commission" not in account

    def test_present_group_round_trips(self) -> None:
        runtime = MT5GatewayRuntime(
            bridge=_AccountBridge(_account_info(group="Standard"))
        )
        runtime.diagnostics.connected = True
        assert runtime.account()["group"] == "Standard"


@pytest.mark.unit
class TestCandlesUseSerializer:
    def test_runtime_candles_keep_null_spread_and_forming_bar(self) -> None:
        class _Bridge:
            available = True

            def copy_rates_from_pos(
                self, symbol: str, timeframe: int, start_pos: int, count: int
            ) -> list[dict[str, Any]]:
                assert symbol == "XAUUSD"
                assert start_pos == 0
                assert timeframe == 1
                assert count == 2
                return [_ohlc(1_700_000_000, 184), _ohlc(1_700_000_060)]

            def last_error(self) -> tuple[int, str]:
                return (1, "ok")

        runtime = MT5GatewayRuntime(bridge=_Bridge())
        runtime.diagnostics.connected = True
        runtime._ensure_symbol = lambda _symbol: "XAUUSD"  # type: ignore[method-assign]
        payload = runtime.candles("XAUUSD", timeframe="M1", count=2)
        items = payload["items"]
        assert payload["symbol"] == "XAUUSD"
        assert items[0]["spread_points"] == 184
        assert items[0]["closed"] is True
        assert items[1]["spread_points"] is None
        assert items[1]["forming"] is True
        assert len(items) == 2
