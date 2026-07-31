"""Adaptive Replay Explain (AI v8) — evidence-only success/failure narrative."""

from __future__ import annotations

from typing import Any


def explain_trade_replay(raw: dict[str, Any] | Any) -> dict[str, Any]:
    """Explain WHY succeeded/failed using only recorded artefacts — no hallucination."""
    if hasattr(raw, "to_dict"):
        item = raw.to_dict()
    elif isinstance(raw, dict):
        item = dict(raw)
    else:
        item = {}

    market = (
        item.get("market_snapshot")
        if isinstance(item.get("market_snapshot"), dict)
        else {}
    )
    inst = (
        market.get("institutional")
        if isinstance(market.get("institutional"), dict)
        else {}
    )
    timeline = item.get("management_timeline") or item.get("frames") or []
    if not isinstance(timeline, list):
        timeline = []

    entry = item.get("entry")
    exit_px = item.get("exit")
    direction = str(item.get("direction") or "").upper()
    pnl_hint = None
    try:
        if entry is not None and exit_px is not None:
            e = float(entry)
            x = float(exit_px)
            if "BUY" in direction or direction in {"LONG", "0"}:
                pnl_hint = x - e
            elif "SELL" in direction or direction in {"SHORT", "1"}:
                pnl_hint = e - x
    except Exception:
        pnl_hint = None

    succeeded = pnl_hint is not None and pnl_hint > 0
    failed = pnl_hint is not None and pnl_hint < 0

    why_success: list[str] = []
    why_failed: list[str] = []
    exceptional: list[str] = []
    reduced_expectancy: list[str] = []

    ai = str(item.get("ai_decision") or inst.get("ai_decision") or "")
    if ai:
        (why_success if succeeded else why_failed if failed else exceptional).append(
            f"AI decision recorded: {ai[:160]}"
        )

    close_reason = item.get("close_reason") or inst.get("close_reason")
    if close_reason:
        bucket = why_success if succeeded else why_failed if failed else exceptional
        bucket.append(f"Close reason: {close_reason}")

    exec_dec = inst.get("execution_decision")
    if isinstance(exec_dec, dict):
        score = exec_dec.get("execution_quality_score")
        rec = exec_dec.get("recommendation")
        if score is not None:
            if int(score) >= 70 and succeeded:
                exceptional.append(f"Execution moment score {score} (favorable)")
            elif int(score) < 50:
                reduced_expectancy.append(
                    f"Execution moment score {score} (suboptimal microstructure)"
                )
        if rec:
            exceptional.append(f"Optimizer recommendation was {rec}")

    sor = inst.get("smart_order_routing")
    if isinstance(sor, dict):
        slip = sor.get("expected_slippage")
        if slip is not None:
                try:
                    if abs(float(slip)) >= 0.2:
                        reduced_expectancy.append(f"Elevated expected slippage {slip}")
                    elif succeeded:
                        why_success.append(f"Contained expected slippage {slip}")
                except (TypeError, ValueError):
                    reduced_expectancy.append("Slippage value non-numeric in artefact")

    oms = inst.get("oms_payload") or inst.get("oms")
    if isinstance(oms, dict) and oms.get("outcome"):
        exceptional.append(f"OMS outcome: {oms.get('outcome')}")

    if isinstance(item.get("sl"), (int, float)) and entry is not None:
        exceptional.append("Stop and entry recorded in replay")

    # Evidence gaps — never invent
    if not why_success and succeeded:
        why_success.append("Positive price excursion vs entry (evidence-limited)")
    if not why_failed and failed:
        why_failed.append("Negative price excursion vs entry (evidence-limited)")
    if pnl_hint is None:
        exceptional.append("PnL not reconstructable from entry/exit alone")

    return {
        "id": item.get("id"),
        "ticket": item.get("ticket"),
        "symbol": item.get("symbol"),
        "direction": item.get("direction"),
        "succeeded": succeeded if pnl_hint is not None else None,
        "why_succeeded": why_success,
        "why_failed": why_failed,
        "what_made_exceptional": exceptional,
        "what_reduced_expectancy": reduced_expectancy,
        "evidence_only": True,
        "hallucinations": False,
        "fabricated": False,
        "source": "trade_replay_artefacts",
    }


def enrich_replay_library(items: list[Any], *, limit: int = 25) -> dict[str, Any]:
    out: list[dict[str, Any]] = []
    for raw in items[:limit]:
        try:
            from app.domain.institutional_trading.ai_scalping.institutional_replay_viewer import (  # noqa: E501
                format_institutional_replay,
            )

            base = format_institutional_replay(raw)
        except Exception:
            base = raw.to_dict() if hasattr(raw, "to_dict") else (
                dict(raw) if isinstance(raw, dict) else {}
            )
        explain = explain_trade_replay(base if isinstance(base, dict) else raw)
        merged = dict(base) if isinstance(base, dict) else {"fabricated": False}
        merged["adaptive_explain"] = explain
        out.append(merged)
    return {
        "items": out,
        "count": len(out),
        "fabricated": False,
        "observe_only": True,
    }
