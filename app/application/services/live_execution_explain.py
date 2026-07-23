"""Live Execution Explain Mode — read-only decision cards (never mutates engines).

Transforms existing strategy-diagnostics cycle artefacts into a single
operator-facing decision card:

- EXECUTE TRADE → list every gate PASS reason
- NO TRADE → show only the **first** blocking condition
- Full Decision Trace → expandable stage-by-stage PASS/FAIL

Does not modify Strategy, Thresholds, Risk, Safety, or OMS.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.trading.xauusd_specs import VOLUME_MIN

_STAGE_ORDER: tuple[str, ...] = (
    "session",
    "mtf",
    "quality",
    "confluence",
    "risk",
    "safety",
)


def _d(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _stage(
    *,
    key: str,
    label: str,
    status: str,
    detail: str,
    blocking: bool = False,
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,  # PASS | FAIL | SKIP
        "detail": detail,
        "blocking": blocking,
    }


def _evaluate_stages(cycle: dict[str, Any]) -> list[dict[str, Any]]:
    """Build ordered gate stages from a diagnostics cycle (read-only)."""
    trend = _as_dict(cycle.get("trend"))
    quality = _as_dict(cycle.get("quality"))
    confluence = _as_dict(cycle.get("confluence"))
    sizing = _as_dict(cycle.get("sizing"))
    rejection = _as_dict(cycle.get("rejection"))

    session_allowed = cycle.get("session_allowed")
    session_name = str(cycle.get("market_session") or "—")
    if session_allowed is True:
        session_stage = _stage(
            key="session",
            label="Session",
            status="PASS",
            detail="Session PASS",
        )
    elif session_allowed is False:
        session_stage = _stage(
            key="session",
            label="Session",
            status="FAIL",
            detail=f"Session FAILED ({session_name} not allowed)",
            blocking=True,
        )
    else:
        session_stage = _stage(
            key="session",
            label="Session",
            status="SKIP",
            detail="Session unknown",
        )

    aligned = trend.get("aligned")
    if aligned is True:
        mtf_stage = _stage(
            key="mtf",
            label="MTF Alignment",
            status="PASS",
            detail="MTF PASS",
        )
    elif aligned is False:
        mtf_stage = _stage(
            key="mtf",
            label="MTF Alignment",
            status="FAIL",
            detail="MTF Alignment FAILED",
            blocking=True,
        )
    else:
        mtf_stage = _stage(
            key="mtf",
            label="MTF Alignment",
            status="SKIP",
            detail="MTF Alignment unknown",
        )

    q_score = quality.get("score")
    q_req = quality.get("required")
    q_pass = quality.get("passed")
    if q_pass is True and q_score is not None and q_req is not None:
        quality_stage = _stage(
            key="quality",
            label="Quality",
            status="PASS",
            detail=f"Quality {q_score}/{q_req} PASS",
        )
    elif q_pass is False and q_score is not None and q_req is not None:
        quality_stage = _stage(
            key="quality",
            label="Quality",
            status="FAIL",
            detail=f"Quality {q_score} < {q_req}",
            blocking=True,
        )
    elif q_pass is False:
        quality_stage = _stage(
            key="quality",
            label="Quality",
            status="FAIL",
            detail="Quality FAILED",
            blocking=True,
        )
    else:
        quality_stage = _stage(
            key="quality",
            label="Quality",
            status="SKIP",
            detail="Quality unknown",
        )

    c_score = confluence.get("total")
    c_req = confluence.get("required")
    c_pass = confluence.get("passed")
    if c_pass is True and c_score is not None and c_req is not None:
        confluence_stage = _stage(
            key="confluence",
            label="Confluence",
            status="PASS",
            detail=f"Confluence {c_score}/{c_req} PASS",
        )
    elif c_pass is False and c_score is not None and c_req is not None:
        confluence_stage = _stage(
            key="confluence",
            label="Confluence",
            status="FAIL",
            detail=f"Confluence {c_score} < {c_req}",
            blocking=True,
        )
    elif c_pass is False:
        confluence_stage = _stage(
            key="confluence",
            label="Confluence",
            status="FAIL",
            detail="Confluence FAILED",
            blocking=True,
        )
    else:
        confluence_stage = _stage(
            key="confluence",
            label="Confluence",
            status="SKIP",
            detail="Confluence unknown",
        )

    lots = _d(sizing.get("approved_lots"))
    if lots is None:
        lots = _d(cycle.get("approved_lots") or cycle.get("calculated_lots"))
    lots_txt = f"{lots:.2f}" if lots is not None else "—"
    all_codes = [str(c) for c in (rejection.get("all_codes") or [])]
    risk_reason_hit = any(
        "lot" in c.lower() or "risk" in c.lower() or "size" in c.lower()
        for c in all_codes
    )
    if lots is not None and lots >= VOLUME_MIN:
        risk_stage = _stage(
            key="risk",
            label="Risk",
            status="PASS",
            detail=f"Risk PASS ({lots_txt} lots)",
        )
    elif lots is not None and lots < VOLUME_MIN:
        risk_stage = _stage(
            key="risk",
            label="Risk",
            status="FAIL",
            detail=f"Risk FAILED (approved_lots = {lots_txt})",
            blocking=True,
        )
    elif risk_reason_hit:
        risk_stage = _stage(
            key="risk",
            label="Risk",
            status="FAIL",
            detail="Risk FAILED (approved_lots = 0.00)",
            blocking=True,
        )
    else:
        # No sizing facts — treat as SKIP unless execute path requires it later
        risk_stage = _stage(
            key="risk",
            label="Risk",
            status="SKIP",
            detail="Risk not evaluated / no lot facts",
        )

    # Safety — observational only from cycle/abort/news codes
    abort = str(cycle.get("abort_reason") or "")
    outcome = str(cycle.get("cycle_outcome") or "").lower()
    safety_fail_codes = {
        "news_blackout",
        "AUTO_TRADING_BLOCKED",
        "KILL_SWITCH",
        "EXECUTION_DISABLED",
        "SAFETY_BLOCKED",
    }
    safety_blocked = any(c in all_codes for c in ("news_blackout",)) or any(
        token.lower() in abort.lower()
        for token in safety_fail_codes
        if abort
    ) or outcome in {"aborted"} and "safety" in abort.lower()
    if safety_blocked:
        detail = abort or "Safety FAILED"
        if "news_blackout" in all_codes:
            detail = "Safety FAILED (news blackout)"
        safety_stage = _stage(
            key="safety",
            label="Safety",
            status="FAIL",
            detail=detail,
            blocking=True,
        )
    else:
        safety_stage = _stage(
            key="safety",
            label="Safety",
            status="PASS",
            detail="Safety PASS",
        )

    by_key = {
        "session": session_stage,
        "mtf": mtf_stage,
        "quality": quality_stage,
        "confluence": confluence_stage,
        "risk": risk_stage,
        "safety": safety_stage,
    }
    return [by_key[k] for k in _STAGE_ORDER]


def _is_execute(cycle: dict[str, Any]) -> bool:
    action = str(cycle.get("decision_action") or "").upper()
    if action in {"BUY", "SELL"}:
        return True
    if bool(cycle.get("forwarded_to_oms")) or bool(cycle.get("executed")):
        return action not in {"NO_TRADE", "WATCH"}
    return False


def build_execution_explain(cycle: dict[str, Any]) -> dict[str, Any]:
    """Build one Live Execution Explain card from a diagnostics cycle."""
    stages = _evaluate_stages(cycle)
    execute = _is_execute(cycle)
    action = str(cycle.get("decision_action") or "").upper() or "NO_TRADE"

    first_block = next((s for s in stages if s["status"] == "FAIL"), None)

    if execute:
        # On execute, surface PASS reasons (and note any unexpected FAIL).
        reasons = [
            s["detail"]
            for s in stages
            if s["status"] == "PASS"
        ]
        verdict = "EXECUTE_TRADE"
        headline = "✅ EXECUTE TRADE"
        primary_rejection = None
        primary_rejection_detail = None
    else:
        verdict = "NO_TRADE"
        headline = "❌ NO TRADE"
        if first_block is not None:
            primary_rejection = first_block["label"]
            primary_rejection_detail = first_block["detail"]
            # Prefer concise mission-style primary lines
            if first_block["key"] == "mtf":
                primary_rejection = "MTF Alignment FAILED"
                primary_rejection_detail = "MTF Alignment FAILED"
            elif first_block["key"] == "risk":
                primary_rejection = first_block["detail"]
                primary_rejection_detail = first_block["detail"]
            elif first_block["key"] in {"quality", "confluence"}:
                primary_rejection = first_block["detail"]
                primary_rejection_detail = first_block["detail"]
            else:
                primary_rejection = first_block["detail"]
                primary_rejection_detail = first_block["detail"]
        else:
            # Fall back to diagnostics primary label
            rejection = _as_dict(cycle.get("rejection"))
            primary_rejection = (
                rejection.get("primary_label")
                or rejection.get("primary")
                or f"Action {action or 'NO_TRADE'}"
            )
            primary_rejection_detail = primary_rejection
        reasons = []

    return {
        "schema_version": "1.0.0",
        "mode": "live_execution_explain",
        "mutates_engines": False,
        "recorded_at": cycle.get("recorded_at"),
        "signal_id": cycle.get("signal_id"),
        "trace_id": cycle.get("trace_id"),
        "decision_action": action,
        "verdict": verdict,
        "headline": headline,
        "execute_trade": execute,
        "reasons": reasons,  # PASS reasons when EXECUTE
        "primary_rejection": primary_rejection,  # first block when NO_TRADE
        "primary_rejection_detail": primary_rejection_detail,
        "stages": stages,
        "full_trace_available": True,
        "thresholds": {
            "quality_required": _as_dict(cycle.get("quality")).get("required"),
            "confluence_required": _as_dict(cycle.get("confluence")).get("required"),
        },
        "lots": str(
            _as_dict(cycle.get("sizing")).get("approved_lots")
            or cycle.get("approved_lots")
            or cycle.get("calculated_lots")
            or ""
        )
        or None,
    }


def enrich_cycles_with_explain(
    cycles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Attach ``explain`` card to each diagnostics cycle (non-destructive)."""
    out: list[dict[str, Any]] = []
    for cycle in cycles:
        row = dict(cycle)
        row["explain"] = build_execution_explain(cycle)
        out.append(row)
    return out


def explain_snapshot_from_diagnostics(diagnostics: dict[str, Any]) -> dict[str, Any]:
    """Ops payload: latest + recent explain cards from strategy diagnostics."""
    cycles = list(diagnostics.get("cycles") or [])
    enriched = enrich_cycles_with_explain(cycles)
    latest = enriched[0] if enriched else None
    return {
        "schema_version": "1.0.0",
        "mode": "live_execution_explain",
        "mutates_engines": False,
        "never_modifies_strategy_thresholds_risk_safety_oms": True,
        "latest": latest.get("explain") if latest else None,
        "latest_cycle": latest,
        "evaluations": [
            {
                "recorded_at": c.get("recorded_at"),
                "signal_id": c.get("signal_id"),
                "decision_action": c.get("decision_action"),
                "explain": c.get("explain"),
            }
            for c in enriched
        ],
        "count": len(enriched),
        "thresholds": (diagnostics.get("thresholds") or {}),
        "advisory_only": True,
    }
