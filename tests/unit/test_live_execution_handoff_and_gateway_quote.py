"""Live execution handoff + gateway quote integrity — no risk/threshold weaken."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_SCALPING_UNIVERSE,
    MICRO_SAFE_USD_MAJOR_DESKS,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    discover_from_broker_rows,
    resolve_seed_to_broker_symbol,
)
from app.domain.institutional_trading.auto_trading import (
    allowlist_matches,
    ensure_scalping_universe_handoff,
    prefer_allowlisted_handoff,
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
@pytest.mark.trading_core
def test_full_catalogue_seed_does_not_demote_oil() -> None:
    """BROKER_DISCOVERED catalogue-as-seed is a no-op — the live defect."""
    eligible = ["XBRUSD", "XTIUSD", "EURUSD_I", "GBPUSD_I", "XAUUSD_I"]
    catalogue = (*eligible, "AUDUSD_I", "NZDUSD_I", "CADCHF_I")
    as_catalogue = prefer_allowlisted_handoff(eligible, catalogue)
    assert as_catalogue[0] == "XBRUSD"
    as_desks = prefer_allowlisted_handoff(eligible, DEFAULT_SCALPING_UNIVERSE)
    assert as_desks[0] in {"EURUSD_I", "GBPUSD_I", "XAUUSD_I"}
    assert as_desks.index("EURUSD_I") < as_desks.index("XBRUSD")
    assert "XBRUSD" in as_desks


@pytest.mark.unit
@pytest.mark.trading_core
def test_prioritize_ready_keeps_sniper_takes_ahead_of_injected_majors() -> None:
    """Live defect: ensure/prefer buried NDX/LTC/BTC behind seed majors."""
    from app.domain.institutional_trading.auto_trading import (
        ensure_scalping_universe_handoff,
        prioritize_ready_execution_handoff,
    )

    catalogue = [
        "EURUSD",
        "GBPUSD",
        "AUDUSD",
        "NZDUSD",
        "USDCHF",
        "USDCAD",
        "USDJPY",
        "XAUUSD",
        "BTCUSD",
        "ETHUSD",
        "NDXUSD",
        "LTCUSD",
        "EURCHF",
    ]
    # Scanner already ranked sniper-ready desks first.
    scan_ready = ["NDXUSD", "LTCUSD", "BTCUSD", "EURCHF"]
    after_ensure = ensure_scalping_universe_handoff(
        scan_ready, DEFAULT_SCALPING_UNIVERSE, catalogue=catalogue
    )
    # Without prioritize, injected majors steal first focus.
    assert after_ensure[0] in set(DEFAULT_SCALPING_UNIVERSE)
    ordered = prioritize_ready_execution_handoff(
        after_ensure, ["NDXUSD", "LTCUSD", "BTCUSD"]
    )
    assert ordered[:3] == ["NDXUSD", "LTCUSD", "BTCUSD"]
    assert ordered.index("EURUSD") > ordered.index("BTCUSD")
    assert "EURCHF" in ordered


@pytest.mark.unit
@pytest.mark.trading_core
def test_ite_handoff_seeds_scalping_universe_not_full_catalogue() -> None:
    import inspect

    from app.application.services.institutional_ite_runtime import (
        InstitutionalIteRuntime,
    )

    src = inspect.getsource(InstitutionalIteRuntime._multi_asset_preferred_symbol)
    assert "prefer_allowlisted_handoff" in src
    assert "DEFAULT_SCALPING_UNIVERSE" in src
    assert "ensure_scalping_universe_handoff" in src
    assert "prioritize_ready_execution_handoff" in src
    assert "len(plane_allowed) >= 2" not in src
    assert "SYMBOL_SAFETY_RELEASE" in inspect.getsource(
        InstitutionalIteRuntime.run_auto_cycle
    )


@pytest.mark.unit
@pytest.mark.trading_core
def test_ensure_handoff_injects_missing_majors_and_demotes_oil() -> None:
    """Live defect: research/scan eligible can be oil-first and omit majors."""
    catalogue = [
        "XBRUSD",
        "XTIUSD",
        "EURUSD_I",
        "GBPUSD_I",
        "AUDUSD_I",
        "NZDUSD_I",
        "USDCHF_I",
        "USDCAD_I",
        "USDJPY_I",
        "XAUUSD_I",
        "BTCUSD",
        "ETHUSD",
        "EURJPY",
    ]
    oil_first = ["XBRUSD", "XTIUSD", "EURJPY"]
    ordered = ensure_scalping_universe_handoff(
        oil_first, DEFAULT_SCALPING_UNIVERSE, catalogue=catalogue
    )
    assert ordered[0] in {"EURUSD_I", "GBPUSD_I", "AUDUSD_I"}
    assert "EURUSD_I" in ordered
    assert "XAUUSD_I" in ordered
    assert ordered.index("EURUSD_I") < ordered.index("EURJPY")
    assert "XBRUSD" not in ordered
    assert "XTIUSD" not in ordered


@pytest.mark.unit
@pytest.mark.trading_core
def test_ensure_handoff_does_not_invent_absent_catalogue_desks() -> None:
    ordered = ensure_scalping_universe_handoff(
        ["GBPUSD_I", "XBRUSD"],
        DEFAULT_SCALPING_UNIVERSE,
        catalogue=["GBPUSD_I", "XBRUSD"],
    )
    assert ordered[0] == "GBPUSD_I"
    assert "EURUSD" not in ordered
    assert "EURUSD_I" not in ordered
    assert "XBRUSD" not in ordered


@pytest.mark.unit
@pytest.mark.trading_core
def test_ensure_handoff_keeps_oil_when_only_unspecified_remain() -> None:
    ordered = ensure_scalping_universe_handoff(
        ["XBRUSD", "XTIUSD"],
        DEFAULT_SCALPING_UNIVERSE,
        catalogue=["XBRUSD", "XTIUSD"],
    )
    assert ordered[0] in {"XBRUSD", "XTIUSD"}
    assert "XBRUSD" in ordered


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
