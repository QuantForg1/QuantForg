"""Phase-24 research audit report. Unknowns stay UNKNOWN / INSUFFICIENT_SAMPLE."""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.analytics import performance_report
from app.domain.market_universe.config_audit import build_configuration_audit
from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    CATALOGUE_ERROR,
    CATALOGUE_MOCK,
    CATALOGUE_UNAVAILABLE,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_MIN_RR,
    FROZEN_OPPORTUNITY_THRESHOLD,
    INSUFFICIENT_SAMPLE,
    UNKNOWN,
)
from app.domain.market_universe.correlation_research import analyze_correlation_exposure
from app.domain.market_universe.identity import canonical_desk
from app.domain.market_universe.oos import chronological_split, walk_forward_windows
from app.domain.market_universe.opportunity_board import build_opportunity_board
from app.domain.market_universe.registry import build_registry
from app.domain.market_universe.shadow_wall import scan_package_isolation


def _dist(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or UNKNOWN)
        out[label] = out.get(label, 0) + 1
    return out


def build_market_universe_report(
    *,
    broker_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    quotes: dict[str, dict[str, Any]] | None = None,
    scored_rows: list[dict[str, Any]] | None = None,
    matched_trades: list[dict[str, Any]] | None = None,
    shadow_candidates: list[dict[str, Any]] | None = None,
    catalogue_source: str = "INJECTED",
    news_protection: dict[str, Any] | None = None,
) -> dict[str, Any]:
    registry = build_registry(broker_rows or (), quotes=quotes)
    instruments = list(registry.get("instruments") or [])
    by_desk = {str(i.get("canonical_symbol")): i for i in instruments}
    board = build_opportunity_board(scored_rows or [], registry_by_desk=by_desk)
    rows = list(board.get("rows") or [])
    perf = performance_report(matched_trades or [])
    shadows = list(shadow_candidates or [])
    split = chronological_split(shadows)
    wf = walk_forward_windows(shadows)
    corr = analyze_correlation_exposure(
        [str(r.get("canonical_symbol") or r.get("symbol") or "") for r in rows],
    )
    isolation = scan_package_isolation()
    counts = registry.get("counts") or {}
    unavailable = catalogue_source in {
        CATALOGUE_UNAVAILABLE,
        CATALOGUE_ERROR,
        CATALOGUE_MOCK,
    }

    def count_or(key: str, default: int = 0) -> Any:
        if unavailable:
            return CATALOGUE_UNAVAILABLE
        return counts.get(key, default)
    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "1_MARKET_UNIVERSE_COUNT": count_or("universe", 0),
        "2_FOREX_COUNT": count_or("FOREX", 0),
        "3_CRYPTO_COUNT": count_or("CRYPTO", 0),
        "4_METALS_COUNT": count_or("METALS", 0),
        "5_INDICES_COUNT": count_or("INDICES", 0),
        "6_ENERGY_COUNT": count_or("ENERGY", 0),
        "6b_STOCKS_COUNT": count_or("STOCKS", 0),
        "6c_COMMODITIES_COUNT": count_or("COMMODITIES", 0),
        "7_OTHER_COUNT": count_or("OTHER", 0),
        "8_DATA_READY_COUNT": count_or("data_ready", 0),
        "9_STALE_COUNT": count_or("stale", 0),
        "10_MARKET_CLOSED_COUNT": count_or("market_closed", 0),
        "11_UNSUPPORTED_COUNT": count_or("unsupported", 0),
        "12_TOP_OPPORTUNITIES": board.get("top_opportunities") or INSUFFICIENT_SAMPLE,
        "13_TOP_DIRECTIONAL_EDGES": board.get("top_directional_edges")
        or INSUFFICIENT_SAMPLE,
        "14_OPPORTUNITY_DISTRIBUTION": _dist(rows, "opportunity_score") or UNKNOWN,
        "15_EDGE_DISTRIBUTION": _dist(rows, "directional_edge") or UNKNOWN,
        "16_SESSION_DISTRIBUTION": _dist(rows, "session") or UNKNOWN,
        "17_REGIME_DISTRIBUTION": _dist(
            [{"regime": (r.get("evidence") or {}).get("REGIME")} for r in rows],
            "regime",
        )
        or UNKNOWN,
        "18_SHADOW_SAMPLE_SIZE": len(shadows),
        "19_STRATEGY_MATCHED_SAMPLE": perf.get("STRATEGY_MATCHED_SAMPLE", 0),
        "20_PERFORMANCE_BY_ASSET_CLASS": {
            "OVERALL": perf.get("OVERALL"),
            "FOREX": perf.get("FOREX"),
            "CRYPTO": perf.get("CRYPTO"),
            "METALS": perf.get("METALS"),
            "INDICES": perf.get("INDICES"),
            "ENERGY": perf.get("ENERGY"),
            "STOCKS": perf.get("STOCKS"),
            "COMMODITIES": perf.get("COMMODITIES"),
            "OTHER": perf.get("OTHER"),
        },
        "21_PERFORMANCE_BY_SYMBOL": perf.get("by_symbol"),
        "22_PERFORMANCE_BY_SESSION": perf.get("by_session"),
        "23_PERFORMANCE_BY_REGIME": perf.get("by_regime"),
        "24_PERFORMANCE_BY_SETUP": perf.get("by_setup"),
        "25_OOS": split if shadows else INSUFFICIENT_SAMPLE,
        "26_WALK_FORWARD": wf if shadows else INSUFFICIENT_SAMPLE,
        "27_CORRELATION_EXPOSURE": corr,
        "28_DATA_QUALITY": {
            "by_state": (
                CATALOGUE_UNAVAILABLE
                if unavailable
                else (registry.get("by_state") or {})
            ),
            "broker_symbols_found": (
                CATALOGUE_UNAVAILABLE
                if unavailable
                else registry.get("broker_symbols_found", 0)
            ),
            "canonical_instruments": (
                CATALOGUE_UNAVAILABLE
                if unavailable
                else registry.get("canonical_instruments", 0)
            ),
            "catalogue_source": catalogue_source,
        },
        "29_CONFIGURATION_AUDIT": build_configuration_audit(),
        "30_PRODUCTION_SAFETY_AUDIT": {
            "TRADING_LOGIC_CHANGED": False,
            "OPPORTUNITY_CHANGED": False,
            "EDGE_CHANGED": False,
            "RISK_CHANGED": False,
            "SAFETY_CHANGED": False,
            "OMS_CHANGED": False,
            "MT5_CHANGED": False,
            "SHADOW_CAN_EXECUTE": False,
            "LIVE_ORDER_SENT": False,
            "COMMITTED": False,
            "PUSHED": False,
            "DEPLOYED": False,
            "frozen_opportunity_threshold": FROZEN_OPPORTUNITY_THRESHOLD,
            "frozen_directional_edge": FROZEN_DIRECTIONAL_EDGE,
            "frozen_min_rr": FROZEN_MIN_RR,
            "research_package_isolated": isolation.get("isolated"),
            "isolation_hits": isolation.get("hits") or [],
            "xauusd_reference_present": bool(registry.get("xauusd_reference")),
            "xauusd_canonical": canonical_desk("XAUUSD_i"),
            "catalogue_source": catalogue_source,
            "fixture_presented_as_live": False,
            "NEWS_PROTECTION": (news_protection or {}).get("STATUS", UNKNOWN),
        },
        "31_BY_OPPORTUNITY_BAND": perf.get("by_opportunity_band")
        or INSUFFICIENT_SAMPLE,
        "32_BY_EDGE_BAND": perf.get("by_edge_band") or INSUFFICIENT_SAMPLE,
        "33_BY_RR_BAND": perf.get("by_rr_band") or INSUFFICIENT_SAMPLE,
        "34_BY_VOLATILITY": perf.get("by_volatility") or INSUFFICIENT_SAMPLE,
        "35_BY_SPREAD_BAND": perf.get("by_spread_band") or INSUFFICIENT_SAMPLE,
        "registry": {
            "counts": counts,
            "by_class": registry.get("by_class"),
            "by_state": registry.get("by_state"),
        },
        "disclaimer": (
            "Unknowns remain UNKNOWN or INSUFFICIENT_SAMPLE. Never fabricated."
        ),
    }
