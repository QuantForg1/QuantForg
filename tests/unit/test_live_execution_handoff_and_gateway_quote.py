"""Live execution handoff + gateway quote integrity — no risk/threshold weaken."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_SCALPING_UNIVERSE,
    MICRO_SAFE_USD_MAJOR_DESKS,
)
from app.domain.institutional_trading.auto_trading import (
    allowlist_matches,
    prefer_allowlisted_handoff,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    discover_from_broker_rows,
    resolve_seed_to_broker_symbol,
)
from services.mt5_gateway.trade import build_mt5_trade_request, resolve_deal_price


@pytest.mark.unit
@pytest.mark.parametrize(
    ("desk", "broker"),
    [
        ("EURUSD", "EURUSD_I"),
        ("GBPUSD", "GBPUSD_I"),
        ("AUDUSD", "AUDUSD_I"),
        ("NZDUSD", "NZDUSD_I"),
        ("USDCHF", "USDCHF_I"),
        ("USDCAD", "USDCAD_I"),
    ],
)
def test_desk_to_broker_i_and_allowlist_identity(desk: str, broker: str) -> None:
    rows = [{"code": broker, "trade_mode": 4, "digits": 5}]
    discovered = discover_from_broker_rows(rows)
    assert resolve_seed_to_broker_symbol(desk, discovered=discovered) == broker
    allowed = {desk, "XAUUSD"}
    assert allowlist_matches(broker, allowed) is True
    assert allowlist_matches(desk, allowed) is True
    assert allowlist_matches("CADCHF_I", allowed) is False


@pytest.mark.unit
def test_prefer_allowlisted_handoff_puts_usd_majors_before_crosses() -> None:
    eligible = [
        "CADCHF_I",
        "AUDCAD_I",
        "EURUSD_I",
        "XAUUSD_I",
        "GEREUR",
        "GBPUSD_I",
    ]
    ordered = prefer_allowlisted_handoff(eligible, DEFAULT_SCALPING_UNIVERSE)
    assert ordered[0] in {"EURUSD_I", "GBPUSD_I", "XAUUSD_I"}
    assert ordered.index("EURUSD_I") < ordered.index("CADCHF_I")
    assert ordered.index("GBPUSD_I") < ordered.index("AUDCAD_I")
    # Non-allowlisted retained — Safety still decides.
    assert "CADCHF_I" in ordered
    assert "GEREUR" in ordered
    for desk in MICRO_SAFE_USD_MAJOR_DESKS[:2]:
        assert allowlist_matches(f"{desk}_I", set(DEFAULT_SCALPING_UNIVERSE))


@pytest.mark.unit
def test_build_trade_request_preserves_catalogue_exact_symbol() -> None:
    """Must not force .upper() on catalogue-exact names (Weltrade IPC)."""
    tick = SimpleNamespace(bid=4396.0, ask=4396.2)
    info = SimpleNamespace(
        digits=3,
        volume_min=0.01,
        volume_max=50.0,
        volume_step=0.01,
        trade_mode=4,
        filling_mode=1,
        trade_tick_size=0.001,
        trade_tick_value=0.1,
        trade_contract_size=100.0,
        point=0.001,
        stops_level=0,
        freeze_level=0,
        order_mode=127,
        execution_mode=1,
    )
    mt5 = MagicMock()
    mt5.symbol_info.return_value = info
    mt5.symbol_info_tick.return_value = tick
    req = build_mt5_trade_request(
        mt5,
        symbol="XAUUSD_I",
        action="buy",
        volume=0.01,
        price=0.0,
        stop_loss=4380.0,
        take_profit=4420.0,
        deviation=20,
        magic=42,
        comment="quantforg",
    )
    assert req["symbol"] == "XAUUSD_I"
    # Called with catalogue-exact spelling (not a forced different case).
    assert mt5.symbol_info_tick.call_args.args[0] == "XAUUSD_I"


@pytest.mark.unit
def test_resolve_deal_price_retries_transient_none_tick() -> None:
    tick = SimpleNamespace(bid=1.10, ask=1.1002)
    mt5 = MagicMock()
    mt5.symbol_info_tick.side_effect = [None, None, tick]
    price = resolve_deal_price(
        mt5,
        symbol="EURUSD_I",
        order_type=0,
        price=0.0,
        digits=5,
        force_tick=True,
    )
    assert price == 1.1002
    assert mt5.symbol_info_tick.call_count == 3


@pytest.mark.unit
def test_non_allowlisted_still_blocked_by_allowlist_match() -> None:
    allowed = set(DEFAULT_SCALPING_UNIVERSE)
    assert allowlist_matches("CADCHF_I", allowed) is False
    assert allowlist_matches("AEXEUR", allowed) is False
    assert allowlist_matches("EURUSD_I", allowed) is True
