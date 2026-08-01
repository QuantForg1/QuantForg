"""Trade Investigation Console — assemble evidence for a Trade ID."""

from __future__ import annotations

from typing import Any

from app.domain.live_trading_evidence.persistence import utc_iso
from app.domain.live_trading_evidence.trade_repository import get_trade


def investigate_trade(trade_id: str) -> dict[str, Any]:
    """Given any Trade ID / ticket / validation_id, return investigation pack.

    Missing sections stay null/empty — never fabricated.
    """
    trade = get_trade(trade_id)
    if trade is None:
        return {
            "ok": False,
            "error": "not_found",
            "trade_id": trade_id,
            "as_of": utc_iso(),
            "fabricated": False,
            "note": "No archived evidence for this id",
        }

    validation_id = trade.get("validation_id")
    pipeline: list[dict[str, Any]] = []
    timeline = trade.get("timeline") if isinstance(trade.get("timeline"), list) else []
    if timeline:
        pipeline = list(timeline)

    # Enrich from PVM attempt when available
    pvm_attempt: dict[str, Any] | None = None
    if validation_id:
        try:
            from app.domain.institutional_trading.production_validation_mode import (
                recorder as pvm_recorder,
            )

            get_production_validation_recorder = (
                pvm_recorder.get_production_validation_recorder
            )

            attempt = get_production_validation_recorder().get(str(validation_id))
            if attempt is not None and hasattr(attempt, "to_dict"):
                pvm_attempt = attempt.to_dict()
            elif isinstance(attempt, dict):
                pvm_attempt = attempt
            if pvm_attempt and not pipeline:
                stages = pvm_attempt.get("stages") or pvm_attempt.get("timeline") or []
                if isinstance(stages, list):
                    pipeline = [s for s in stages if isinstance(s, dict)]
        except Exception:
            pvm_attempt = None

    # Live execution explain (observe) — best effort by validation/signal
    live_explain: dict[str, Any] | None = None
    try:
        from app.application.services import live_execution_explain as lee

        builder = getattr(lee, "build_live_execution_explain", None) or getattr(
            lee, "build_explain", None
        )
        if callable(builder):
            live_explain = builder()
            if isinstance(live_explain, dict):
                # Keep only if related
                explain_id = str(
                    live_explain.get("validation_id")
                    or live_explain.get("trace_id")
                    or ""
                )
                if validation_id and explain_id and explain_id != str(validation_id):
                    # Still surface as latest explain context
                    live_explain = {
                        "latest_explain": live_explain,
                        "related": False,
                        "observe_only": True,
                    }
    except Exception:
        live_explain = None

    # Replay lab reference — observe inventory only
    replay: dict[str, Any] = {
        "available": False,
        "note": "Replay Evidence Lab is separate observe surface",
        "href": "/replay-evidence-lab",
    }
    try:
        from app.domain.replay_evidence_lab.evidence_store import get_evidence_database

        inv = get_evidence_database().inventory()
        replay = {
            "available": True,
            "inventory": inv,
            "href": "/replay-evidence-lab",
            "observe_only": True,
        }
    except Exception:  # noqa: S110
        pass

    ai = trade.get("ai") if isinstance(trade.get("ai"), dict) else {}
    risk = trade.get("risk") if isinstance(trade.get("risk"), dict) else {}
    oms = trade.get("oms") if isinstance(trade.get("oms"), dict) else {}
    broker = trade.get("broker") if isinstance(trade.get("broker"), dict) else {}
    management = (
        trade.get("management_events")
        if isinstance(trade.get("management_events"), list)
        else []
    )

    return {
        "ok": True,
        "as_of": utc_iso(),
        "trade_id": trade.get("trade_id"),
        "trade": trade,
        "pipeline": pipeline,
        "execution_timeline": timeline or pipeline,
        "ai_explanation": {
            "decision": ai.get("decision") or trade.get("direction"),
            "quality": ai.get("quality_score") or trade.get("quality"),
            "confidence": ai.get("confidence") or trade.get("confidence"),
            "reasons": ai.get("reasons") or [],
            "session": ai.get("session") or trade.get("session"),
            "fabricated": False,
        },
        "risk_explanation": {
            "risk_score": risk.get("risk_score") or trade.get("risk_pct"),
            "rr": risk.get("rr"),
            "position_size": risk.get("position_size") or trade.get("lot"),
            "eligibility_result": risk.get("eligibility_result"),
            "fabricated": False,
        },
        "oms_events": oms,
        "broker_response": broker,
        "management_events": management,
        "pvm_attempt": pvm_attempt,
        "live_execution_explain": live_explain,
        "replay": replay,
        "fabricated": False,
        "observe_only": True,
    }
