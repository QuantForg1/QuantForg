"""FT-3: Gateway order guard — owner limits enforced on the Windows host.

New entries need Gold, SL > 0, TP > 0, volume <= 0.01, a known commission,
and a unique client_order_id. Closes are always allowed; SL/TP modifies may
only tighten. Inclusive planned risk cannot exceed 20% of equity, and the
open book cannot exceed 30%. The position maximum is five.
"""

from __future__ import annotations

import codecs
from dataclasses import replace
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import pytest

from services.mt5_gateway.order_guard import (
    KIND_CLOSE,
    KIND_ENTRY,
    KIND_SLTP,
    RETCODE_ORDER_GUARD_REJECTED,
    ClientOrderIdRegistry,
    OrderGuardRejected,
    classify_order,
    enforce_order_guard,
)

pytestmark = [pytest.mark.unit, pytest.mark.trading_core]

_ROOT = Path(__file__).resolve().parents[2]


_QUOTE: dict[str, Any] = {
    "bid": "4102.00",
    "ask": "4102.20",
    "specs": {"contract_size": "100", "tick_size": "0.01", "tick_value": "1"},
}
_EQUITY = Decimal("1000")


def _entry(**overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "symbol": "XAUUSD_i",
        "action": "buy",
        "volume": 0.01,
        "sl": 4100.0,
        "tp": 4103.5,
        "position": 0,
        "oms_kind": "",
        "client_order_id": "cid-1",
        "commission": 0,
    }
    body.update(overrides)
    return body


def _guard(body: dict[str, Any], **kwargs: Any) -> str:
    kwargs.setdefault("positions_lookup", lambda: [])
    kwargs.setdefault("equity", _EQUITY)
    kwargs.setdefault("quote", _QUOTE)
    kwargs.setdefault("registry", ClientOrderIdRegistry())
    return enforce_order_guard(body, **kwargs)


def _code(exc: pytest.ExceptionInfo[OrderGuardRejected]) -> str:
    return exc.value.code


