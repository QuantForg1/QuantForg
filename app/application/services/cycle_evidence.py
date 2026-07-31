"""Durable per-cycle execution evidence + structured rejection logging.

Every ITE scan cycle appends one JSONL row (outcome, reasons, sizing).
Rejected trades always log the exact rejection reason. Special handling for
below_min_lot includes calculated lot, broker minimum, balance, and risk%.

Never forces trades. Never lowers quality / risk thresholds.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.Lock()
_PATH: Path | None = None


def _evidence_path() -> Path:
    global _PATH
    if _PATH is not None:
        return _PATH
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    _PATH = base / "ite_cycle_evidence.jsonl"
    return _PATH


def reset_cycle_evidence_path_for_tests(path: Path | None = None) -> None:
    """Test helper — redirect or clear the evidence path."""
    global _PATH
    _PATH = path


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    return str(value)


def log_trade_rejection(
    *,
    reasons: list[str] | tuple[str, ...] | str,
    stage: str,
    code: str | None = None,
    symbol: str | None = None,
    session: str | None = None,
    trace_id: str | None = None,
    sizing: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Log every rejected trade with the exact rejection reason(s)."""
    if isinstance(reasons, str):
        reason_list = [reasons] if reasons.strip() else []
    else:
        reason_list = [str(r) for r in reasons if str(r).strip()]
    if not reason_list:
        reason_list = [code or "unknown_rejection"]
    primary = reason_list[0]
    payload: dict[str, Any] = {
        "event": "trade_rejected",
        "stage": stage,
        "code": code or _infer_code(primary),
        "reason": primary,
        "reasons": reason_list,
        "symbol": symbol,
        "session": session,
        "trace_id": trace_id,
    }
    if sizing:
        payload["sizing"] = _jsonable(sizing)
        if str(payload.get("code") or "").lower() == "below_min_lot" or any(
            "below_min_lot" in str(r).lower() or "below broker min" in str(r).lower()
            for r in reason_list
        ):
            payload["below_min_lot"] = {
                "calculated_lot": sizing.get("calculated_lot")
                or sizing.get("raw_lots")
                or sizing.get("lots"),
                "broker_minimum": sizing.get("broker_minimum")
                or sizing.get("broker_min_lot")
                or sizing.get("min_lot"),
                "account_balance": sizing.get("account_balance")
                or sizing.get("equity")
                or sizing.get("balance"),
                "risk_percentage": sizing.get("risk_percentage")
                or sizing.get("risk_pct"),
            }
            logger.warning(
                "Rejected because: below_min_lot",
                calculated_lot=payload["below_min_lot"]["calculated_lot"],
                broker_minimum=payload["below_min_lot"]["broker_minimum"],
                account_balance=payload["below_min_lot"]["account_balance"],
                risk_percentage=payload["below_min_lot"]["risk_percentage"],
                reasons=reason_list,
                stage=stage,
                symbol=symbol,
                session=session,
                trace_id=trace_id,
            )
            if extra:
                payload.update(_jsonable(extra))
            return
    if extra:
        payload.update(_jsonable(extra))
    logger.warning(
        "Rejected because: %s",
        primary,
        **{k: v for k, v in payload.items() if k not in {"event", "reason"}},
    )


def _infer_code(reason: str) -> str:
    low = reason.lower()
    if "below_min_lot" in low or "below broker min" in low:
        return "below_min_lot"
    if "session" in low and ("off_hours" in low or "weekend" in low or "closed" in low):
        return "market_window_closed"
    if "session" in low:
        return "session_gate"
    if "spread" in low:
        return "spread_reject"
    if "news" in low:
        return "news_blackout"
    if "quality" in low:
        return "quality_below_threshold"
    if "confluence" in low or "confidence" in low:
        return "confidence_below_threshold"
    if "safety" in low:
        return "safety_blocked"
    return "rejected"


def record_cycle_evidence(
    *,
    cycle_outcome: str,
    decision_action: str | None = None,
    reasons: list[str] | tuple[str, ...] | None = None,
    abort_reason: str | None = None,
    symbol: str | None = None,
    session: str | None = None,
    session_stars: int | None = None,
    quality_score: int | None = None,
    confluence_score: int | None = None,
    forwarded_to_oms: bool = False,
    trace_id: str | None = None,
    sizing: dict[str, Any] | None = None,
    diagnostics: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one durable evidence row for every autonomous scan cycle."""
    reason_list = [str(r) for r in (reasons or ()) if str(r).strip()]
    if abort_reason and abort_reason not in reason_list:
        reason_list.insert(0, str(abort_reason))
    action_u = str(decision_action or "NO_TRADE").upper()
    rejected = (not forwarded_to_oms) and action_u in {
        "NO_TRADE",
        "WATCH",
        "",
    }
    row: dict[str, Any] = {
        "recorded_at": datetime.now(UTC).isoformat(),
        "cycle_outcome": cycle_outcome,
        "decision_action": decision_action or "NO_TRADE",
        "rejected": rejected,
        "forwarded_to_oms": bool(forwarded_to_oms),
        "reasons": reason_list,
        "primary_reason": reason_list[0] if reason_list else None,
        "symbol": symbol,
        "session": session,
        "session_stars": session_stars,
        "quality_score": quality_score,
        "confluence_score": confluence_score,
        "trace_id": trace_id,
        "sizing": _jsonable(sizing) if sizing else None,
        "autonomous": True,
        "forced_trade": False,
        "quality_thresholds_reduced": False,
    }
    if diagnostics:
        # Keep payload bounded — store only scalar-ish keys
        slim = {
            k: _jsonable(diagnostics[k])
            for k in (
                "equity",
                "risk_pct",
                "raw_lots",
                "calculated_lots",
                "broker_min_lot",
                "broker_lot_step",
                "sizing_status",
                "trading_session",
                "session_allowed",
                "spread",
                "atr",
            )
            if k in diagnostics
        }
        if slim:
            row["market_context"] = slim
    if extra:
        row["extra"] = _jsonable(extra)

    path = _evidence_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK, path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, default=str) + "\n")
    except Exception:
        logger.exception("cycle_evidence_append_failed", path=str(path))

    if rejected and reason_list:
        log_trade_rejection(
            reasons=reason_list,
            stage=cycle_outcome or "cycle",
            symbol=symbol,
            session=session,
            trace_id=trace_id,
            sizing=sizing,
        )
    else:
        logger.info(
            "cycle_evidence_recorded",
            outcome=cycle_outcome,
            action=row["decision_action"],
            forwarded_to_oms=forwarded_to_oms,
            trace_id=trace_id,
            path=str(path),
        )
    return row
