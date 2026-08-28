"""Virtual replay rules for shadow research.

Lookahead is forbidden. Same-bar or earlier prints are rejected.
If SL and TP print in the same future bar, SL wins conservatively.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from app.domain.market_universe.constants import UNKNOWN
from app.domain.market_universe.lookahead import detect_lookahead_fields


def _parse_ts(value: Any) -> datetime | None:
    if value in (None, "", UNKNOWN):
        return None
    if isinstance(value, datetime):
        return value
    text = str(value).strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def conservative_exit_hit(
    *,
    direction: str,
    sl: float | None,
    tp: float | None,
    high: float | None,
    low: float | None,
) -> str | None:
    if high is None and low is None:
        return None
    hi = high if high is not None else low
    lo = low if low is not None else high
    if hi is None or lo is None:
        return None
    side = (direction or "").upper()
    if side == "BUY":
        sl_hit = sl is not None and lo <= sl
        tp_hit = tp is not None and hi >= tp
    else:
        sl_hit = sl is not None and hi >= sl
        tp_hit = tp is not None and lo <= tp
    if sl_hit and tp_hit:
        return "SL"
    if sl_hit:
        return "SL"
    if tp_hit:
        return "TP"
    return None


def evaluate_virtual_bar(
    *,
    entry_timestamp: Any,
    bar_timestamp: Any,
    direction: str,
    sl: float | None,
    tp: float | None,
    high: float | None,
    low: float | None,
    features: dict[str, Any] | None = None,
) -> dict[str, Any]:
    leaked = detect_lookahead_fields(features)
    entry_dt = _parse_ts(entry_timestamp)
    bar_dt = _parse_ts(bar_timestamp)
    if leaked:
        return {
            "status": "LOOKAHEAD_REJECTED",
            "lookahead_fields": leaked,
            "applied": False,
            "exit_reason": None,
            "would_submit_order": False,
        }
    if entry_dt is None or bar_dt is None or bar_dt <= entry_dt:
        return {
            "status": "SAME_BAR_OR_EARLIER_REJECTED",
            "applied": False,
            "exit_reason": None,
            "would_submit_order": False,
            "requires_bar_timestamp_gt_entry": True,
        }
    hit = conservative_exit_hit(
        direction=direction, sl=sl, tp=tp, high=high, low=low
    )
    return {
        "status": "OK",
        "applied": hit is not None,
        "exit_reason": hit,
        "sl_wins_when_both_hit": True,
        "would_submit_order": False,
        "ALLOW_LIVE_PROMOTION": False,
    }
