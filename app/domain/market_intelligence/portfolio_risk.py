"""Portfolio risk dashboard from real account inputs only."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.market_intelligence.config import MarketIntelligenceConfig


@dataclass(frozen=True, slots=True)
class PortfolioRiskInput:
    equity: Decimal | None = None
    allocated_pct: Decimal | None = None
    daily_risk_used_pct: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PortfolioRiskDashboard:
    equity: Decimal | None
    capital_allocation_pct: Decimal | None
    daily_risk_used_pct: Decimal | None
    remaining_risk_budget_pct: Decimal | None
    daily_risk_budget_pct: Decimal
    within_budget: bool
    status: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "equity": str(self.equity) if self.equity is not None else None,
            "capital_allocation_pct": (
                str(self.capital_allocation_pct)
                if self.capital_allocation_pct is not None
                else None
            ),
            "daily_risk_used_pct": (
                str(self.daily_risk_used_pct)
                if self.daily_risk_used_pct is not None
                else None
            ),
            "remaining_risk_budget_pct": (
                str(self.remaining_risk_budget_pct)
                if self.remaining_risk_budget_pct is not None
                else None
            ),
            "daily_risk_budget_pct": str(self.daily_risk_budget_pct),
            "within_budget": self.within_budget,
            "status": self.status,
            "reasons": list(self.reasons),
        }


def build_portfolio_risk_dashboard(
    config: MarketIntelligenceConfig, inp: PortfolioRiskInput
) -> PortfolioRiskDashboard:
    reasons: list[str] = []
    missing_all = (
        inp.equity is None
        and inp.allocated_pct is None
        and inp.daily_risk_used_pct is None
    )
    if missing_all:
        return PortfolioRiskDashboard(
            equity=None,
            capital_allocation_pct=None,
            daily_risk_used_pct=None,
            remaining_risk_budget_pct=None,
            daily_risk_budget_pct=config.daily_risk_budget_pct,
            within_budget=False,
            status="unavailable",
            reasons=(
                "No portfolio risk inputs supplied — empty dashboard; "
                "never invent allocation or risk used.",
            ),
        )

    used = inp.daily_risk_used_pct
    remaining: Decimal | None = None
    within = True
    if used is not None:
        remaining = (config.daily_risk_budget_pct - used).quantize(Decimal("0.01"))
        within = used < config.daily_risk_budget_pct
        reasons.append(
            f"Daily risk used {used}% of budget {config.daily_risk_budget_pct}%."
        )
        if not within:
            reasons.append("Daily risk budget exhausted — block new risk.")
    else:
        reasons.append("Daily risk used not supplied.")
        within = False

    if inp.allocated_pct is not None:
        if inp.allocated_pct > config.max_allocation_pct:
            within = False
            reasons.append(
                f"Allocation {inp.allocated_pct}% exceeds "
                f"{config.max_allocation_pct}%."
            )
        else:
            reasons.append(f"Capital allocation {inp.allocated_pct}%.")

    if inp.equity is not None:
        reasons.append(f"Equity snapshot {inp.equity} (caller-supplied).")

    return PortfolioRiskDashboard(
        equity=inp.equity,
        capital_allocation_pct=inp.allocated_pct,
        daily_risk_used_pct=used,
        remaining_risk_budget_pct=remaining,
        daily_risk_budget_pct=config.daily_risk_budget_pct,
        within_budget=within,
        status="available",
        reasons=tuple(reasons),
    )
