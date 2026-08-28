"""Research-only position candidates. submit_order remains blocked."""

from __future__ import annotations

from typing import Any

from app.domain.market_universe.constants import ALLOW_LIVE_PROMOTION, UNKNOWN
from app.domain.market_universe.identity import canonical_desk


def _known(value: Any) -> bool:
    return value not in (None, "", UNKNOWN)


def build_position_candidates(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """A candidate requires entry + SL + TP known at analysis time.

    Incomplete levels are not invented. No MT5 ticket is created.
    """
    candidates: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for row in rows or ():
        if not isinstance(row, dict):
            continue
        entry = row.get("entry_candidate") or row.get("entry")
        sl = row.get("sl_candidate") or row.get("sl")
        tp = row.get("tp_candidate") or row.get("tp")
        desk = canonical_desk(
            str(row.get("canonical_symbol") or row.get("symbol") or "")
        )
        if not (_known(entry) and _known(sl) and _known(tp)):
            skipped.append(
                {
                    "canonical_symbol": desk,
                    "reason": "entry_sl_tp_unknown",
                    "would_submit_order": False,
                }
            )
            continue
        direction = str(row.get("direction") or "").upper()
        if direction not in {"BUY", "SELL"}:
            skipped.append(
                {
                    "canonical_symbol": desk,
                    "reason": "direction_not_buy_or_sell",
                    "would_submit_order": False,
                }
            )
            continue
        candidates.append(
            {
                "kind": "RESEARCH_POSITION_CANDIDATE",
                "instrument": desk,
                "broker_symbol": str(row.get("broker_symbol") or ""),
                "direction": direction,
                "entry": entry,
                "SL": sl,
                "TP": tp,
                "RR": row.get("RR") or row.get("rr") or UNKNOWN,
                "risk_estimate": UNKNOWN,
                "setup": row.get("setup_state") or UNKNOWN,
                "reason": row.get("blocker") or UNKNOWN,
                "confidence": row.get("confidence_state") or UNKNOWN,
                "market_conditions": {
                    "regime": (row.get("evidence") or {}).get("REGIME") or UNKNOWN,
                    "session": row.get("session") or UNKNOWN,
                    "spread": row.get("spread") or UNKNOWN,
                },
                "would_submit_order": False,
                "authorizes_trade": False,
                "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
                "forwarded_to_oms": False,
                "mt5_ticket": None,
            }
        )
    return {
        "advisory_only": True,
        "would_submit_order": False,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": False,
        "submit_order_blocked": True,
        "n": len(candidates),
        "candidates": candidates,
        "skipped": skipped,
        "n_skipped": len(skipped),
    }
