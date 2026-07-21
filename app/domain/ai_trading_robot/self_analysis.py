"""Self-analysis reports — discipline audit, never a profitability promise."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

from app.domain.ai_trading_robot.config import RobotV1Config
from app.domain.ai_trading_robot.journal_intelligence import JournalIntelligence
from app.domain.ai_trading_robot.strategy_health import StrategyHealth


@dataclass(frozen=True, slots=True)
class SelfAnalysisReport:
    generated_at: datetime
    version: str
    mission: str
    discipline_score: Decimal
    status: str
    findings: tuple[str, ...]
    recommendations: tuple[str, ...]
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "version": self.version,
            "mission": self.mission,
            "discipline_score": str(self.discipline_score),
            "status": self.status,
            "findings": list(self.findings),
            "recommendations": list(self.recommendations),
            "disclaimer": self.disclaimer,
        }


def build_self_analysis_report(
    config: RobotV1Config,
    *,
    journal: JournalIntelligence | None = None,
    health: StrategyHealth | None = None,
    filters_passed: int = 0,
    filters_total: int = 0,
    risk_passed: bool | None = None,
    safety_passed: bool | None = None,
    forbidden_attempts: int = 0,
) -> SelfAnalysisReport:
    findings: list[str] = []
    recommendations: list[str] = []
    score = Decimal("70")

    if forbidden_attempts > 0:
        score -= Decimal(min(40, forbidden_attempts * 15))
        findings.append(
            f"{forbidden_attempts} forbidden technique attempt(s) blocked "
            "(martingale/grid/average-loser)."
        )
        recommendations.append("Keep forbidden techniques hard-locked.")

    if risk_passed is False:
        score -= Decimal("20")
        findings.append("Latest evaluation failed Risk Engine — entries blocked.")
    elif risk_passed is True:
        findings.append("Risk Engine gate observed.")

    if safety_passed is False:
        score -= Decimal("20")
        findings.append("Latest evaluation failed Safety Engine — entries blocked.")
    elif safety_passed is True:
        findings.append("Safety Engine gate observed.")

    if filters_total > 0:
        ratio = Decimal(filters_passed) / Decimal(filters_total)
        score += (ratio - Decimal("0.5")) * Decimal("20")
        findings.append(
            f"Filter pass rate {filters_passed}/{filters_total}."
        )

    if journal is not None:
        findings.append(
            f"Journal: {journal.trade_count} trades, win rate {journal.win_rate}%, "
            f"net {journal.net_pnl}."
        )
        findings.extend(journal.insights[:3])
        if journal.net_pnl < 0:
            score -= Decimal("10")
            recommendations.append(
                "After negative journal PnL, shrink risk — never increase size."
            )

    if health is not None:
        findings.append(
            f"Strategy {health.strategy_id} health {health.score} ({health.status})."
        )
        if health.auto_pause:
            score -= Decimal("15")
            recommendations.append(
                f"Auto-pause active for {health.strategy_id} — do not force entries."
            )
        elif health.status == "watch":
            recommendations.append("Strategy on watch — require higher confidence.")

    if not recommendations:
        recommendations.append(
            "Maintain Signal → Strategy Validation → Risk → Safety → Execution."
        )
        recommendations.append(
            "Capital preservation first — Robot V1 never promises profitability."
        )

    score = max(Decimal("0"), min(Decimal("100"), score)).quantize(Decimal("0.01"))
    if score >= 75:
        status = "disciplined"
    elif score >= 50:
        status = "watch"
    else:
        status = "remediate"

    return SelfAnalysisReport(
        generated_at=datetime.now(UTC),
        version=config.version,
        mission=str(config.to_dict()["mission"]),
        discipline_score=score,
        status=status,
        findings=tuple(findings),
        recommendations=tuple(recommendations),
        disclaimer=(
            "This report measures process discipline and capital-preservation "
            "controls. It is not a performance guarantee and does not authorize "
            "orders. Every live order must still pass Risk Engine and Safety Engine."
        ),
    )
