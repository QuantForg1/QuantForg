"""Sample-size governance — never promote from thin evidence."""

from __future__ import annotations

from typing import Any


def classify_sample(
    *,
    total_trades: int = 0,
    oos_trades: int = 0,
    shadow_trades: int = 0,
    live_matched: int = 0,
    regime_coverage: int = 0,
    symbol_coverage: int = 0,
    session_coverage: int = 0,
    min_total: int = 30,
    min_oos: int = 20,
    min_shadow: int = 20,
    min_live_matched: int = 20,
    min_regimes: int = 1,
    min_symbols: int = 1,
    min_sessions: int = 1,
) -> dict[str, Any]:
    counts = {
        "total_trades": int(total_trades),
        "oos_trades": int(oos_trades),
        "shadow_trades": int(shadow_trades),
        "live_matched_opportunities": int(live_matched),
        "regime_coverage": int(regime_coverage),
        "symbol_coverage": int(symbol_coverage),
        "session_coverage": int(session_coverage),
    }
    mins = {
        "min_total_trades": min_total,
        "min_oos_trades": min_oos,
        "min_shadow_trades": min_shadow,
        "min_live_matched": min_live_matched,
        "min_regimes": min_regimes,
        "min_symbols": min_symbols,
        "min_sessions": min_sessions,
    }
    checks = {
        "total": counts["total_trades"] >= min_total,
        "oos": counts["oos_trades"] >= min_oos,
        "shadow": counts["shadow_trades"] >= min_shadow,
        "live_matched": counts["live_matched_opportunities"] >= min_live_matched,
        "regimes": counts["regime_coverage"] >= min_regimes,
        "symbols": counts["symbol_coverage"] >= min_symbols,
        "sessions": counts["session_coverage"] >= min_sessions,
    }
    if not all(checks.values()):
        state = "INSUFFICIENT_SAMPLE"
    elif (
        counts["total_trades"] >= min_total * 2
        and counts["shadow_trades"] >= min_shadow * 2
    ):
        state = "STRONG_SAMPLE"
    else:
        state = "MINIMUM_SAMPLE"
    return {
        "state": state,
        "counts": counts,
        "minimums": mins,
        "checks": checks,
        "assumptions": (
            "Minimums are operational evidence floors for promotion review, "
            "not frequentist confidence claims."
        ),
        "promotable_by_sample": state != "INSUFFICIENT_SAMPLE",
    }
