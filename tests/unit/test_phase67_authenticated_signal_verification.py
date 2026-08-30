"""Phase 67 — authenticated signal verification contracts + merge fix.

Locks research-batch merge so UNKNOWN stubs cannot block re-analysis.
Does not invent production LIVE_BROKER results.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.application.services.market_universe_service import (
    _merge_research_batch_scores,
    _row_has_numeric_opportunity,
)
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION


@pytest.mark.unit
def test_row_has_numeric_opportunity() -> None:
    assert _row_has_numeric_opportunity({"opportunity_score": 73}) is True
    assert _row_has_numeric_opportunity({"opportunity_score": 73.5}) is True
    assert _row_has_numeric_opportunity({"opportunity_score": "UNKNOWN"}) is False
    assert _row_has_numeric_opportunity({"opportunity_score": None}) is False
    assert _row_has_numeric_opportunity({"direction": "WAIT"}) is False


@pytest.mark.unit
def test_merge_rescores_unknown_stubs_not_treated_as_already_scored() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    scored = [
        {
            "symbol": "XAUUSD",
            "opportunity_score": 73,
            "direction": "SELL",
        },
        {
            "symbol": "BTCUSD",
            "opportunity_score": "UNKNOWN",
            "direction": "WAIT",
        },
        {
            "symbol": "EURUSD",
            "direction": "WAIT",
        },
    ]
    schedule = {
        "queue": [
            {"canonical_symbol": "XAUUSD", "broker_symbol": "XAUUSD"},
            {"canonical_symbol": "BTCUSD", "broker_symbol": "BTCUSD"},
            {"canonical_symbol": "EURUSD", "broker_symbol": "EURUSD"},
        ]
    }
    batch = {
        "rows": [
            {
                "symbol": "BTCUSD",
                "opportunity_score": 71,
                "directional_edge": 6,
                "direction": "BUY",
                "authorizes_trade": False,
                "forwarded_to_oms": False,
            },
            {
                "symbol": "EURUSD",
                "opportunity_score": 72,
                "directional_edge": 7,
                "direction": "SELL",
                "authorizes_trade": False,
                "forwarded_to_oms": False,
            },
        ]
    }
    with patch(
        "app.application.services.research_universe_scanner.score_symbols_for_research",
        return_value=batch,
    ) as scored_fn:
        merged = _merge_research_batch_scores(
            scored,
            mt5_adapter=object(),
            catalogue_source="LIVE_BROKER",
            schedule=schedule,
        )
    # XAUUSD already numeric — must not be re-requested.
    called_symbols = scored_fn.call_args.args[1]
    assert "XAUUSD" not in called_symbols
    assert "BTCUSD" in called_symbols
    assert "EURUSD" in called_symbols
    by_sym = {str(r.get("symbol")): r for r in merged}
    assert by_sym["XAUUSD"]["opportunity_score"] == 73
    assert by_sym["BTCUSD"]["opportunity_score"] == 71
    assert by_sym["EURUSD"]["opportunity_score"] == 72
    assert by_sym["BTCUSD"]["authorizes_trade"] is False
    assert by_sym["EURUSD"]["forwarded_to_oms"] is False


@pytest.mark.unit
def test_merge_skips_when_catalogue_not_live() -> None:
    scored = [{"symbol": "EURUSD", "direction": "WAIT"}]
    out = _merge_research_batch_scores(
        scored,
        mt5_adapter=object(),
        catalogue_source="UNAVAILABLE",
        schedule={
            "queue": [
                {"canonical_symbol": "EURUSD", "broker_symbol": "EURUSD"},
            ]
        },
    )
    assert out == scored
