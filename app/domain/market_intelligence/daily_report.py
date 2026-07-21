"""Daily validation report from supplied trade/violation records only."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class DayTradeRecord:
    trade_id: str
    side: str
    pnl: Decimal | None = None
    accepted: bool | None = None
    notes: str = ""


@dataclass(frozen=True, slots=True)
class RuleViolation:
    code: str
    detail: str


@dataclass(frozen=True, slots=True)
class DailyValidationReport:
    generated_at: datetime
    trade_count: int
    accepted_count: int
    rejected_count: int
    net_pnl: Decimal | None
    violations: tuple[RuleViolation, ...]
    recommendations: tuple[str, ...]
    summary: str
    disclaimer: str

    def to_dict(self) -> dict[str, object]:
        return {
            "generated_at": self.generated_at.isoformat(),
            "trade_count": self.trade_count,
            "accepted_count": self.accepted_count,
            "rejected_count": self.rejected_count,
            "net_pnl": str(self.net_pnl) if self.net_pnl is not None else None,
            "violations": [
                {"code": v.code, "detail": v.detail} for v in self.violations
            ],
            "recommendations": list(self.recommendations),
            "summary": self.summary,
            "disclaimer": self.disclaimer,
        }


def build_daily_validation_report(
    *,
    trades: tuple[DayTradeRecord, ...] = (),
    violations: tuple[RuleViolation, ...] = (),
) -> DailyValidationReport:
    if not trades and not violations:
        return DailyValidationReport(
            generated_at=datetime.now(UTC),
            trade_count=0,
            accepted_count=0,
            rejected_count=0,
            net_pnl=None,
            violations=(),
            recommendations=(
                "No day trades or violations supplied — empty report.",
            ),
            summary="Daily validation unavailable without real day records.",
            disclaimer=(
                "Report uses only supplied records. Never invents fills or PnL. "
                "Not a profitability promise."
            ),
        )

    accepted = sum(1 for t in trades if t.accepted is True)
    rejected = sum(1 for t in trades if t.accepted is False)
    pnls = [t.pnl for t in trades if t.pnl is not None]
    net = (
        sum(pnls, Decimal("0")).quantize(Decimal("0.01")) if pnls else None
    )

    recommendations: list[str] = []
    if violations:
        recommendations.append(
            f"Operator review recommended — {len(violations)} rule violation(s)."
        )
    if rejected > accepted and trades:
        recommendations.append(
            "More rejects than accepts — review filter thresholds and consensus."
        )
    if net is not None and net < 0:
        recommendations.append(
            "Negative day PnL in sample — reduce risk; never increase after losses."
        )
    if not recommendations:
        recommendations.append(
            "No critical flags — maintain Risk/Safety gates and dry-run discipline."
        )

    summary = (
        f"Day sample: {len(trades)} trades "
        f"(accepted={accepted}, rejected={rejected}); "
        f"violations={len(violations)}; "
        f"net_pnl={'n/a' if net is None else net}."
    )
    return DailyValidationReport(
        generated_at=datetime.now(UTC),
        trade_count=len(trades),
        accepted_count=accepted,
        rejected_count=rejected,
        net_pnl=net,
        violations=violations,
        recommendations=tuple(recommendations),
        summary=summary,
        disclaimer=(
            "Daily Validation Report measures process discipline from supplied "
            "records only. It never invents market data and never authorizes orders."
        ),
    )
