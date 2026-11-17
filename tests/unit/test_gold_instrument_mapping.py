"""Gold First mapping: metadata-validated canonical XAUUSD per broker.

Only the Weltrade spec is real Production evidence (Weltrade-Real 12439799,
17 Nov 2026). The other brokers use FIXTURES modelled on typical published
gold contract specs to exercise the validator; they are NOT evidence that
those brokers are validated. Live validation needs each broker's DEMO
account (owner action A14).
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.trading.gold_instrument_mapping import (
    resolve_gold_mapping,
    validate_gold_spec,
)

pytestmark = [pytest.mark.unit]

# Real: GET /api/v1/mt5/symbols/XAUUSD, Weltrade-Real, 17 Nov 2026 05:4x UTC.
WELTRADE_LIVE = {
    "code": "XAUUSD",
    "description": "Gold Ounce vs US Dollar (Spot)",
    "currency_base": "USD",
    "currency_profit": "USD",
    "contract_size": "100.0",
    "digits": 3,
    "point": "0.001",
    "tick_size": "0.001",
    "tick_value": "0.1",
    "bid": "3885.683",
    "ask": "3886.137",
    "volume_min": "0.01",
    "volume_step": "0.01",
    "trade_mode": "full",
    "selected": True,
}


def _fixture(
    code: str, *, digits: int, tick: str, value: str, **kw: Any
) -> dict[str, Any]:
    spec = {
        "code": code,
        "description": "Gold vs US Dollar",
        "currency_base": "XAU",
        "currency_profit": "USD",
        "contract_size": "100",
        "digits": digits,
        "tick_size": tick,
        "tick_value": value,
        "bid": "3885.68",
        "ask": "3885.95",
        "volume_min": "0.01",
        "volume_max": "50",
        "volume_step": "0.01",
        "trade_mode": "full",
        "selected": True,
    }
    spec.update(kw)
    return spec


BROKER_FIXTURES = {
    "weltrade": ("XAUUSD", WELTRADE_LIVE),
    "xm": ("GOLD", _fixture("GOLD", digits=2, tick="0.01", value="1.0")),
    "exness": ("XAUUSDm", _fixture("XAUUSDm", digits=3, tick="0.001", value="0.1")),
    "hfm": ("XAUUSD", _fixture("XAUUSD", digits=2, tick="0.01", value="1.0")),
    "icmarkets": ("XAUUSD", _fixture("XAUUSD", digits=2, tick="0.01", value="1.0")),
    "pepperstone": ("XAUUSD", _fixture("XAUUSD", digits=2, tick="0.01", value="1.0")),
    "fpmarkets": ("XAUUSD", _fixture("XAUUSD", digits=2, tick="0.01", value="1.0")),
    "justmarkets": (
        "XAUUSD.m",
        _fixture("XAUUSD.m", digits=3, tick="0.001", value="0.1"),
    ),
}


@pytest.mark.parametrize("broker", sorted(BROKER_FIXTURES))
def test_each_broker_maps_its_own_gold_symbol(broker: str) -> None:
    expected, spec = BROKER_FIXTURES[broker]
    eurusd = {
        "code": "EURUSD",
        "description": "Euro vs US Dollar",
        "currency_base": "EUR",
        "currency_profit": "USD",
        "bid": "1.08",
        "ask": "1.0801",
    }
    m = resolve_gold_mapping(
        [spec, eurusd], broker=broker, account_currency="USD", login=12439799
    )
    assert m.status == "VALIDATED", m.as_dict()
    assert m.broker_symbol == expected
    assert m.canonical == "XAUUSD"
    assert m.login_masked == "12•••99"
    d = m.as_dict()
    assert d["spec"]["contract_size"] and d["spec"]["tick_value"]


def test_weltrade_live_spec_passes_geometry_check() -> None:
    check = validate_gold_spec(WELTRADE_LIVE, account_currency="USD")
    assert check.ok, check.reasons
    assert check.evidence["geometry_checked"] is True


def test_name_alone_is_not_enough() -> None:
    # Named XAUUSD, but metadata says a USD-based non-gold instrument.
    fake = dict(WELTRADE_LIVE, description="US Dollar Index CFD")
    check = validate_gold_spec(fake, account_currency="USD")
    assert not check.ok
    assert "metadata_does_not_identify_gold" in check.reasons


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"currency_profit": "EUR", "code": "XAUEUR"}, "not_quoted_in_usd:EUR"),
        ({"bid": "25000", "ask": "25001"}, "price_outside_gold_band:25000"),
        ({"bid": None, "ask": None}, "no_live_quote"),
        ({"contract_size": "1"}, "tick_geometry_mismatch"),
        ({"tick_value": None}, "tick_value_missing"),
        ({"trade_mode": "disabled"}, "trade_mode_disabled"),
        ({"trade_mode": "closeonly"}, "trade_mode_closeonly"),
        ({"volume_step": "0"}, "volume_step_missing"),
        ({"bid": "3890", "ask": "3880"}, "crossed_quote"),
    ],
)
def test_invalid_metadata_rejected(change: dict[str, Any], reason: str) -> None:
    check = validate_gold_spec(dict(WELTRADE_LIVE, **change), account_currency="USD")
    assert not check.ok
    assert any(r.startswith(reason) for r in check.reasons), check.reasons


def test_missing_and_invalid_and_ambiguous() -> None:
    assert resolve_gold_mapping([], broker="x").status == "MISSING"
    bad = dict(WELTRADE_LIVE, trade_mode="disabled")
    m = resolve_gold_mapping([bad], broker="x", account_currency="USD")
    assert m.status == "INVALID" and not m.tradable
    a = dict(WELTRADE_LIVE)
    b = dict(WELTRADE_LIVE, code="XAUUSD.pro")
    amb = resolve_gold_mapping([a, b], broker="x", account_currency="USD")
    assert amb.status == "AMBIGUOUS" and amb.broker_symbol is None
    pinned = resolve_gold_mapping(
        [a, b], broker="x", account_currency="USD", pinned_symbol="xauusd.pro"
    )
    assert pinned.status == "VALIDATED" and pinned.broker_symbol == "XAUUSD.pro"


def test_geometry_skipped_for_non_usd_account() -> None:
    # tick_value is in account currency; only check geometry for USD accounts.
    eur = dict(WELTRADE_LIVE, tick_value="0.092")
    assert validate_gold_spec(eur, account_currency="EUR").ok
    assert not validate_gold_spec(eur, account_currency="USD").ok


# --- execution gate (ITE market context) -----------------------------------

from types import SimpleNamespace  # noqa: E402
from unittest.mock import MagicMock  # noqa: E402

from app.application.services import ite_cycle_market_context as ctxmod  # noqa: E402


@pytest.fixture
def _gold_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.domain.trading.gold_only.gold_only_enabled", lambda: True)
    ctxmod._GOLD_GATE_CACHE.clear()


def _adapter(spec: dict[str, Any] | Exception) -> MagicMock:
    adapter = MagicMock()
    adapter.client = SimpleNamespace(is_connected=True, session_mode="attached")
    if isinstance(spec, Exception):
        adapter.symbol_info.side_effect = spec
    else:
        adapter.symbol_info.return_value = SimpleNamespace(**spec)
    adapter.account_info.return_value = SimpleNamespace(currency="USD")
    return adapter


@pytest.mark.asyncio
@pytest.mark.usefixtures("_gold_on")
async def test_gate_passes_real_weltrade_spec() -> None:
    gate = await ctxmod._gold_metadata_gate(_adapter(WELTRADE_LIVE), "XAUUSD")
    assert gate["ok"] is True and gate["geometry_checked"] is True


@pytest.mark.asyncio
@pytest.mark.usefixtures("_gold_on")
async def test_gate_fails_closed_on_bad_or_unreadable_metadata() -> None:
    bad = dict(WELTRADE_LIVE, contract_size="1")
    gate = await ctxmod._gold_metadata_gate(_adapter(bad), "XAUUSD")
    assert gate["ok"] is False
    ctxmod._GOLD_GATE_CACHE.clear()
    gate = await ctxmod._gold_metadata_gate(_adapter(RuntimeError("down")), "XAUUSD")
    assert gate["ok"] is False
    assert "XAUUSD" not in ctxmod._GOLD_GATE_CACHE  # unreadable is never cached


@pytest.mark.asyncio
@pytest.mark.usefixtures("_gold_on")
async def test_market_context_rejects_symbol_failing_gold_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.domain.institutional_trading.ai_scalping.universe_discovery."
        "fetch_broker_symbol_rows",
        lambda *_a, **_k: ({"code": "XAUUSD", "trade_mode": 4},),
    )
    adapter = _adapter(dict(WELTRADE_LIVE, description="US Dollar Index CFD"))
    ctx = await ctxmod.build_ite_cycle_market_context(adapter, symbol="XAUUSD")
    assert ctx.ok is False
    assert "GOLD_MAPPING_INVALID" in ctx.reason
    assert ctx.diagnostics.get("next_action") == "FAIL_CLOSED"
    adapter.copy_rates_from_pos.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.usefixtures("_gold_on")
async def test_non_gold_instrument_blocked_before_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    adapter = _adapter(WELTRADE_LIVE)
    ctx = await ctxmod.build_ite_cycle_market_context(adapter, symbol="EURUSD")
    assert ctx.ok is False
    assert "DISABLED_AUTONOMOUS_SYMBOL" in ctx.reason
