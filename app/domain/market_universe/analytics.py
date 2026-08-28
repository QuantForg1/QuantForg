"""Per-asset research analytics. Every metric includes n.

Never displays a win rate without n. Never uses unmatched broker
activity as strategy PnL.
"""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.classification import classify_or_unknown
from app.domain.market_universe.constants import UNKNOWN
from app.domain.market_universe.honesty import DISCLAIMER, _metrics, sample_status
from app.domain.market_universe.identity import canonical_desk
from app.domain.market_universe.opportunity_tiers import opportunity_band_label

ASSET_KEYS = ("OVERALL", "FOREX", "CRYPTO", "METALS", "INDICES", "ENERGY", "OTHER")


def _matched_only(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for row in trades:
        kind = str(row.get("match_class") or row.get("classification") or "").upper()
        if kind != "STRATEGY_MATCHED":
            continue
        out.append(row)
    return out


def _group_key(trade: dict[str, Any], dimension: str) -> str:
    if dimension == "asset_class":
        return str(
            trade.get("asset_class")
            or classify_or_unknown(
                str(trade.get("canonical_symbol") or trade.get("symbol") or "")
            )
        ).upper()
    if dimension == "symbol":
        return (
            canonical_desk(
                str(trade.get("canonical_symbol") or trade.get("symbol") or "")
            )
            or UNKNOWN
        )
    if dimension == "session":
        return str(
            trade.get("session") or trade.get("market_session") or UNKNOWN
        ).upper()
    if dimension == "regime":
        return str(trade.get("regime") or trade.get("market_regime") or UNKNOWN).upper()
    if dimension == "setup":
        return str(trade.get("setup") or trade.get("setup_state") or UNKNOWN).upper()
    if dimension == "direction":
        return str(trade.get("direction") or trade.get("side") or UNKNOWN).upper()
    if dimension == "opportunity_band":
        return opportunity_band_label(
            trade.get("opportunity") or trade.get("opportunity_score")
        )
    if dimension == "edge_band":
        edge = trade.get("edge") or trade.get("directional_edge")
        if edge in (None, "", UNKNOWN):
            return UNKNOWN
        try:
            n = int(float(edge))
        except (TypeError, ValueError):
            return UNKNOWN
        if n >= 15:
            return "15+"
        if n >= 10:
            return "10-14"
        if n >= 5:
            return "5-9"
        return "<5"
    if dimension == "rr_band":
        rr = trade.get("rr") or trade.get("expected_rr") or trade.get("RR")
        if rr in (None, "", UNKNOWN):
            return UNKNOWN
        try:
            n = float(rr)
        except (TypeError, ValueError):
            return UNKNOWN
        if n >= 2:
            return ">=2.0"
        if n >= 1.2:
            return "1.20-1.99"
        return "<1.20"
    if dimension == "volatility":
        return str(trade.get("volatility") or trade.get("volatility_band") or UNKNOWN)
    if dimension == "spread_band":
        spread = trade.get("spread")
        if spread in (None, "", UNKNOWN):
            return UNKNOWN
        try:
            n = float(spread)
        except (TypeError, ValueError):
            return UNKNOWN
        if n >= 5:
            return "WIDE"
        if n >= 2:
            return "MID"
        return "TIGHT"
    return UNKNOWN


def performance_slice(trades: list[dict[str, Any]]) -> dict[str, Any]:
    matched = _matched_only(trades)
    metrics = _metrics(matched)
    n = int(metrics.get("sample_size") or 0)
    wr = metrics.get("WIN_RATE")
    display = metrics.get("WIN_RATE_DISPLAY")
    if n > 0 and wr not in (None, UNKNOWN) and "n=" not in str(display):
        display = f"{wr}% (n={n})"
        metrics["WIN_RATE_DISPLAY"] = display
    metrics["sample_confidence"] = sample_status(n)
    metrics["disclaimer"] = DISCLAIMER
    metrics["matched_only"] = True
    metrics["unmatched_excluded"] = True
    return metrics


def performance_by_dimension(
    trades: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
    *,
    dimension: str,
) -> dict[str, Any]:
    rows = list(trades or [])
    buckets: dict[str, list[dict[str, Any]]] = {}
    for trade in rows:
        key = _group_key(trade, dimension) or UNKNOWN
        buckets.setdefault(key, []).append(trade)
    out = {k: performance_slice(v) for k, v in sorted(buckets.items())}
    return {
        "dimension": dimension,
        "n_groups": len(out),
        "groups": out,
        "disclaimer": DISCLAIMER,
        "matched_only": True,
    }


def performance_report(
    trades: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    rows = list(trades or [])
    by_class = performance_by_dimension(rows, dimension="asset_class")
    class_groups = by_class["groups"]
    overall = performance_slice(rows)
    per_class = {
        k: class_groups.get(k) or performance_slice([])
        for k in ASSET_KEYS
        if k != "OVERALL"
    }
    return {
        "advisory_only": True,
        "disclaimer": DISCLAIMER,
        "OVERALL": overall,
        "FOREX": per_class.get("FOREX"),
        "CRYPTO": per_class.get("CRYPTO"),
        "METALS": per_class.get("METALS"),
        "INDICES": per_class.get("INDICES"),
        "ENERGY": per_class.get("ENERGY"),
        "by_symbol": performance_by_dimension(rows, dimension="symbol"),
        "by_session": performance_by_dimension(rows, dimension="session"),
        "by_regime": performance_by_dimension(rows, dimension="regime"),
        "by_setup": performance_by_dimension(rows, dimension="setup"),
        "by_direction": performance_by_dimension(rows, dimension="direction"),
        "by_opportunity_band": performance_by_dimension(
            rows, dimension="opportunity_band"
        ),
        "by_edge_band": performance_by_dimension(rows, dimension="edge_band"),
        "by_rr_band": performance_by_dimension(rows, dimension="rr_band"),
        "by_volatility": performance_by_dimension(rows, dimension="volatility"),
        "by_spread_band": performance_by_dimension(rows, dimension="spread_band"),
        "STRATEGY_MATCHED_SAMPLE": int(overall.get("sample_size") or 0),
        "unmatched_never_in_strategy_pnl": True,
    }
