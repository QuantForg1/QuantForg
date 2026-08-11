"""Scanner overlap + demotion recovery regressions (no forced trades)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from app.application.services import institutional_multi_asset_scanner as scanner
from app.domain.institutional_trading.ai_scalping.config import DEFAULT_AI_SCALPING_CONFIG
from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
    SymbolStatsBook,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    build_dynamic_scalping_universe,
    catalogue_ordered_candidates,
    discover_from_broker_rows,
)


@pytest.mark.unit
@pytest.mark.asyncio
async def test_scanner_cycles_do_not_overlap() -> None:
    release = asyncio.Event()
    entered = asyncio.Event()

    async def _slow_body(*_a, **_k):
        entered.set()
        await release.wait()
        return {
            "as_of": "t1",
            "enabled": True,
            "universe": ["XAUUSD_I"],
            "rows": [],
            "noc_rows": [],
            "ranked": [],
            "best": None,
            "best_symbol": None,
            "eligible_count": 0,
            "eligible_symbols": [],
            "version": DEFAULT_AI_SCALPING_CONFIG.version,
            "forced_trades": False,
            "governed_by_existing_ai_and_risk": True,
        }

    scanner._store_last_scan(
        {
            "as_of": "prior",
            "enabled": True,
            "universe": ["XAUUSD_I"],
            "rows": [],
            "noc_rows": [],
            "ranked": [],
            "best": None,
            "best_symbol": None,
            "eligible_count": 0,
            "eligible_symbols": [],
        }
    )

    with patch.object(
        scanner,
        "_run_institutional_multi_asset_scan_body",
        new=AsyncMock(side_effect=_slow_body),
    ):
        first = asyncio.create_task(
            scanner.run_institutional_multi_asset_scan(mt5_adapter=object())
        )
        await entered.wait()
        second = await scanner.run_institutional_multi_asset_scan(mt5_adapter=object())
        assert second.get("overlap_skipped") is True
        release.set()
        result = await first
        assert result.get("as_of") == "t1"


@pytest.mark.unit
def test_catalogue_candidates_do_not_lead_with_invalid_bare_when_i_exists() -> None:
    rows = [{"code": "XAUUSD_I", "trade_mode": 4, "digits": 3}]
    ordered = catalogue_ordered_candidates("XAUUSD", broker_symbol_rows=rows)
    assert ordered[0] == "XAUUSD_I"


@pytest.mark.unit
def test_demoted_non_seed_stays_out_without_recovery() -> None:
    rows = [
        {"code": "XAUUSD_I", "trade_mode": 4},
        {"code": "NDXUSD", "trade_mode": 4},
        {"code": "SPXUSD", "trade_mode": 4},
    ]
    discovered = discover_from_broker_rows(rows)
    universe = build_dynamic_scalping_universe(
        discovered,
        demoted={"NDXUSD", "SPXUSD"},
        seed_recovery=set(),
        max_symbols=36,
    )
    assert "XAUUSD_I" in universe
    assert "NDXUSD" not in universe
    assert "SPXUSD" not in universe


@pytest.mark.unit
def test_record_broker_ok_clears_demotion(tmp_path: Path) -> None:
    book = SymbolStatsBook(_path=tmp_path / "ok.json", _demote_cooldown_seconds=9999)
    for _ in range(8):
        book.record_scan("XAUUSD_I", eligible=False, broker_hard_fail=True)
    assert "XAUUSD_I" in book.demoted_symbols()
    assert book.record_broker_ok("XAUUSD_I", source="test") is True
    assert "XAUUSD_I" not in book.demoted_symbols()
