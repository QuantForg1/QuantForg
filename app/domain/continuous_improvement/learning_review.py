"""Daily learning review — patterns, blockers, sessions, symbols (observe-only)."""

from __future__ import annotations

from typing import Any

from app.domain.continuous_improvement.persistence import utc_iso


def build_learning_review() -> dict[str, Any]:
    success_patterns: list[dict[str, Any]] = []
    failure_patterns: list[dict[str, Any]] = []
    blocking_gates: list[dict[str, Any]] = []
    profitable_sessions: list[dict[str, Any]] = []
    profitable_symbols: list[dict[str, Any]] = []
    recommendations: list[dict[str, Any]] = []

    try:
        from app.domain.institutional_trading.ai_scalping.pattern_intelligence import (
            build_pattern_intelligence,
        )

        pack = build_pattern_intelligence() or {}
        patterns = pack.get("patterns") or pack.get("buckets") or []
        if isinstance(patterns, dict):
            patterns = list(patterns.values())
        rows = [p for p in patterns if isinstance(p, dict)]
        ranked = sorted(
            rows,
            key=lambda r: float(r.get("win_rate") or r.get("score") or 0),
            reverse=True,
        )
        for r in ranked[:5]:
            wr = r.get("win_rate")
            entry = {
                "id": r.get("id") or r.get("pattern") or r.get("name"),
                "label": r.get("label") or r.get("name") or r.get("pattern"),
                "win_rate": wr,
                "sample_size": r.get("sample_size") or r.get("count"),
            }
            if wr is not None and float(wr) >= 0.5:
                success_patterns.append(entry)
            else:
                failure_patterns.append(entry)
        # Remaining low performers
        for r in ranked[-5:]:
            entry = {
                "id": r.get("id") or r.get("pattern") or r.get("name"),
                "label": r.get("label") or r.get("name") or r.get("pattern"),
                "win_rate": r.get("win_rate"),
                "sample_size": r.get("sample_size") or r.get("count"),
            }
            if entry not in failure_patterns and entry not in success_patterns:
                failure_patterns.append(entry)
        failure_patterns = failure_patterns[:5]
        success_patterns = success_patterns[:5]
    except Exception:  # noqa: S110
        pass

    try:
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        store = get_strategy_diagnostics_store()
        hist = []
        if hasattr(store, "list_recent"):
            hist = store.list_recent(limit=50) or []
        elif hasattr(store, "history"):
            hist = list(store.history or [])[-50:]
        gate_counts: dict[str, int] = {}
        for row in hist:
            if not isinstance(row, dict):
                continue
            gate = (
                row.get("first_blocker")
                or row.get("blocking_gate")
                or row.get("primary_blocker")
            )
            if gate:
                key = str(gate)[:120]
                gate_counts[key] = gate_counts.get(key, 0) + 1
        blocking_gates = [
            {"gate": g, "count": c}
            for g, c in sorted(gate_counts.items(), key=lambda x: x[1], reverse=True)[
                :10
            ]
        ]
    except Exception:  # noqa: S110
        pass

    try:
        from app.domain.institutional_trading.ai_scalping import (
            institutional_period_reports as period_mod,
        )

        build_institutional_period_reports = (
            period_mod.build_institutional_period_reports
        )

        periods = build_institutional_period_reports() or {}
        period_map = periods.get("periods") or periods
        daily = period_map.get("daily") or period_map.get("d") or {}
        if isinstance(daily, dict):
            for s in daily.get("top_sessions") or daily.get("sessions") or []:
                if isinstance(s, dict):
                    profitable_sessions.append(s)
            for s in daily.get("top_symbols") or daily.get("symbols") or []:
                if isinstance(s, dict):
                    profitable_symbols.append(s)
    except Exception:  # noqa: S110
        pass

    try:
        from app.domain.institutional_trading.ai_scalping import (
            adaptive_recommendations as rec_mod,
        )

        build_adaptive_recommendations = rec_mod.build_adaptive_recommendations

        rec = build_adaptive_recommendations() or {}
        rows = rec.get("recommendations") or rec.get("items") or []
        for r in rows[:15]:
            if isinstance(r, dict):
                recommendations.append(
                    {
                        "id": r.get("id") or r.get("code"),
                        "summary": r.get("summary")
                        or r.get("message")
                        or r.get("title"),
                        "priority": r.get("priority") or r.get("severity"),
                        "operator_review_only": True,
                        "auto_applies": False,
                    }
                )
    except Exception:  # noqa: S110
        pass

    return {
        "as_of": utc_iso(),
        "top_success_patterns": success_patterns,
        "top_failure_patterns": failure_patterns,
        "most_common_blocking_gates": blocking_gates,
        "most_profitable_sessions": profitable_sessions[:10],
        "most_profitable_symbols": profitable_symbols[:10],
        "recommendations": recommendations,
        "operator_review_only": True,
        "auto_applies": False,
        "fabricated": False,
        "observe_only": True,
        "note": "Recommendations for operator review only — never auto-applied",
    }
