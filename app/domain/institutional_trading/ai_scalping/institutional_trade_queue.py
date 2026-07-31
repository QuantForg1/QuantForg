"""Institutional Trade Queue — durable ranked candidates from live scans.

Only one eligible opportunity may reach Risk. No duplicate execution.
If the best disappears, peek_next_eligible() returns the next ranked candidate.
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.institutional_trading.ai_scalping.execution_probability import (
    estimate_execution_probability,
)
from app.domain.institutional_trading.ai_scalping.opportunity_ranking import (
    compute_opportunity_score,
    enrich_scores_with_opportunity,
)

_LOCK = threading.RLock()
_QUEUE: list[dict[str, Any]] = []
_AS_OF: str | None = None
_SELECTED: str | None = None
_TTL_SECONDS = 180


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(dt: datetime | None = None) -> str:
    return (dt or _now()).isoformat().replace("+00:00", "Z")


def rebuild_trade_queue(
    scored: list[dict[str, Any]],
    *,
    ttl_seconds: int = _TTL_SECONDS,
) -> dict[str, Any]:
    """Rebuild queue from latest multi-asset scan scores."""
    global _QUEUE, _AS_OF, _SELECTED
    enriched = enrich_scores_with_opportunity(scored)
    rows: list[dict[str, Any]] = []
    for row in enriched:
        opp = compute_opportunity_score(row)
        prob = estimate_execution_probability(row)
        rows.append(
            {
                "symbol": str(row.get("symbol") or "").upper(),
                "direction": str(row.get("direction") or "NONE").upper(),
                "score": opp["opportunity_score"],
                "opportunity_score": opp["opportunity_score"],
                "quality": int(row.get("trade_quality") or row.get("quality") or 0),
                "confidence": int(
                    row.get("ai_confidence") or row.get("confidence") or 0
                ),
                "blocking_gate": row.get("reject_reason")
                or row.get("blocking_gate")
                or None,
                "timestamp": _iso(),
                "estimated_probability": prob["probability_of_success"],
                "probability": prob,
                "eligible": bool(opp.get("eligible")),
                "reject": bool(row.get("reject")),
                "expected_rr": row.get("expected_rr"),
                "ttl_seconds": ttl_seconds,
            }
        )
    rows.sort(
        key=lambda r: (
            0 if r.get("eligible") else 1,
            -int(r.get("score") or 0),
            -int(r.get("confidence") or 0),
            str(r.get("symbol") or ""),
        )
    )
    with _LOCK:
        _QUEUE = rows
        _AS_OF = _iso()
        _SELECTED = None
    return snapshot_trade_queue()


def snapshot_trade_queue() -> dict[str, Any]:
    with _LOCK:
        return {
            "as_of": _AS_OF,
            "size": len(_QUEUE),
            "selected_symbol": _SELECTED,
            "candidates": [dict(r) for r in _QUEUE],
            "eligible_count": sum(1 for r in _QUEUE if r.get("eligible")),
            "observe_only": False,
            "one_to_risk_only": True,
            "forced_trades": False,
        }


def peek_next_eligible(
    *,
    exclude_symbols: set[str] | None = None,
) -> dict[str, Any] | None:
    """Return next eligible candidate (best first). Does not mark selected."""
    exclude = {s.upper() for s in (exclude_symbols or set())}
    cutoff = _now() - timedelta(seconds=_TTL_SECONDS)
    with _LOCK:
        for row in _QUEUE:
            if not row.get("eligible"):
                continue
            sym = str(row.get("symbol") or "").upper()
            if sym in exclude:
                continue
            ts = str(row.get("timestamp") or "")
            try:
                when = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                if when < cutoff:
                    continue
            except Exception:
                pass
            return dict(row)
    return None


def select_for_risk(symbol: str | None = None) -> dict[str, Any] | None:
    """Mark one eligible symbol as selected for the Risk handoff (single-flight)."""
    global _SELECTED
    with _LOCK:
        if _SELECTED and symbol and symbol.upper() != _SELECTED:
            # Another symbol already selected this scan window
            return None
        cand = None
        if symbol:
            want = symbol.upper()
            for row in _QUEUE:
                if row.get("eligible") and str(row.get("symbol") or "").upper() == want:
                    cand = dict(row)
                    break
        else:
            for row in _QUEUE:
                if row.get("eligible"):
                    cand = dict(row)
                    break
        if cand is None:
            return None
        _SELECTED = str(cand["symbol"]).upper()
        cand["selected"] = True
        return cand


def clear_selection() -> None:
    global _SELECTED
    with _LOCK:
        _SELECTED = None
