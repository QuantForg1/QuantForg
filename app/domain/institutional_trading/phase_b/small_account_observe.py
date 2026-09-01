"""Small-account protection observability — does not change risk ceilings."""

from __future__ import annotations

from typing import Any


def observe_small_account_xau_block(
    *,
    equity: float | None,
    symbol: str,
    min_lot_risk_pct: float | None = None,
    hard_max_risk_pct: float = 80.0,
    blocked_by_min_lot: bool = False,
    block_reason: str | None = None,
) -> dict[str, Any]:
    """Surface why XAU may be blocked on ~$100 equity without forcing size."""
    sym = str(symbol or "").upper()
    is_xau = "XAU" in sym or sym in {"GOLD", "XAUUSD_I", "XAUUSDI"}
    eq = float(equity) if equity is not None else None
    approx_small = eq is not None and eq <= 150.0
    why = block_reason
    if blocked_by_min_lot and not why:
        why = "MIN_LOT_RISK_EXCEEDS_HARD_CEILING"
    if (
        is_xau
        and approx_small
        and min_lot_risk_pct is not None
        and min_lot_risk_pct > hard_max_risk_pct
    ):
        why = why or "XAU_MIN_LOT_TOO_LARGE_FOR_EQUITY"
    return {
        "equity": eq,
        "symbol": sym,
        "approx_100_equity": approx_small,
        "xau_candidate": is_xau,
        "min_lot_risk_pct": min_lot_risk_pct,
        "hard_max_risk_pct": hard_max_risk_pct,
        "blocked": bool(blocked_by_min_lot or why),
        "why_blocked": why,
        "continue_ranking_other_symbols": True,
        "force_trade": False,
        "risk_ceiling_preserved": True,
    }