class TestEntries:
    @pytest.mark.parametrize("symbol", ["XAUUSD_i", "XAUUSD", "xauusd", "GOLD"])
    def test_gold_entry_with_stops_passes(self, symbol: str) -> None:
        reg = ClientOrderIdRegistry()
        assert _guard(_entry(symbol=symbol), registry=reg) == KIND_ENTRY

    @pytest.mark.parametrize("symbol", ["EURUSD", "XAGUSD", "BTCUSD", "XAUJPY", ""])
    def test_non_gold_entry_rejected(self, symbol: str) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(symbol=symbol))
        assert _code(exc) == "GUARD_GOLD_ONLY"

    @pytest.mark.parametrize(
        ("field", "code"), [("sl", "GUARD_SL_REQUIRED"), ("tp", "GUARD_TP_REQUIRED")]
    )
    def test_missing_stop_rejected(self, field: str, code: str) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(**{field: 0}))
        assert _code(exc) == code

    @pytest.mark.parametrize("volume", [0.02, 0.011, 0.1, 0, -0.01])
    def test_volume_outside_owner_cap_rejected(self, volume: float) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(volume=volume))
        assert _code(exc) == "GUARD_MAX_LOT"

    def test_client_order_id_required(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(client_order_id="  "))
        assert _code(exc) == "GUARD_CLIENT_ORDER_ID_REQUIRED"

    def test_duplicate_client_order_id_rejected(self) -> None:
        reg = ClientOrderIdRegistry()
        _guard(_entry(), registry=reg)
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(), registry=reg)
        assert _code(exc) == "GUARD_DUPLICATE_CLIENT_ORDER_ID"
        assert exc.value.as_detail()["retcode"] == RETCODE_ORDER_GUARD_REJECTED

    def test_rejected_entry_does_not_burn_its_id(self) -> None:
        reg = ClientOrderIdRegistry()
        with pytest.raises(OrderGuardRejected):
            _guard(_entry(volume=0.02), registry=reg)
        assert _guard(_entry(), registry=reg) == KIND_ENTRY

    def test_position_ticket_on_an_entry_is_rejected(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(position=77, oms_kind=""))
        assert _code(exc) == "GUARD_ENTRY_POSITION"

    def test_unpriced_pending_gold_order_fails_closed(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(
                _entry(),
                orders_lookup=lambda: [
                    {
                        "ticket": 15,
                        "symbol": "XAUUSD",
                        "volume_current": "0.01",
                    }
                ],
            )
        assert _code(exc) == "GUARD_OPEN_RISK_UNMEASURED"

    def test_measured_pending_gold_order_under_the_cap_is_allowed(self) -> None:
        assert (
            _guard(
                _entry(client_order_id="second"),
                equity=Decimal("100"),
                orders_lookup=lambda: [
                    {
                        "ticket": 15,
                        "symbol": "XAUUSD",
                        "volume_current": "0.01",
                        "sl": 4100.0,
                        "price_open": 4102.0,
                    }
                ],
            )
            == KIND_ENTRY
        )

    def test_five_open_gold_positions_block_another_entry(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(
                _entry(),
                positions_lookup=lambda: [
                    {"ticket": ticket, "symbol": "XAUUSD", "volume": "0.01"}
                    for ticket in range(1, 6)
                ],
            )
        assert _code(exc) == "GUARD_MAX_POSITIONS"

    def test_unreadable_pending_orders_block_an_entry(self) -> None:
        def _down() -> list[dict[str, Any]]:
            raise RuntimeError("orders down")

        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(), orders_lookup=_down)
        assert _code(exc) == "GUARD_ORDERS_UNVERIFIED"

    def test_unpriced_open_gold_stop_fails_closed(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(
                _entry(),
                positions_lookup=lambda: [
                    {"ticket": 9, "symbol": "XAUUSD_i", "volume": "0.01"}
                ],
            )
        assert _code(exc) == "GUARD_OPEN_RISK_UNMEASURED"

    def test_one_measured_gold_position_is_allowed(self) -> None:
        assert (
            _guard(
                _entry(client_order_id="with-open"),
                equity=Decimal("100"),
                positions_lookup=lambda: [
                    {
                        "ticket": 9,
                        "symbol": "XAUUSD_i",
                        "volume": "0.01",
                        "sl": 4100.0,
                        "price_current": 4102.0,
                    }
                ],
            )
            == KIND_ENTRY
        )

    def test_buy_stop_above_bid_is_rejected(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(_entry(sl=4102.5))
        assert _code(exc) == "GUARD_SL_WRONG_SIDE"

    def test_exact_20_percent_is_allowed_and_above_is_rejected(self) -> None:
        # 0.01 lot, tick 0.01 / $1, and the quote spread of 0.20 counts.
        # Distance 19.80 + spread 0.20 = $20.00, exactly 20% of $100.
        # One further tick is $20.01 and is rejected.
        allowed = _entry(sl=4082.40, tp=4120.0, client_order_id="exact-20")
        assert _guard(allowed, equity=Decimal("100")) == KIND_ENTRY
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(
                _entry(sl=4082.39, tp=4120.0, client_order_id="over-20"),
                equity=Decimal("100"),
            )
        assert _code(exc) == "GUARD_MAX_RISK"
        assert "20.01" in str(exc.value)

    def test_order_slippage_counts_toward_the_cap(self) -> None:
        quote = {
            "bid": "4102.00",
            "ask": "4102.20",
            "specs": {
                "contract_size": "100",
                "tick_size": "0.01",
                "tick_value": "1",
                "point": "0.01",
            },
        }
        # 19.70 + spread 0.20 + slippage 10 * 0.01 = 20.00.
        allowed = _entry(sl=4082.50, tp=4120.0, client_order_id="slip-ok", slippage=10)
        assert _guard(allowed, equity=Decimal("100"), quote=quote) == KIND_ENTRY
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(
                _entry(sl=4082.49, tp=4120.0, client_order_id="slip-over", slippage=10),
                equity=Decimal("100"),
                quote=quote,
            )
        assert _code(exc) == "GUARD_MAX_RISK"

    def test_unknown_commission_rejects_without_a_zero_fee_pass(self) -> None:
        body = _entry(client_order_id="no-fee")
        body.pop("commission")
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(body, equity=Decimal("100"))
        assert _code(exc) == "GUARD_COMMISSION_UNKNOWN"

    def test_known_commission_can_push_a_ticket_over_20_percent(self) -> None:
        # Distance 2.20 + spread 0.20 = $2.40. Commission $18.00 makes $20.40.
        with pytest.raises(OrderGuardRejected) as exc:
            _guard(
                _entry(client_order_id="fee-over", commission=18),
                equity=Decimal("100"),
            )
        assert _code(exc) == "GUARD_MAX_RISK"
        assert "20.40" in str(exc.value)

    def test_reverse_without_position_is_an_entry(self) -> None:
        assert classify_order(_entry(oms_kind="reverse")) == KIND_ENTRY


class TestClientOrderIdRegistry:
    def test_ids_expire_after_ttl(self) -> None:
        now = [1000.0]
        reg = ClientOrderIdRegistry(ttl_seconds=60, clock=lambda: now[0])
        assert reg.claim("a") is True
        assert reg.claim("a") is False
        now[0] += 61
        assert reg.claim("a") is True

    def test_bounded_memory(self) -> None:
        reg = ClientOrderIdRegistry(max_tracked=3)
        for cid in ("a", "b", "c", "d"):
            assert reg.claim(cid) is True
        # Oldest was evicted to stay within the bound.
        assert reg.claim("a") is True


class TestCloses:
    @pytest.mark.parametrize("oms_kind", ["close", "partial_close"])
    def test_explicit_close_of_the_open_ticket_is_allowed(self, oms_kind: str) -> None:
        body = {
            "symbol": "XAUUSD",
            "action": "sell",
            "volume": 0.01,
            "sl": 0,
            "tp": 0,
            "position": 77,
            "oms_kind": oms_kind,
        }
        assert (
            enforce_order_guard(
                body,
                positions_lookup=lambda: [
                    {"ticket": 77, "symbol": "XAUUSD", "volume": "0.01"}
                ],
            )
            == KIND_CLOSE
        )

    def test_close_without_a_live_ticket_is_rejected(self) -> None:
        body = {
            "symbol": "XAUUSD",
            "action": "sell",
            "volume": 0.01,
            "position": 77,
            "oms_kind": "close",
        }
        with pytest.raises(OrderGuardRejected) as exc:
            enforce_order_guard(body, positions_lookup=lambda: [])
        assert _code(exc) == "GUARD_CLOSE_UNVERIFIED"


class TestSlTpModify:
    @staticmethod
    def _pos(*, type_: int, sl: float) -> list[dict[str, Any]]:
        return [{"ticket": 77, "type": type_, "sl": str(sl), "tp": "4110"}]

    @staticmethod
    def _sltp(sl: float, tp: float = 4110.0) -> dict[str, Any]:
        return {
            "symbol": "XAUUSD",
            "action": "sltp",
            "oms_kind": "sltp",
            "volume": 0,
            "sl": sl,
            "tp": tp,
            "position": 77,
        }

    @pytest.mark.parametrize(
        ("type_", "current", "new"),
        [(0, 4100.0, 4101.0), (0, 4100.0, 4100.0), (1, 4110.0, 4109.0)],
    )
    def test_tightening_allowed(self, type_: int, current: float, new: float) -> None:
        kind = enforce_order_guard(
            self._sltp(new),
            positions_lookup=lambda: self._pos(type_=type_, sl=current),
        )
        assert kind == KIND_SLTP

    @pytest.mark.parametrize(
        ("type_", "current", "new"), [(0, 4100.0, 4099.0), (1, 4110.0, 4111.0)]
    )
    def test_widening_rejected(self, type_: int, current: float, new: float) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            enforce_order_guard(
                self._sltp(new),
                positions_lookup=lambda: self._pos(type_=type_, sl=current),
            )
        assert _code(exc) == "GUARD_SL_WIDEN"

    def test_setting_first_sl_allowed(self) -> None:
        kind = enforce_order_guard(
            self._sltp(4095.0), positions_lookup=lambda: self._pos(type_=0, sl=0)
        )
        assert kind == KIND_SLTP

    @pytest.mark.parametrize(
        ("sl", "tp", "code"),
        [(0, 4110.0, "GUARD_SL_REQUIRED"), (4100.0, 0, "GUARD_TP_REQUIRED")],
    )
    def test_removing_stops_rejected(self, sl: float, tp: float, code: str) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            enforce_order_guard(
                self._sltp(sl, tp), positions_lookup=lambda: self._pos(type_=0, sl=4100)
            )
        assert _code(exc) == code

    def test_unknown_position_fails_closed(self) -> None:
        with pytest.raises(OrderGuardRejected) as exc:
            enforce_order_guard(self._sltp(4101.0), positions_lookup=lambda: [])
        assert _code(exc) == "GUARD_SLTP_UNVERIFIED"

    def test_lookup_error_fails_closed(self) -> None:
        def _boom() -> list[dict[str, Any]]:
            raise RuntimeError("MT5 busy")

        with pytest.raises(OrderGuardRejected) as exc:
            enforce_order_guard(self._sltp(4101.0), positions_lookup=_boom)
        assert _code(exc) == "GUARD_SLTP_UNVERIFIED"


def test_gateway_client_sends_unique_client_order_id() -> None:
    import app.infrastructure.brokers.mt5.gateway_client as mod
    from app.domain.entities.mt5_order import TradeRequest

    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content)["client_order_id"])
        return httpx.Response(
            200,
            json={"ok": True, "retcode": 10009, "order_ticket": 1, "deal_ticket": 2},
        )

    transport = httpx.MockTransport(handler)
    original = mod.httpx.Client

    class PatchedClient(original):  # type: ignore[valid-type,misc]
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            kwargs["transport"] = transport
            super().__init__(*args, **kwargs)

    client = mod.GatewayMT5Client(base_url="https://gw.example", token="tok")
    request = TradeRequest(
        symbol="XAUUSD",
        action="buy",
        volume=Decimal("0.01"),
        price=Decimal("0"),
        stop_loss=Decimal("4100"),
        take_profit=Decimal("4103.5"),
        deviation=20,
        magic=0,
    )
    mod.httpx.Client = PatchedClient  # type: ignore[misc]
    try:
        object.__setattr__(client, "_connected", True)
        client.order_send(request)
        client.order_send(request)
        client.order_send(replace(request, client_order_id="fixed-id"))
    finally:
        mod.httpx.Client = original  # type: ignore[misc]

    assert seen == ["", "", "fixed-id"]


def test_gateway_ps1_files_are_ascii_or_utf8_bom() -> None:
    """Windows PowerShell 5.1 reads BOM-less files as ANSI and mangles UTF-8."""
    scripts = [
        *sorted((_ROOT / "deploy" / "mt5_gateway").glob("*.ps1")),
        *sorted((_ROOT / "scripts").glob("*.ps1")),
        _ROOT / "start_mt5_gateway.ps1",
    ]
    bad = []
    for path in scripts:
        data = path.read_bytes()
        if data.startswith(codecs.BOM_UTF8):
            continue
        if any(byte > 127 for byte in data):
            bad.append(path.name)
    assert len(scripts) > 20
    assert bad == []
