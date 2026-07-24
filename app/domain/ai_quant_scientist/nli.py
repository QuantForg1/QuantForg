"""AQS natural language interface — deterministic institutional Q&A."""

from __future__ import annotations

from typing import Any


def answer_question(question: str, *, pack: dict[str, Any]) -> dict[str, Any]:
    q = (question or "").strip().lower()
    patterns = pack.get("patterns") or []
    weaknesses = pack.get("weaknesses") or []
    comparison = pack.get("comparison") or {}
    regimes = pack.get("regimes") or {}
    sensitivity = pack.get("sensitivity") or {}
    recommendations = pack.get("recommendations") or []

    def _base(answer: str, evidence: list[Any]) -> dict[str, Any]:
        return {
            "question": question,
            "answer": answer,
            "evidence": evidence,
            "advisory_only": True,
            "never_modifies_production": True,
        }

    if not q:
        return _base("Ask a research question about regimes, PF, drawdown, or experiments.", [])

    if "drawdown" in q or "why" in q and "poor" in q:
        weak = [w for w in weaknesses if "drawdown" in str(w.get("kind"))]
        if not weak:
            weak = weaknesses[:2]
        return _base(
            "Drawdown / poor performance drivers from current research sample: "
            + "; ".join(w.get("title", "") for w in weak)
            or "Insufficient weakness evidence in current snapshot.",
            weak,
        )

    if "regime" in q and ("highest" in q or "best" in q or "pf" in q):
        rows = regimes.get("regime_expectations") or []
        if rows:
            best = max(rows, key=lambda r: float(r.get("expected_pf") or 0))
            return _base(
                f"Highest expected PF regime in research table: {best.get('regime')} "
                f"(PF≈{best.get('expected_pf')}, WR≈{best.get('expected_win_rate')}).",
                [best],
            )
        return _base("Regime expectations unavailable in this snapshot.", [])

    if "regime" in q:
        return _base(
            f"Current regime: {regimes.get('current_regime') or 'unknown'}.",
            [regimes.get("current_regime"), regimes.get("regime_expectations", [])[:3]],
        )

    if "replay" in q or "experiment" in q and "best" in q:
        best = comparison.get("best_candidate")
        if best:
            return _base(
                f"Best research leaderboard candidate: {best.get('name')} "
                f"(PF={best.get('profit_factor')}, composite={best.get('composite_score')}).",
                [best, comparison.get("replay_experiments", [])[:3]],
            )
        return _base("No completed research experiments on the leaderboard yet.", [])

    if "parameter" in q or "stable" in q or "sensitivity" in q:
        stable = sensitivity.get("most_stable")
        if stable:
            return _base(
                f"Most stable research band: Quality={stable.get('quality')}, "
                f"Confluence={stable.get('confluence')} "
                f"(stability={stable.get('stability_score')}). Never applied live.",
                [stable],
            )
        return _base("Sensitivity grid not available.", [])

    if "evidence" in q or "show evidence" in q:
        top = recommendations[:3]
        return _base(
            "Top recommendation evidence packages attached.",
            [r.get("explainability") for r in top],
        )

    if "pf" in q or "profit factor" in q:
        return _base(
            f"Production vs candidate PF delta: {comparison.get('profit_factor_difference_pct')}%.",
            [comparison.get("production"), comparison.get("best_candidate")],
        )

    if "pattern" in q:
        return _base(
            "Discovered patterns: " + "; ".join(p.get("title", "") for p in patterns[:5]),
            patterns[:5],
        )

    if any(k in q for k in ("knowledge graph", "qkg", "lineage", "root cause", "graph")):
        try:
            from app.domain.quant_knowledge_graph import qkg_query_for_ai

            gq = qkg_query_for_ai(question)
            return _base(
                f"QKG ({gq.get('capability')}): graph query result attached.",
                [gq],
            )
        except Exception:  # noqa: BLE001
            return _base("QKG unavailable in this snapshot.", [])

    if any(k in q for k in ("simulation", "ise", "monte carlo", "walk forward", "digital twin")):
        try:
            from app.domain.institutional_simulation_engine import get_ise

            sims = get_ise().store.list_simulations(limit=5)
            analyses = [
                get_ise().analyze_for_aqs(str(s.get("simulation_id")))
                for s in sims
                if s.get("simulation_id")
            ]
            return _base(
                f"ISE digital twin: {len(sims)} recent isolated simulations analyzed.",
                [s for s in analyses if s],
            )
        except Exception:  # noqa: BLE001
            return _base("ISE unavailable in this snapshot.", [])

    # Default: summarize recommendations
    return _base(
        f"AQS has {len(recommendations)} open research recommendations. "
        "Try: regimes, drawdown, best experiment, stable parameter, or show evidence.",
        recommendations[:5],
    )
