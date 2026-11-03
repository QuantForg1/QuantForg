"""In-process SOE cycle activity — last evaluation truth for robot health.

Never fabricates broker P&L. Never authorizes LIVE. Process-local only;
survives within a worker lifetime and is reset on restart (honest about that).
"""

from __future__ import annotations

import threading
from datetime import UTC, datetime
from typing import Any, Literal

OperationalStatus = Literal[
    "ACTIVE_AND_EVALUATING",
    "ACTIVE_NO_VALID_SETUP",
    "SIGNAL_GENERATED",
    "BLOCKED_BY_RISK",
    "DISABLED",
    "DATA_UNAVAILABLE",
    "ERROR",
]

_LOCK = threading.Lock()
_STATE: dict[str, Any] = {
    "last_cycle_at": None,
    "last_quote_age_seconds": None,
    "last_market_data_at": None,
    "last_soe_decision": None,
    "last_soe_reasons": (),
    "last_selected_strategy_id": None,
    "last_symbol": None,
    "last_regime": None,
    "last_error": None,
    "cycles_observed": 0,
    "strategies": {},
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def record_cycle_start(
    *,
    symbol: str | None = None,
    quote_age_seconds: float | None = None,
    regime: str | None = None,
) -> None:
    with _LOCK:
        _STATE["cycles_observed"] = int(_STATE.get("cycles_observed") or 0) + 1
        _STATE["last_cycle_at"] = _now()
        _STATE["last_symbol"] = symbol
        _STATE["last_regime"] = regime
        if quote_age_seconds is not None:
            _STATE["last_quote_age_seconds"] = float(quote_age_seconds)
            _STATE["last_market_data_at"] = _now()
        _STATE["last_error"] = None


def record_strategy_evaluation(
    *,
    strategy_id: str,
    name: str,
    passed: bool,
    direction: str,
    quality: int,
    confidence: int,
    reject_reason: str | None = None,
) -> None:
    sid = str(strategy_id)
    with _LOCK:
        rows: dict[str, Any] = dict(_STATE.get("strategies") or {})
        rows[sid] = {
            "strategy_id": sid,
            "name": name,
            "last_evaluated_at": _now(),
            "passed": bool(passed),
            "direction": str(direction or "NONE").upper(),
            "quality": int(quality),
            "confidence": int(confidence),
            "reject_reason": reject_reason,
            "status": ("ACTIVE_AND_EVALUATING" if passed else "ACTIVE_NO_VALID_SETUP"),
        }
        _STATE["strategies"] = rows


def record_soe_verdict(
    *,
    decision: str,
    reasons: tuple[str, ...] | list[str] | None = None,
    selected_strategy_id: str | None = None,
    stale_data: bool = False,
    error: str | None = None,
) -> None:
    with _LOCK:
        _STATE["last_soe_decision"] = str(decision or "NO_TRADE").upper()
        _STATE["last_soe_reasons"] = tuple(reasons or ())
        _STATE["last_selected_strategy_id"] = selected_strategy_id
        if error:
            _STATE["last_error"] = str(error)[:500]
        if stale_data:
            _STATE["last_error"] = None
            rows: dict[str, Any] = dict(_STATE.get("strategies") or {})
            for sid, row in rows.items():
                updated = dict(row)
                updated["status"] = "DATA_UNAVAILABLE"
                rows[sid] = updated
            _STATE["strategies"] = rows
            return
        selected = selected_strategy_id
        if selected:
            rows = dict(_STATE.get("strategies") or {})
            if selected in rows:
                updated = dict(rows[selected])
                updated["status"] = "SIGNAL_GENERATED"
                rows[selected] = updated
                _STATE["strategies"] = rows


def record_blocked_by_risk(
    *,
    strategy_id: str | None,
    reason: str,
) -> None:
    with _LOCK:
        sid = str(strategy_id or _STATE.get("last_selected_strategy_id") or "")
        if not sid:
            return
        rows: dict[str, Any] = dict(_STATE.get("strategies") or {})
        row = dict(rows.get(sid) or {"strategy_id": sid, "name": sid})
        row["status"] = "BLOCKED_BY_RISK"
        row["reject_reason"] = str(reason)[:300]
        row["last_evaluated_at"] = row.get("last_evaluated_at") or _now()
        rows[sid] = row
        _STATE["strategies"] = rows
        _STATE["last_soe_reasons"] = (str(reason)[:300],)


def record_error(message: str) -> None:
    with _LOCK:
        _STATE["last_error"] = str(message)[:500]
        _STATE["last_cycle_at"] = _now()


def reset_cycle_activity() -> None:
    """Test/helper only — clears process-local activity."""
    with _LOCK:
        _STATE.clear()
        _STATE.update(
            {
                "last_cycle_at": None,
                "last_quote_age_seconds": None,
                "last_market_data_at": None,
                "last_soe_decision": None,
                "last_soe_reasons": (),
                "last_selected_strategy_id": None,
                "last_symbol": None,
                "last_regime": None,
                "last_error": None,
                "cycles_observed": 0,
                "strategies": {},
            }
        )


def snapshot_cycle_activity() -> dict[str, Any]:
    with _LOCK:
        return {
            "last_cycle_at": _STATE.get("last_cycle_at"),
            "last_market_data_at": _STATE.get("last_market_data_at"),
            "last_quote_age_seconds": _STATE.get("last_quote_age_seconds"),
            "last_soe_decision": _STATE.get("last_soe_decision"),
            "last_soe_reasons": list(_STATE.get("last_soe_reasons") or ()),
            "last_selected_strategy_id": _STATE.get("last_selected_strategy_id"),
            "last_symbol": _STATE.get("last_symbol"),
            "last_regime": _STATE.get("last_regime"),
            "last_error": _STATE.get("last_error"),
            "cycles_observed": int(_STATE.get("cycles_observed") or 0),
            "strategies": dict(_STATE.get("strategies") or {}),
            "process_local": True,
            "note": (
                "Timestamps are process-local. A worker restart clears this "
                "snapshot until the next evaluation cycle."
            ),
        }
