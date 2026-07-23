"""AQC natural language interface — operational Q&A with mandatory evidence."""

from __future__ import annotations

from typing import Any

from app.domain.ai_quant_copilot.analysis import (
    build_executive_summaries,
    build_historical_comparison,
    build_investigations,
    package_evidence,
    search_aqs_recommendations,
)


def _as_dict(v: Any) -> dict[str, Any]:
    return v if isinstance(v, dict) else {}


def _as_list(v: Any) -> list[Any]:
    return v if isinstance(v, list) else []


def answer_question(
    question: str,
    *,
    ctx: dict[str, Any],
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    q = (question or "").strip().lower()
    pack = pack or {}
    investigations = pack.get("investigations") or build_investigations(ctx)
    comparison = pack.get("comparison") or build_historical_comparison(ctx)
    summaries = pack.get("executive_summaries") or build_executive_summaries(ctx)
    explain = _as_dict(ctx.get("sources", {}).get("execution_explain"))
    regime = _as_dict(ctx.get("sources", {}).get("regime"))
    portfolio = _as_dict(ctx.get("sources", {}).get("portfolio"))
    aqs_recs = search_aqs_recommendations(ctx, limit=20)

    if not q:
        return {
            "question": question,
            **package_evidence(
                answer="Ask an operational question — e.g. why no trade, quality fail, PF change.",
                evidence=[],
                source_subsystem="aqc",
                confidence=0.0,
            ),
        }

    if ("no trade" in q or "no trades" in q or "why was no trade" in q) or (
        "blocked" in q and "execution" in q
    ):
        blocked = [
            inv
            for inv in investigations
            if str(inv.get("final_decision") or "").upper()
            in {"BLOCKED", "CANCELLED", "FAIL", "REJECTED"}
            or inv.get("first_block")
        ]
        top = blocked[:3] or investigations[:3]
        reason = "No blocking evidence in current diagnostics snapshot."
        if top:
            fb = top[0].get("first_block") or {}
            reason = (
                f"Last investigated cycle decision={top[0].get('final_decision')}; "
                f"first block={fb.get('stage')} ({fb.get('reason')})."
            )
        return {
            "question": question,
            **package_evidence(
                answer=reason,
                evidence=top,
                source_subsystem="live_execution_explain+diagnostics",
                confidence=0.8 if top else 0.35,
                supporting_statistics={"investigations": len(investigations)},
            ),
        }

    if "quality" in q and ("fail" in q or "failed" in q or "why" in q):
        quality_fails = []
        for inv in investigations:
            for step in inv.get("timeline") or []:
                if "quality" in str(step.get("stage") or "").lower() and str(
                    step.get("status") or ""
                ).upper() == "FAIL":
                    quality_fails.append({"investigation": inv.get("id"), **step})
        return {
            "question": question,
            **package_evidence(
                answer=(
                    f"Found {len(quality_fails)} Quality FAIL stages in investigation timelines."
                    if quality_fails
                    else "No Quality FAIL stages in current investigation sample."
                ),
                evidence=quality_fails[:10] or investigations[:2],
                source_subsystem="live_execution_explain",
                confidence=0.85 if quality_fails else 0.4,
                supporting_statistics={"quality_fail_count": len(quality_fails)},
            ),
        }

    if "risk" in q and ("reject" in q or "fail" in q or "why" in q):
        risk_fails = []
        for inv in investigations:
            for step in inv.get("timeline") or []:
                if "risk" in str(step.get("stage") or "").lower() and str(
                    step.get("status") or ""
                ).upper() in {"FAIL", "REJECT", "REJECTED"}:
                    risk_fails.append({"investigation": inv.get("id"), **step})
        return {
            "question": question,
            **package_evidence(
                answer=(
                    f"Found {len(risk_fails)} Risk reject/fail stages."
                    if risk_fails
                    else "No Risk reject/fail stages in current sample."
                ),
                evidence=risk_fails[:10] or investigations[:2],
                source_subsystem="live_execution_explain",
                confidence=0.85 if risk_fails else 0.4,
            ),
        }

    if "evidence" in q or "show the evidence" in q or "show evidence" in q:
        return {
            "question": question,
            **package_evidence(
                answer="Evidence packages from latest investigations and AQS recommendations.",
                evidence={
                    "investigations": investigations[:3],
                    "aqs_recommendations": aqs_recs[:3],
                    "execution_explain": explain,
                },
                source_subsystem="aqc_evidence_viewer",
                confidence=0.75,
            ),
        }

    if "pf" in q or "profit factor" in q:
        highlights = _as_dict(comparison.get("highlights"))
        periods = _as_dict(comparison.get("periods"))
        return {
            "question": question,
            **package_evidence(
                answer=(
                    f"PF today={_as_dict(periods.get('today')).get('profit_factor')}; "
                    f"delta vs yesterday={highlights.get('pf_vs_yesterday_pct')}%."
                ),
                evidence=[comparison],
                source_subsystem="portfolio_analytics",
                confidence=0.7,
                historical_references=[
                    periods.get("yesterday"),
                    periods.get("last_week"),
                    periods.get("last_month"),
                ],
                supporting_statistics=highlights,
            ),
        }

    if ("safest" in q and "regime" in q) or ("regime" in q and "safe" in q):
        hist = _as_list(regime.get("history") or regime.get("regimes") or [])
        current = _as_dict(regime.get("current"))
        return {
            "question": question,
            **package_evidence(
                answer=(
                    f"Current regime={current.get('current_regime') or regime.get('current_regime')}. "
                    "Safest regime is the one with lowest drawdown / highest PF in regime research — "
                    "confirm via AQS regime expectations; AQC does not change thresholds."
                ),
                evidence=[current or regime, hist[:5]],
                source_subsystem="market_regime_intelligence",
                confidence=0.65,
            ),
        }

    if "experiment" in q and ("confidence" in q or "highest" in q or "best" in q):
        irl = _as_dict(ctx.get("sources", {}).get("irl"))
        board = _as_dict(irl.get("leaderboard"))
        rows = _as_list(board.get("rows"))
        best = rows[0] if rows else None
        if not best and aqs_recs:
            best = max(
                aqs_recs,
                key=lambda r: float(
                    (_as_dict(r.get("scores")).get("research_confidence_score") or 0)
                ),
            )
        return {
            "question": question,
            **package_evidence(
                answer=(
                    f"Highest-confidence research item: {best.get('name') or best.get('title')}"
                    if best
                    else "No experiments/recommendations available in snapshot."
                ),
                evidence=[best] if best else [],
                source_subsystem="irl+aqs",
                confidence=0.7 if best else 0.3,
            ),
        }

    if "alert" in q or "subsystem" in q:
        icc = _as_dict(ctx.get("sources", {}).get("icc"))
        alerts = _as_list(
            icc.get("alerts") or _as_dict(icc.get("sections")).get("alerts") or []
        )
        return {
            "question": question,
            **package_evidence(
                answer=f"ICC reports {len(alerts)} alerts/open items in current snapshot.",
                evidence=alerts[:10],
                source_subsystem="institutional_control_center",
                confidence=0.75 if alerts else 0.45,
            ),
        }

    if "explain today" in q or ("session" in q) or ("today" in q and "trading" in q):
        daily = _as_dict(summaries.get("daily"))
        return {
            "question": question,
            **package_evidence(
                answer=(
                    f"Daily summary — PF={_as_dict(daily.get('trading')).get('profit_factor')}, "
                    f"trades={_as_dict(daily.get('trading')).get('trade_count')}, "
                    f"regime={daily.get('regime')}."
                ),
                evidence=[daily, investigations[:2]],
                source_subsystem="executive_summary+investigations",
                confidence=0.72,
                supporting_statistics=_as_dict(daily.get("trading")),
            ),
        }

    if "drawdown" in q:
        risk = _as_dict(
            _as_dict(portfolio.get("sections")).get("risk") or portfolio.get("risk")
        )
        return {
            "question": question,
            **package_evidence(
                answer=f"Max drawdown in portfolio snapshot: {risk.get('max_drawdown_pct')}%.",
                evidence=[risk, comparison],
                source_subsystem="portfolio_analytics",
                confidence=0.7,
            ),
        }

    if any(k in q for k in ("knowledge graph", "qkg", "lineage", "root cause", "graph")):
        try:
            from app.domain.quant_knowledge_graph import qkg_query_for_ai

            gq = qkg_query_for_ai(question)
            return {
                "question": question,
                **package_evidence(
                    answer=f"QKG ({gq.get('capability')}): graph evidence attached.",
                    evidence=[gq],
                    source_subsystem="quant_knowledge_graph",
                    confidence=0.7,
                ),
            }
        except Exception:  # noqa: BLE001
            return {
                "question": question,
                **package_evidence(
                    answer="QKG unavailable in this snapshot.",
                    evidence=[],
                    source_subsystem="quant_knowledge_graph",
                    confidence=0.2,
                ),
            }

    # Default — never answer without evidence
    return {
        "question": question,
        **package_evidence(
            answer=(
                f"AQC correlated {ctx.get('source_count', 0)} subsystems. "
                "Try: why no trade, quality fail, PF decrease, safest regime, show evidence."
            ),
            evidence={
                "availability": ctx.get("availability"),
                "investigations_sample": investigations[:2],
                "aqs_sample": aqs_recs[:2],
            },
            source_subsystem="aqc_cross_system",
            confidence=0.55,
        ),
    }
