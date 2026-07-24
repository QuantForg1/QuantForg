"""AI Capital Protection — reduce new exposure near limits (never martingale)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.domain.institutional_trading.portfolio_intelligence.config import (
    DEFAULT_PI_CONFIG,
    PortfolioIntelligenceConfig,
)
from app.domain.institutional_trading.portfolio_intelligence.state import PortfolioState


@dataclass(frozen=True, slots=True)
class ProtectionDecision:
    allow_new_exposure: bool
    new_exposure_scale: float  # 0..1 multiplier for NEW trades only
    reasons: tuple[str, ...]
    limits: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "allow_new_exposure": self.allow_new_exposure,
            "new_exposure_scale": self.new_exposure_scale,
            "reasons": list(self.reasons),
            "limits": self.limits,
            "auto_reallocate": False,
        }


def evaluate_capital_protection(
    state: PortfolioState,
    *,
    candidate_symbol: str | None = None,
    config: PortfolioIntelligenceConfig | None = None,
) -> ProtectionDecision:
    cfg = config or DEFAULT_PI_CONFIG
    reasons: list[str] = []
    scale = 1.0
    eq = state.equity or 1.0

    def _pct(pnl: float) -> float:
        return abs(pnl) / eq * 100.0 if pnl < 0 else 0.0

    daily = _pct(state.daily_pnl)
    weekly = _pct(state.weekly_pnl)
    monthly = _pct(state.monthly_pnl)

    limits = {
        "max_daily_loss_pct": cfg.max_daily_loss_pct,
        "max_weekly_loss_pct": cfg.max_weekly_loss_pct,
        "max_monthly_loss_pct": cfg.max_monthly_loss_pct,
        "max_symbol_exposure_pct": cfg.max_symbol_exposure_pct,
        "max_correlated_exposure_pct": cfg.max_correlated_exposure_pct,
        "max_session_exposure_pct": cfg.max_session_exposure_pct,
        "max_leverage": cfg.max_leverage,
        "daily_loss_pct": round(daily, 3),
        "weekly_loss_pct": round(weekly, 3),
        "monthly_loss_pct": round(monthly, 3),
        "leverage": state.leverage,
    }

    # Hard stops
    if daily >= cfg.max_daily_loss_pct:
        return ProtectionDecision(False, 0.0, ("max daily loss reached",), limits)
    if weekly >= cfg.max_weekly_loss_pct:
        return ProtectionDecision(False, 0.0, ("max weekly loss reached",), limits)
    if monthly >= cfg.max_monthly_loss_pct:
        return ProtectionDecision(False, 0.0, ("max monthly loss reached",), limits)
    if state.leverage >= cfg.max_leverage:
        return ProtectionDecision(False, 0.0, ("max leverage reached",), limits)

    # Soft approach — reduce new exposure
    if daily >= cfg.max_daily_loss_pct * cfg.approach_ratio:
        scale = min(scale, 0.5)
        reasons.append("approaching daily loss limit")
    if weekly >= cfg.max_weekly_loss_pct * cfg.approach_ratio:
        scale = min(scale, 0.6)
        reasons.append("approaching weekly loss limit")
    if state.current_drawdown_pct >= cfg.drawdown_cut_pct:
        scale = min(scale, 0.55)
        reasons.append("drawdown protection")

    if candidate_symbol:
        sym = candidate_symbol.upper()
        total_exp = sum(abs(v) for v in state.exposure_by_symbol.values()) or 1.0
        sym_exp = abs(state.exposure_by_symbol.get(sym, 0.0))
        sym_pct = 100.0 * sym_exp / total_exp if total_exp else 0.0
        if sym_pct >= cfg.max_symbol_exposure_pct:
            return ProtectionDecision(
                False, 0.0, (f"max symbol exposure for {sym}",), limits
            )
        if sym_pct >= cfg.max_symbol_exposure_pct * cfg.approach_ratio:
            scale = min(scale, 0.5)
            reasons.append(f"approaching symbol exposure for {sym}")

        # Reuse Alpha correlation groups
        try:
            from app.domain.institutional_trading.alpha_engine.correlation import (
                may_open_with_correlation,
            )

            corr = may_open_with_correlation(
                candidate_symbol=sym, open_symbols=state.open_symbols
            )
            if not corr.allow:
                return ProtectionDecision(False, 0.0, (corr.reason,), limits)
        except Exception:
            pass

    if not reasons:
        reasons.append("within capital protection limits")
    return ProtectionDecision(True, round(scale, 3), tuple(reasons), limits)
