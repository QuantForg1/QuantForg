"""Quant Studio — AI strategy review (advisory explanations only)."""

from __future__ import annotations

from typing import Any


def review_strategy(
    *,
    metrics: dict[str, Any],
    assumptions: dict[str, Any] | None = None,
    fold_stability: dict[str, Any] | None = None,
    graph_summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Explain strengths / weaknesses / overfitting risk from real metrics."""
    if not metrics:
        return {
            "status": "unavailable",
            "reason": "No strategy metrics available for review",
            "autonomous_trading": False,
        }

    strengths: list[str] = []
    weaknesses: list[str] = []
    risks: list[str] = []
    suitability: list[str] = []
    overfitting: list[str] = []
    sensitivity: list[str] = []

    def _f(key: str) -> float | None:
        raw = metrics.get(key)
        if raw is None:
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    wr = _f("win_rate")
    pf = _f("profit_factor")
    sharpe = _f("sharpe_ratio")
    sortino = _f("sortino_ratio")
    dd = _f("max_drawdown_pct")
    exp = _f("expectancy")
    trades = _f("trade_count")

    if wr is not None and wr >= 55:
        strengths.append(f"Win rate {wr:.1f}% supports consistency")
    elif wr is not None and wr < 40:
        weaknesses.append(f"Win rate {wr:.1f}% is low — edge must come from RR")

    if pf is not None and pf >= 1.5:
        strengths.append(f"Profit factor {pf:.2f} indicates positive expectancy structure")
    elif pf is not None and pf < 1.1:
        weaknesses.append(f"Profit factor {pf:.2f} near breakeven")

    if sharpe is not None and sharpe >= 1.0:
        strengths.append(f"Sharpe {sharpe:.2f} shows favorable risk-adjusted returns")
    elif sharpe is not None and sharpe < 0.5:
        weaknesses.append(f"Sharpe {sharpe:.2f} is weak")

    if dd is not None and dd >= 20:
        risks.append(f"Max drawdown {dd:.1f}% — capital stress risk")
    elif dd is not None and dd < 8:
        strengths.append(f"Controlled drawdown {dd:.1f}%")

    if exp is not None and exp > 0:
        strengths.append(f"Positive expectancy {exp:.4f} per trade")
    elif exp is not None and exp <= 0:
        risks.append("Non-positive expectancy — unsuitable for live capital")

    if trades is not None and trades < 30:
        overfitting.append(
            f"Only {int(trades)} trades — sample too small; high overfit risk"
        )
        sensitivity.append("Parameter changes likely swing metrics on small sample")
    elif trades is not None and trades >= 100:
        strengths.append(f"Sample size {int(trades)} improves statistical confidence")

    if fold_stability:
        stab = fold_stability.get("stability_score")
        if stab is not None:
            try:
                s = float(stab)
                if s >= 0.7:
                    strengths.append(f"Walk-forward stability {s:.2f}")
                else:
                    overfitting.append(f"Walk-forward stability {s:.2f} — fragile OOS")
            except (TypeError, ValueError):
                pass

    assumptions = assumptions or {}
    sl = assumptions.get("stop_loss_distance")
    tp = assumptions.get("take_profit_distance")
    if sl and tp:
        try:
            rr = float(tp) / float(sl) if float(sl) else 0
            sensitivity.append(f"Configured RR ≈ {rr:.2f} (TP/SL distances)")
            if rr < 1.2:
                risks.append("SL/TP RR under 1.2 may not compensate win-rate drag")
            else:
                suitability.append(f"RR ≈ {rr:.2f} suits trend-following regimes")
        except (TypeError, ValueError):
            pass

    if graph_summary and graph_summary.get("warnings"):
        for w in graph_summary["warnings"]:
            weaknesses.append(str(w))

    if not suitability:
        suitability.append("Assess regime fit via session + volatility modules before live use")

    return {
        "status": "available",
        "strengths": strengths or ["No standout strengths from available metrics"],
        "weaknesses": weaknesses or ["No critical weaknesses flagged"],
        "risk": risks or ["Residual strategy risk remains"],
        "market_suitability": suitability,
        "overfitting": overfitting or ["No acute overfitting flag from sample size alone"],
        "parameter_sensitivity": sensitivity
        or ["Insufficient data to grade parameter sensitivity"],
        "why": {
            "summary": "Advisory strategy review from observed metrics only",
            "supporting_factors": strengths[:3] + weaknesses[:2] + risks[:2],
        },
        "autonomous_trading": False,
        "advisory_only": True,
        "never_modifies_user_settings": True,
    }
