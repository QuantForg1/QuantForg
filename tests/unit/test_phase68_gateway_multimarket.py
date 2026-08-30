"""Phase 68 — gateway research I/O isolation + multi-market re-score contracts."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.application.services.market_universe_service import (
    _merge_research_batch_scores,
    _row_has_numeric_opportunity,
    get_last_research_batch_diag,
)
from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION


@pytest.mark.unit
def test_phase67_unknown_still_reenters_research() -> None:
    assert ALLOW_LIVE_PROMOTION is False
    assert _row_has_numeric_opportunity({"opportunity_score": "UNKNOWN"}) is False
    assert _row_has_numeric_opportunity({"opportunity_score": None}) is False
    assert _row_has_numeric_opportunity({"opportunity_score": 71}) is True


@pytest.mark.unit
def test_merge_requests_all_live_non_gold_unknown_stubs() -> None:
    scored = [
        {"symbol": "XAUUSD", "opportunity_score": 73, "direction": "SELL"},
        {"symbol": "BTCUSD", "opportunity_score": "UNKNOWN", "direction": "WAIT"},
        {"symbol": "ETHUSD", "opportunity_score": "UNKNOWN", "direction": "WAIT"},
        {"symbol": "EURUSD", "opportunity_score": "UNKNOWN", "direction": "WAIT"},
        {"symbol": "GBPUSD", "direction": "WAIT"},
        {"symbol": "AUDUSD", "opportunity_score": "UNKNOWN", "direction": "WAIT"},
        {"symbol": "USDJPY", "opportunity_score": "UNKNOWN", "direction": "WAIT"},
        {"symbol": "XAGUSD", "opportunity_score": "UNKNOWN", "direction": "WAIT"},
    ]
    schedule = {
        "queue": [
            {"canonical_symbol": s, "broker_symbol": s}
            for s in (
                "XAUUSD",
                "BTCUSD",
                "ETHUSD",
                "EURUSD",
                "GBPUSD",
                "AUDUSD",
                "USDJPY",
                "XAGUSD",
            )
        ]
    }
    batch = {
        "rows": [
            {
                "symbol": s,
                "opportunity_score": 60 + i,
                "direction": "WAIT",
                "authorizes_trade": False,
                "forwarded_to_oms": False,
            }
            for i, s in enumerate(
                ("BTCUSD", "ETHUSD", "EURUSD", "GBPUSD", "AUDUSD", "USDJPY", "XAGUSD")
            )
        ],
        "errors": [],
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
    called = scored_fn.call_args.args[1]
    assert "XAUUSD" not in called
    assert set(called) == {
        "BTCUSD",
        "ETHUSD",
        "EURUSD",
        "GBPUSD",
        "AUDUSD",
        "USDJPY",
        "XAGUSD",
    }
    diag = get_last_research_batch_diag()
    assert diag["symbols_attempted"] == 7
    assert diag["returned"] == 7
    assert diag["symbols_with_numeric"] == 7
    by_sym = {str(r.get("symbol")): r for r in merged}
    assert by_sym["XAUUSD"]["opportunity_score"] == 73
    assert by_sym["BTCUSD"]["opportunity_score"] == 60
    assert by_sym["EURUSD"]["opportunity_score"] == 62
    assert all(r.get("authorizes_trade") is False for r in merged if r.get("symbol") != "XAUUSD")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_research_mode_offload_uses_to_thread_not_ite_pool() -> None:
    from app.application.services import ite_cycle_market_context as mctx

    called: dict[str, int] = {"to_thread": 0, "ite_pool": 0}

    async def _fake_to_thread(fn, /, *args, **kwargs):  # type: ignore[no-untyped-def]
        called["to_thread"] += 1
        return fn(*args, **kwargs) if callable(fn) else None

    async def _fake_offload(fn, /, *args, **kwargs):  # type: ignore[no-untyped-def]
        called["ite_pool"] += 1
        return fn(*args, **kwargs) if callable(fn) else None

    def _ping() -> str:
        return "ok"

    with (
        patch("asyncio.to_thread", new=_fake_to_thread),
        patch(
            "app.application.services.blocking_io_offload.offload_blocking",
            new=_fake_offload,
        ),
    ):
        out = await mctx._offload_sync(_ping, research_io=True)
        live = await mctx._offload_sync(_ping, research_io=False)
    assert out == "ok"
    assert live == "ok"
    assert called["to_thread"] == 1
    assert called["ite_pool"] == 1


@pytest.mark.unit
def test_ensure_gateway_session_still_non_authorizing() -> None:
    from app.application.services.market_universe_service import (
        ensure_gateway_session_for_research,
    )

    client = MagicMock()
    client.is_connected = True
    adapter = MagicMock()
    adapter.client = client
    diag = ensure_gateway_session_for_research(adapter)
    assert diag["authorizes_trade"] is False
    assert diag["adopted"] is True
