"""Portfolio-wide risk aggregation for multi-asset scalping (v7).

Combines ALL open symbols into one exposure / daily-loss view.
Does not raise risk ceilings or lower quality floors.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.decision_models import AccountRiskState


@dataclass(frozen=True, slots=True)
class PortfolioRiskSnapshot:
    """Aggregated book facts used by the multi-asset portfolio gate."""

    open_positions: int
    daily_loss_pct: Decimal
    exposure_pct: Decimal
    max_open_positions: int
    max_daily_loss_pct: Decimal
    max_exposure_pct: Decimal
    equity: Decimal
    daily_pnl: Decimal
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "open_positions": self.open_positions,
            "daily_loss_pct": str(self.daily_loss_pct),
            "exposure_pct": str(self.exposure_pct),
            "max_open_positions": self.max_open_positions,
            "max_daily_loss_pct": str(self.max_daily_loss_pct),
            "max_exposure_pct": str(self.max_exposure_pct),
            "equity": str(self.equity),
            "daily_pnl": str(self.daily_pnl),
            "reasons": list(self.reasons),
            "scope": "portfolio_all_symbols",
        }


def portfolio_daily_loss_pct(
    *,
    equity: Decimal,
    daily_pnl: Decimal,
) -> Decimal:
    """Loss as % of equity (0 when flat or green). Portfolio-wide."""
    if equity is None or equity <= 0:
        return Decimal("0")
    if daily_pnl >= 0:
        return Decimal("0")
    return (abs(daily_pnl) / equity * Decimal("100")).quantize(Decimal("0.01"))


def portfolio_exposure_pct(
    *,
    open_positions: int,
    risk_per_trade_pct: Decimal,
    position_risk_pcts: Sequence[Decimal] | None = None,
) -> Decimal:
    """Combined exposure across ALL symbols (not per-symbol).

    Prefer explicit per-position risk contributions when provided; otherwise
    estimate from fixed-risk model: open_count x risk_per_trade_pct.
    """
    if position_risk_pcts:
        total = sum(
            (Decimal(str(p)) for p in position_risk_pcts if p is not None),
            Decimal("0"),
        )
        return max(Decimal("0"), total).quantize(Decimal("0.01"))
    n = max(0, int(open_positions))
    if n <= 0:
        return Decimal("0")
    return (Decimal(n) * risk_per_trade_pct).quantize(Decimal("0.01"))


def aggregate_portfolio_risk(
    account: AccountRiskState | None,
    *,
    config: AiScalpingConfig | None = None,
    ite_config: ITEConfig | None = None,
    position_risk_pcts: Sequence[Decimal] | None = None,
    open_positions_override: int | None = None,
) -> PortfolioRiskSnapshot:
    """Build portfolio-combined risk snapshot from live account/book facts."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    ite = ite_config or DEFAULT_ITE_CONFIG
    reasons: list[str] = []

    equity = Decimal("0")
    daily_pnl = Decimal("0")
    open_n = 0
    if account is not None:
        equity = Decimal(str(account.equity or 0))
        daily_pnl = Decimal(str(account.daily_pnl or 0))
        open_n = int(account.open_positions or 0)
    if open_positions_override is not None:
        open_n = int(open_positions_override)

    dd = portfolio_daily_loss_pct(equity=equity, daily_pnl=daily_pnl)
    exp = portfolio_exposure_pct(
        open_positions=open_n,
        risk_per_trade_pct=cfg.risk_per_trade_pct,
        position_risk_pcts=position_risk_pcts,
    )
    max_open = int(cfg.max_open_trades)
    # Prefer ITE institutional daily-loss ceiling (same as v6.3 desk); never raise it
    max_dd = Decimal(str(ite.max_daily_loss_pct))
    max_exp = Decimal(str(cfg.max_daily_exposure_pct))

    reasons.append(
        f"Portfolio open={open_n} daily_loss={dd}% exposure={exp}% "
        f"(limits open<{max_open} loss<{max_dd}% exp<{max_exp}%)"
    )
    return PortfolioRiskSnapshot(
        open_positions=open_n,
        daily_loss_pct=dd,
        exposure_pct=exp,
        max_open_positions=max_open,
        max_daily_loss_pct=max_dd,
        max_exposure_pct=max_exp,
        equity=equity,
        daily_pnl=daily_pnl,
        reasons=tuple(reasons),
    )
