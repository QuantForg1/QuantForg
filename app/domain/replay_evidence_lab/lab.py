"""Report builders for Institutional Replay & Evidence Lab."""

from __future__ import annotations

from typing import Any

from app.domain.replay_evidence_lab.confidence import (
    build_confidence_report,
    score_kpi,
)
from app.domain.replay_evidence_lab.counterfactual import (
    analyze_no_trade_counterfactuals,
)
from app.domain.replay_evidence_lab.evidence_store import EvidenceDatabase
from app.domain.replay_evidence_lab.gates import (
    evaluate_evidence_gates,
    merge_thresholds,
)
from app.domain.replay_evidence_lab.models import HARD_LOCKS
from app.domain.replay_evidence_lab.replay import run_replay


def _win_rate(opportunities: list[dict[str, Any]]) -> float | None:
    closed = [
        o
        for o in opportunities
        if o.get("decision") in {"BUY", "SELL"} and o.get("rr") is not None
    ]
    if not closed:
        return None
    wins = sum(1 for o in closed if float(o["rr"]) > 0)
    return round(wins / len(closed), 4)


def build_recommendations(
    *,
    gates: dict[str, Any],
    coverage: dict[str, Any],
    confidence: dict[str, Any],
    counterfactual: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    if not gates.get("may_recommend_strategy_changes"):
        for check in gates.get("checks") or []:
            if not check.get("passed"):
                recs.append(
                    f"Evidence gate blocked: need {check['required']} "
                    f"{check['label'].lower()} (have {check['observed']})"
                )
        recs.append(
            "Do not recommend production strategy changes until all evidence gates pass"
        )
    else:
        recs.append(
            "Evidence gates passed — strategy-change ideas remain recommendations only"
        )

    lanes = (coverage.get("lanes") or {}) if isinstance(coverage, dict) else {}
    if int(lanes.get("live") or 0) == 0:
        recs.append("Collect live closed-trade evidence separately from demo/replay")
    if int(lanes.get("replay") or 0) == 0:
        recs.append("Run additional XAUUSD historical replays to grow replay lane")

    hist = counterfactual.get("result_histogram") or {}
    if hist.get("sl_first"):
        recs.append(
            f"Research: {hist['sl_first']} NO_TRADE counterfactuals hit SL first "
            "(research only — do not feed live KPIs)"
        )
    if hist.get("tp_first"):
        recs.append(
            f"Research: {hist['tp_first']} NO_TRADE counterfactuals hit TP first "
            "(research only — do not feed live KPIs)"
        )

    overall = confidence.get("overall_confidence")
    if overall in {"insufficient", "low"}:
        recs.append(
            f"Overall confidence is {overall} — expand sample before acting on KPIs"
        )

    recs.append(
        "Never auto-modify strategy, risk, safety, execution, or Performance IQ"
    )
    return recs


def build_open_questions(
    *,
    gates: dict[str, Any],
    replay: dict[str, Any],
    counterfactual: dict[str, Any],
) -> list[str]:
    qs: list[str] = []
    if not gates.get("all_passed"):
        qs.append("Which evidence lane is the bottleneck for gate clearance?")
    if int(replay.get("bars_loaded") or 0) == 0:
        qs.append("Can historical XAUUSD OHLC be supplied for denser replay coverage?")
    if int(counterfactual.get("no_trade_count") or 0) == 0:
        qs.append(
            "Are NO_TRADE decisions persisted with entry/SL/TP for counterfactuals?"
        )
    ambiguous = (counterfactual.get("result_histogram") or {}).get("ambiguous_same_bar")
    if ambiguous:
        qs.append(
            "How should same-bar SL+TP ambiguity be handled in research (never guess)?"
        )
    if not qs:
        qs.append("Are lane inventories still strictly segregated after new ingest?")
    return qs


def build_replay_evidence_lab(
    *,
    bars: list[dict[str, Any]] | None = None,
    opportunities: list[dict[str, Any]] | None = None,
    live_closed_trades: list[dict[str, Any]] | None = None,
    demo_records: list[dict[str, Any]] | None = None,
    research_records: list[dict[str, Any]] | None = None,
    thresholds: dict[str, Any] | None = None,
    database: EvidenceDatabase | None = None,
) -> dict[str, Any]:
    """Full Replay & Evidence Lab pack — advisory only."""
    db = database or EvidenceDatabase()
    th = merge_thresholds(thresholds)

    replay = run_replay(bars=bars, opportunities=opportunities)
    opps = list(replay.get("opportunities") or [])

    # Persist by lane — never mix
    db.extend("replay", opps)
    db.extend("live", live_closed_trades)
    db.extend("demo", demo_records)
    db.extend("research", research_records)

    # Also store NO_TRADE counterfactuals into research lane only
    counterfactual = analyze_no_trade_counterfactuals(opps)
    for row in counterfactual.get("results") or []:
        db.add("research", {**row, "kind": "no_trade_counterfactual"})

    coverage = db.inventory()
    live_n = int((coverage.get("lanes") or {}).get("live") or 0)
    replay_n = int((coverage.get("lanes") or {}).get("replay") or 0)
    no_trade_n = sum(1 for o in opps if o.get("decision") == "NO_TRADE")
    # Count research counterfactuals toward NO_TRADE observations
    no_trade_obs = max(no_trade_n, int(counterfactual.get("no_trade_count") or 0))

    gates = evaluate_evidence_gates(
        live_closed_trades=live_n,
        replay_opportunities=replay_n,
        no_trade_observations=no_trade_obs,
        thresholds=th,
    )

    wr = _win_rate(opps)
    kpis = [
        score_kpi(
            name="replay_win_rate",
            value=wr,
            sample_size=sum(
                1
                for o in opps
                if o.get("decision") in {"BUY", "SELL"} and o.get("rr") is not None
            ),
            required_sample=th["min_live_closed_trades"],
        ),
        score_kpi(
            name="replay_opportunity_count",
            value=len(opps),
            sample_size=len(opps),
            required_sample=th["min_replay_opportunities"],
        ),
        score_kpi(
            name="no_trade_rate",
            value=(round(no_trade_n / len(opps), 4) if opps else None),
            sample_size=len(opps),
            required_sample=th["min_no_trade_observations"],
        ),
    ]

    confidence = build_confidence_report(
        kpis=kpis,
        live_closed_trades=live_n,
        replay_opportunities=replay_n,
        no_trade_observations=no_trade_obs,
        thresholds=th,
    )

    replay_report = {
        "status": replay.get("status"),
        "symbol": "XAUUSD",
        "bars_loaded": replay.get("bars_loaded"),
        "opportunities_recorded": replay.get("opportunities_recorded"),
        "opportunities": opps,
        "research_only": True,
    }
    coverage_report = {
        **coverage,
        "thresholds": th,
        "gate_status": gates.get("all_passed"),
    }
    confidence_report = confidence
    open_questions = build_open_questions(
        gates=gates,
        replay=replay,
        counterfactual=counterfactual,
    )
    recommendations = build_recommendations(
        gates=gates,
        coverage=coverage,
        confidence=confidence,
        counterfactual=counterfactual,
    )

    return {
        "version": "1.0.1",
        "status": "available",
        "advisory_only": True,
        "never_modifies_strategy": True,
        "never_modifies_performance_intelligence": True,
        "hard_locks": HARD_LOCKS,
        "replay": replay_report,
        "counterfactual": counterfactual,
        "evidence": coverage_report,
        "gates": gates,
        "confidence": confidence_report,
        "reports": {
            "replay_report": replay_report,
            "evidence_coverage_report": coverage_report,
            "confidence_report": confidence_report,
            "open_questions": open_questions,
        },
        "recommendations": recommendations,
        "evidence_summary": {
            "bars_loaded": replay.get("bars_loaded"),
            "replay_opportunities": replay_n,
            "live_records": live_n,
            "demo_records": int((coverage.get("lanes") or {}).get("demo") or 0),
            "research_records": int((coverage.get("lanes") or {}).get("research") or 0),
            "no_trade_observations": no_trade_obs,
            "overall_confidence": confidence.get("overall_confidence"),
            "gates_passed": gates.get("all_passed"),
            "may_recommend_strategy_changes": gates.get(
                "may_recommend_strategy_changes"
            ),
        },
    }
