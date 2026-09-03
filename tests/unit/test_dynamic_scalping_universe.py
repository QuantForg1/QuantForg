"""Dynamic scalping universe discovery + session priority tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.application.services.institutional_multi_asset_scanner import (
    resolve_scan_universe,
)
from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
)
from app.domain.institutional_trading.ai_scalping.session_symbol_priority import (
    prioritize_universe_for_session,
    session_priority_score,
)
from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
    SymbolStatsBook,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    build_dynamic_scalping_universe,
    catalogue_ordered_candidates,
    classify_broker_symbol,
    classify_catalogue_summary,
    discover_from_broker_rows,
    is_liquid_scalping_candidate,
    resolve_seed_to_broker_symbol,
)


@pytest.mark.unit
def test_classify_broker_symbols() -> None:
    assert classify_broker_symbol("EURUSD") == "forex"
    assert classify_broker_symbol("XAUUSD") == "metals"
    assert classify_broker_symbol("BTCUSD") == "crypto"
    assert classify_broker_symbol("NDXUSD") == "indices"
    assert classify_broker_symbol("XTIUSD") == "commodities"


@pytest.mark.unit
def test_liquid_candidates_exclude_close_only_and_exotics() -> None:
    assert is_liquid_scalping_candidate("EURUSD", trade_mode=4) is True
    assert is_liquid_scalping_candidate("EURJPY", trade_mode=4) is True
    assert is_liquid_scalping_candidate("XAUUSD", trade_mode=4) is True
    assert is_liquid_scalping_candidate("EURUSD_I", trade_mode=4) is True
    assert is_liquid_scalping_candidate("XAUUSD_I", trade_mode=4) is True
    assert is_liquid_scalping_candidate("EURRUB", trade_mode=4) is False
    assert is_liquid_scalping_candidate("USDTRY", trade_mode=4) is False
    assert is_liquid_scalping_candidate("EURUSD", trade_mode=3) is False
    assert is_liquid_scalping_candidate("NAS100", trade_mode=4) is False


@pytest.mark.unit
def test_weltrade_i_suffix_seed_maps_to_broker_code() -> None:
    rows = [
        {"code": "EURUSD_I", "trade_mode": 4, "digits": 5},
        {"code": "XAUUSD_I", "trade_mode": 4, "digits": 3},
        {"code": "GBPUSD_I", "trade_mode": 4, "digits": 5},
        {"code": "NDXUSD", "trade_mode": 4, "digits": 1},
        {"code": "BTCUSD", "trade_mode": 4, "digits": 2},
    ]
    discovered = discover_from_broker_rows(rows)
    summary = classify_catalogue_summary(discovered)
    assert "EURUSD_I" in summary["liquid_candidates"]
    assert "XAUUSD_I" in summary["liquid_candidates"]
    universe = build_dynamic_scalping_universe(discovered, max_symbols=36)
    assert "EURUSD_I" in universe
    assert "XAUUSD_I" in universe
    assert "EURUSD" not in universe  # desk seed remapped to broker form
    assert "NDXUSD" in universe
    assert "BTCUSD" in universe


@pytest.mark.unit
def test_build_dynamic_universe_from_live_catalogue_fixture() -> None:
    path = Path("docs/trading/_broker_symbols_live.json")
    if not path.exists():
        pytest.skip("live broker catalogue fixture not present")
    items = json.loads(path.read_text(encoding="utf-8-sig"))["items"]
    discovered = discover_from_broker_rows(items)
    summary = classify_catalogue_summary(discovered)
    assert summary["broker_symbols_found"] == 83
    assert "forex" in summary["by_class"]
    universe = build_dynamic_scalping_universe(discovered, max_symbols=36)
    assert "XAUUSD" in universe
    assert "EURUSD" in universe
    assert "EURJPY" in universe  # cross discovered from broker
    assert "XAGUSD" in universe  # metal discovered
    assert any(s in universe for s in ("NDXUSD", "DJIUSD", "SPXUSD", "GEREUR"))
    assert any(s in universe for s in ("XTIUSD", "XBRUSD"))
    assert "NAS100" not in universe
    assert "EURRUB" not in universe
    assert len(universe) <= 36
    assert len(universe) > len(DEFAULT_SCALPING_UNIVERSE)


@pytest.mark.unit
def test_resolve_scan_universe_expands_with_broker_rows() -> None:
    from dataclasses import replace

    rows = [
        {"code": "EURUSD", "trade_mode": 4, "digits": 5},
        {"code": "NZDUSD", "trade_mode": 4, "digits": 5},
        {"code": "EURJPY", "trade_mode": 4, "digits": 3},
        {"code": "XAGUSD", "trade_mode": 4, "digits": 3},
        {"code": "EURRUB", "trade_mode": 3, "digits": 5},
        {"code": "NAS100", "trade_mode": 4, "digits": 1},
    ]
    cfg = replace(DEFAULT_AI_SCALPING_CONFIG, live_symbol_learning_enabled=False)
    uni = resolve_scan_universe(
        cfg,
        broker_symbol_rows=rows,
        session="london",
    )
    assert "EURUSD" in uni
    assert "EURJPY" in uni
    assert "XAGUSD" in uni
    assert "EURRUB" not in uni
    assert "NAS100" not in uni
    # London prioritizes EUR/GBP near the front
    assert uni.index("EURUSD") < uni.index("NZDUSD")


@pytest.mark.unit
def test_session_priority_prefers_london_fx() -> None:
    assert session_priority_score("EURUSD", "london") > session_priority_score(
        "AUDUSD", "london"
    )
    ordered = prioritize_universe_for_session(
        ("AUDUSD", "EURUSD", "XAUUSD"), "london"
    )
    assert ordered[0] == "EURUSD"


@pytest.mark.unit
def test_symbol_stats_demote_after_hard_fails(tmp_path: Path) -> None:
    book = SymbolStatsBook(_path=tmp_path / "stats.json")
    for _ in range(8):
        book.record_scan("NDXUSD", eligible=False, broker_hard_fail=True)
    assert "NDXUSD" in book.demoted_symbols()
    boost = book.performance_boost()
    assert boost["NDXUSD"] <= -50


@pytest.mark.unit
def test_xauusd_resolves_to_catalogue_xauusd_i() -> None:
    rows = [
        {"code": "XAUUSD_I", "trade_mode": 4, "digits": 3},
        {"code": "EURUSD_I", "trade_mode": 4, "digits": 5},
    ]
    discovered = discover_from_broker_rows(rows)
    assert resolve_seed_to_broker_symbol("XAUUSD", discovered=discovered) == "XAUUSD_I"
    ordered = catalogue_ordered_candidates("XAUUSD", discovered=discovered)
    assert ordered == ("XAUUSD_I",)
    assert "XAUUSD" not in ordered


@pytest.mark.unit
def test_healthy_xauusd_i_clears_historical_demotion(tmp_path: Path) -> None:
    book = SymbolStatsBook(
        _path=tmp_path / "stats.json",
        _demote_cooldown_seconds=3600.0,
    )
    for _ in range(8):
        book.record_scan("XAUUSD_I", eligible=False, broker_hard_fail=True)
    assert "XAUUSD_I" in book.demoted_symbols()
    # Quality NO_TRADE with healthy MD must recover (not require BUY/SELL).
    book.record_scan(
        "XAUUSD_I",
        eligible=False,
        broker_hard_fail=False,
        broker_ok=True,
        reject_reason="Weak structure score",
    )
    assert "XAUUSD_I" not in book.demoted_symbols()


@pytest.mark.unit
def test_unhealthy_symbol_remains_demoted_until_cooldown(tmp_path: Path) -> None:
    book = SymbolStatsBook(
        _path=tmp_path / "stats.json",
        _demote_cooldown_seconds=3600.0,
    )
    for _ in range(8):
        book.record_scan("DEADUSD", eligible=False, broker_hard_fail=True)
    assert "DEADUSD" in book.demoted_symbols()
    book.record_scan("DEADUSD", eligible=False, broker_hard_fail=True)
    assert "DEADUSD" in book.demoted_symbols()


@pytest.mark.unit
def test_demotion_cooldown_expires_for_recovery_probe(tmp_path: Path) -> None:
    book = SymbolStatsBook(
        _path=tmp_path / "stats.json",
        _demote_cooldown_seconds=0.01,
    )
    for _ in range(8):
        book.record_scan("XAUUSD_I", eligible=False, broker_hard_fail=True)
    assert "XAUUSD_I" in book.demoted_symbols()
    import time

    time.sleep(0.02)
    released = book.expire_stale_demotions()
    assert "XAUUSD_I" in released
    assert "XAUUSD_I" not in book.demoted_symbols()


@pytest.mark.unit
def test_recovered_seed_reenters_dynamic_universe_despite_demotion() -> None:
    rows = [
        {"code": "XAUUSD_I", "trade_mode": 4, "digits": 3},
        {"code": "EURUSD_I", "trade_mode": 4, "digits": 5},
        {"code": "BTCUSD", "trade_mode": 4, "digits": 2},
        {"code": "LTCUSD", "trade_mode": 4, "digits": 2},
    ]
    discovered = discover_from_broker_rows(rows)
    demoted = {"XAUUSD_I", "EURUSD_I"}
    universe = build_dynamic_scalping_universe(
        discovered,
        demoted=demoted,
        seed_recovery={"XAUUSD_I"},
        max_symbols=36,
    )
    # Catalogue-liquid seed XAUUSD → XAUUSD_I recovers even while demoted.
    assert "XAUUSD_I" in universe
    # Non-recovered demoted EURUSD_I stays out of seed slot if demoted…
    # but seed recovery for EURUSD is also liquid — seed loop adds recovery
    # for all liquid seeds automatically.
    assert "EURUSD_I" in universe


@pytest.mark.unit
def test_dynamic_universe_not_shrunk_by_static_plane_allowlist() -> None:
    """Ops plane seed of 10 must not erase broker-discovered liquid symbols."""
    from dataclasses import replace
    from unittest.mock import MagicMock

    rows = [
        {"code": "EURUSD", "trade_mode": 4},
        {"code": "EURJPY", "trade_mode": 4},
        {"code": "XAGUSD", "trade_mode": 4},
        {"code": "GBPJPY", "trade_mode": 4},
    ]
    plane = MagicMock()
    plane.allowed_symbols = tuple(DEFAULT_SCALPING_UNIVERSE)
    cfg = replace(DEFAULT_AI_SCALPING_CONFIG, live_symbol_learning_enabled=False)
    uni = resolve_scan_universe(
        cfg,
        plane=plane,
        broker_symbol_rows=rows,
        session="london",
    )
    assert "EURJPY" in uni
    assert "XAGUSD" in uni
    assert "GBPJPY" in uni
    assert "GBPUSD" not in uni  # seed absent from catalogue stays out
    assert len(uni) == 4
    cfg = DEFAULT_AI_SCALPING_CONFIG
    assert cfg.normal_vol.quality == 74
    assert cfg.normal_vol.confidence == 71
    assert cfg.min_structure_score == 60
    assert cfg.min_momentum_score == 55
    assert cfg.dynamic_universe_enabled is True
    assert cfg.allow_martingale is False
    assert cfg.allow_grid is False
