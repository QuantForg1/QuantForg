"""Explainable AI risk alerts — never mutate kill-switch or risk prefs."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True, slots=True)
class AiRiskAlert:
    code: str
    severity: str  # info | warning | critical
    title: str
    explanation: str
    recommended_action: str
    evidence: dict[str, Any]


def build_ai_risk_alerts(
    *,
    portfolio: dict[str, Any] | None = None,
    strategy_health: dict[str, Any] | None = None,
    signal_quality_drift: dict[str, Any] | None = None,
    execution: dict[str, Any] | None = None,
) -> list[AiRiskAlert]:
    alerts: list[AiRiskAlert] = []
    portfolio = portfolio or {}
    strategy_health = strategy_health or {}
    signal_quality_drift = signal_quality_drift or {}
    execution = execution or {}

    dd = _dec(portfolio.get("drawdown_pct") or portfolio.get("max_drawdown_pct"))
    if dd is not None and dd >= Decimal("10"):
        alerts.append(
            AiRiskAlert(
                code="portfolio_drawdown",
                severity="critical" if dd >= Decimal("19") else "warning",
                title="Portfolio drawdown elevated",
                explanation=f"Observed drawdown {dd}% from supplied portfolio facts.",
                recommended_action="review",
                evidence={"drawdown_pct": str(dd)},
            )
        )

    consecutive = portfolio.get("consecutive_losses")
    try:
        n = int(consecutive) if consecutive is not None else 0
    except (TypeError, ValueError):
        n = 0
    if n >= 3:
        alerts.append(
            AiRiskAlert(
                code="consecutive_losses",
                severity="warning",
                title="Consecutive losses",
                explanation=f"{n} consecutive losses reported.",
                recommended_action="pause_strategy",
                evidence={"consecutive_losses": n},
            )
        )

    health = strategy_health.get("score")
    h = _dec(health)
    if h is not None and h < Decimal("40"):
        alerts.append(
            AiRiskAlert(
                code="strategy_deterioration",
                severity="warning",
                title="Strategy health deteriorating",
                explanation=f"Strategy health score {h} below 40.",
                recommended_action="pause_strategy",
                evidence={"health_score": str(h)},
            )
        )

    drift = _dec(signal_quality_drift.get("delta_quality"))
    if drift is not None and drift <= Decimal("-15"):
        alerts.append(
            AiRiskAlert(
                code="signal_quality_drift",
                severity="warning",
                title="Signal quality deterioration",
                explanation=f"Quality delta {drift} vs baseline.",
                recommended_action="review",
                evidence={"delta_quality": str(drift)},
            )
        )

    vol = _dec(portfolio.get("volatility_spike_pct"))
    if vol is not None and vol >= Decimal("50"):
        alerts.append(
            AiRiskAlert(
                code="abnormal_volatility",
                severity="warning",
                title="Abnormal volatility",
                explanation=f"Volatility spike {vol}% vs recent baseline.",
                recommended_action="review",
                evidence={"volatility_spike_pct": str(vol)},
            )
        )

    corr = portfolio.get("correlated_exposure_flag")
    if corr is True:
        alerts.append(
            AiRiskAlert(
                code="correlated_exposure",
                severity="info",
                title="Correlated exposure flagged",
                explanation="Caller reported correlated exposure concentration.",
                recommended_action="review",
                evidence={"correlated_exposure_flag": True},
            )
        )

    rejects = execution.get("recent_reject_count")
    try:
        rj = int(rejects) if rejects is not None else 0
    except (TypeError, ValueError):
        rj = 0
    if rj >= 5:
        alerts.append(
            AiRiskAlert(
                code="execution_anomaly",
                severity="warning",
                title="Unexpected execution rejects",
                explanation=f"{rj} recent rejects observed.",
                recommended_action="review",
                evidence={"recent_reject_count": rj},
            )
        )

    return alerts


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None
