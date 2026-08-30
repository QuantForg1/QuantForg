"""Phase 70 — research probe expansion + why-signal evidence propagation."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import signal_center_service
from app.application.services.market_universe_service import (
    _probe_codes,
    _probe_codes_from_rows,
)
from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    MAX_HISTORY_PROBE_SYMBOLS,
    MAX_RESEARCH_WORKERS,
)

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.unit
@pytest.mark.trading_core
def test_probe_cap_expanded_but_bounded() -> None:
    assert MAX_HISTORY_PROBE_SYMBOLS >= 32
    assert MAX_HISTORY_PROBE_SYMBOLS <= 128
    assert MAX_RESEARCH_WORKERS >= 4
    assert MAX_RESEARCH_WORKERS <= 8
    assert ALLOW_LIVE_PROMOTION is False


@pytest.mark.unit
@pytest.mark.trading_core
def test_probe_codes_rotate_across_asset_classes() -> None:
    instruments = []
    prefixes = {
        "FOREX": "FX",
        "METALS": "MT",
        "CRYPTO": "CR",
        "INDICES": "IX",
        "ENERGY": "EN",
        "STOCKS": "ST",
    }
    for asset, prefix in prefixes.items():
        for j in range(20):
            instruments.append(
                {
                    "canonical_symbol": f"{prefix}{j}",
                    "broker_symbol": f"{prefix}{j}",
                    "asset_class": asset,
                }
            )
    codes = _probe_codes(instruments)
    assert len(codes) == MAX_HISTORY_PROBE_SYMBOLS
    hit = {c[:2] for c in codes}
    assert len(hit) >= 4


@pytest.mark.unit
@pytest.mark.trading_core
def test_probe_codes_from_rows_respects_cap() -> None:
    rows = tuple(
        {"code": f"SYM{i}", "symbol": f"SYM{i}", "asset_class": "FOREX"}
        for i in range(200)
    )
    codes = _probe_codes_from_rows(rows)
    assert len(codes) <= MAX_HISTORY_PROBE_SYMBOLS
    assert len(codes) >= 1


@pytest.mark.unit
@pytest.mark.trading_core
def test_research_row_propagates_evidence_for_why_signal() -> None:
    row = signal_center_service._row_from_research_opportunity(
        {
            "symbol": "EURUSD",
            "broker_symbol": "EURUSD",
            "direction": "BUY",
            "opportunity_score": 78,
            "directional_edge": 12,
            "entry": 1.085,
            "stop_loss": 1.08,
            "take_profit": 1.09,
            "price": 1.085,
            "structure_score": 70,
            "momentum_score": 65,
            "volatility_score": 40,
            "reason": "Bullish structure with positive momentum",
            "evidence": {
                "WHY_THIS_DIRECTION": "BUY bias from core scores",
                "WHY_NOW": "Momentum confirmation",
                "REGIME": "TREND",
                "MOMENTUM": 65,
                "STRUCTURE_EVIDENCE": 70,
                "VOLATILITY": 40,
            },
        }
    )
    assert row["authorizes_trade"] is False
    assert row["pipeline"]["forwarded_to_oms"] is False
    assert isinstance(row["evidence"], dict)
    assert row["evidence"]["WHY_THIS_DIRECTION"] == "BUY bias from core scores"
    assert row["structure_score"] == 70
    assert row["reasoning"] == "Bullish structure with positive momentum"


@pytest.mark.unit
@pytest.mark.trading_core
def test_admin_not_in_trader_nav_config() -> None:
    nav = (
        ROOT
        / "frontend"
        / "src"
        / "components"
        / "layout"
        / "nav-config.ts"
    ).read_text(encoding="utf-8")
    assert "OPERATOR_RAIL_ORDER = TRADER_DESK_ORDER" in nav
    assert "never shown here" in nav.lower() or "never lists Admin" in nav or "never surfaces" in nav.lower()
