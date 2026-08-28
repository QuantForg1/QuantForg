"""SHADOW_VIRTUAL_TRADE store — isolated from live forensic / OMS.

A virtual trade is recorded only when ENTRY, SL, and TP are all known at T.
Exits use future bars only via evaluate_virtual_bar. Incomplete levels are
not invented. This ledger is never STRATEGY_MATCHED and never live PnL.
"""

from __future__ import annotations

import hashlib
import json
import threading
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    UNKNOWN,
)
from app.domain.market_universe.identity import canonical_desk
from app.domain.market_universe.virtual_replay import evaluate_virtual_bar

_LOCK = threading.Lock()
_TRADES: deque[dict[str, Any]] = deque(maxlen=2000)

LEDGER = "RESEARCH_SHADOW_ONLY"
KIND = "SHADOW_VIRTUAL_TRADE"


def reset_shadow_virtual_for_tests() -> None:
    with _LOCK:
        _TRADES.clear()


def _known(value: Any) -> bool:
    return value not in (None, "", UNKNOWN)


def _trade_id(row: dict[str, Any], as_of: str) -> str:
    identity = {
        "canonical_symbol": row.get("instrument") or row.get("canonical_symbol"),
        "direction": row.get("direction"),
        "entry": row.get("entry"),
        "SL": row.get("SL"),
        "TP": row.get("TP"),
        "features_as_of": as_of,
    }
    digest = hashlib.sha256(
        json.dumps(identity, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()[:16]
    return f"SV-{digest}"


def record_from_candidates(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Persist complete candidates as SHADOW_VIRTUAL_TRADE. Skip incomplete."""
    as_of = datetime.now(UTC).isoformat()
    added = 0
    skipped = 0
    with _LOCK:
        existing = {str(t.get("trade_id")) for t in _TRADES}
        for row in (payload or {}).get("candidates") or ():
            if not isinstance(row, dict):
                skipped += 1
                continue
            entry, sl, tp = row.get("entry"), row.get("SL"), row.get("TP")
            if not (_known(entry) and _known(sl) and _known(tp)):
                skipped += 1
                continue
            direction = str(row.get("direction") or "").upper()
            if direction not in {"BUY", "SELL"}:
                skipped += 1
                continue
            trade_id = _trade_id(row, str(row.get("features_as_of") or as_of))
            if trade_id in existing:
                continue
            desk = canonical_desk(
                str(row.get("instrument") or row.get("canonical_symbol") or "")
            )
            _TRADES.append(
                {
                    "kind": KIND,
                    "ledger": LEDGER,
                    "not": "LIVE_ORDER",
                    "not_strategy_matched": True,
                    "trade_id": trade_id,
                    "symbol": str(row.get("broker_symbol") or desk),
                    "canonical_symbol": desk,
                    "asset_class": row.get("asset_class") or UNKNOWN,
                    "timestamp": as_of,
                    "virtual_entry_timestamp": as_of,
                    "direction": direction,
                    "entry": entry,
                    "SL": sl,
                    "TP": tp,
                    "RR": row.get("RR") or UNKNOWN,
                    "setup": row.get("setup") or UNKNOWN,
                    "session": (row.get("market_conditions") or {}).get("session")
                    or UNKNOWN,
                    "regime": (row.get("market_conditions") or {}).get("regime")
                    or UNKNOWN,
                    "state": "VIRTUAL_ENTRY",
                    "exit_reason": UNKNOWN,
                    "PnL": UNKNOWN,
                    "R": UNKNOWN,
                    "MAE": UNKNOWN,
                    "MFE": UNKNOWN,
                    "hold_time": UNKNOWN,
                    "completed": False,
                    "would_submit_order": False,
                    "authorizes_trade": False,
                    "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
                    "forwarded_to_oms": False,
                    "mt5_ticket": None,
                }
            )
            existing.add(trade_id)
            added += 1
    return list_shadow_virtual(added=added, skipped=skipped)


def apply_future_bar(
    *,
    trade_id: str,
    bar_timestamp: Any,
    high: float | None,
    low: float | None,
) -> dict[str, Any]:
    """Exit only on a later bar. Same-bar rejected. SL wins if both hit."""
    with _LOCK:
        trade = next(
            (t for t in _TRADES if str(t.get("trade_id")) == str(trade_id)),
            None,
        )
        if trade is None:
            return {
                "status": "UNKNOWN",
                "applied": False,
                "would_submit_order": False,
            }
        result = evaluate_virtual_bar(
            entry_timestamp=trade.get("virtual_entry_timestamp"),
            bar_timestamp=bar_timestamp,
            direction=str(trade.get("direction") or ""),
            sl=float(trade["SL"]) if _known(trade.get("SL")) else None,
            tp=float(trade["TP"]) if _known(trade.get("TP")) else None,
            high=high,
            low=low,
        )
        if result.get("status") == "OK" and result.get("applied"):
            trade["state"] = "VIRTUAL_EXIT"
            trade["exit_reason"] = result.get("exit_reason") or UNKNOWN
            trade["completed"] = True
            trade["PnL"] = UNKNOWN
            trade["R"] = UNKNOWN
        result["would_submit_order"] = False
        result["ALLOW_LIVE_PROMOTION"] = False
        result["trade_id"] = trade_id
        return result


def list_shadow_virtual(
    *, added: int | None = None, skipped: int | None = None
) -> dict[str, Any]:
    with _LOCK:
        rows = list(_TRADES)
    completed = [r for r in rows if r.get("completed")]
    return {
        "advisory_only": True,
        "kind": KIND,
        "ledger": LEDGER,
        "not": "LIVE_FORENSIC_LEDGER",
        "n": len(rows),
        "completed_n": len(completed),
        "added": added,
        "skipped_incomplete": skipped,
        "trades": rows[-40:],
        "would_submit_order": False,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": False,
        "counted_as_strategy_matched": False,
        "hypothetical_pnl_invented": False,
    }
