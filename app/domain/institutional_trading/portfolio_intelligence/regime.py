"""Global market regime intelligence — advisory portfolio input."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


REGIMES = (
    "GLOBAL_RISK_ON",
    "GLOBAL_RISK_OFF",
    "NEUTRAL",
    "TREND_EXPANSION",
    "TREND_EXHAUSTION",
    "LIQUIDITY_HUNT",
)


@dataclass(frozen=True, slots=True)
class GlobalRegime:
    regime: str
    confidence: int
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime": self.regime,
            "confidence": self.confidence,
            "reasons": list(self.reasons),
            "advisory_only": True,
        }


def detect_global_regime(
    *,
    portfolio_volatility: float = 0.0,
    daily_pnl: float = 0.0,
    equity: float = 0.0,
    avg_spread: float | None = None,
    risk_on_score: float | None = None,
) -> GlobalRegime:
    reasons: list[str] = []
    # Prefer explicit risk-on score when provided by upstream alpha/market desks
    if risk_on_score is not None:
        if risk_on_score >= 0.7:
            return GlobalRegime("GLOBAL_RISK_ON", 75, ("risk_on_score elevated",))
        if risk_on_score <= 0.3:
            return GlobalRegime("GLOBAL_RISK_OFF", 75, ("risk_on_score depressed",))

    if avg_spread is not None and avg_spread > 0 and portfolio_volatility > 2:
        reasons.append("spread+vol elevated")
        return GlobalRegime("LIQUIDITY_HUNT", 70, tuple(reasons) or ("liquidity stress",))

    if portfolio_volatility >= 3.5:
        reasons.append(f"portfolio_vol={portfolio_volatility}")
        if daily_pnl < 0:
            return GlobalRegime("TREND_EXHAUSTION", 65, tuple(reasons) + ("negative daily pnl",))
        return GlobalRegime("TREND_EXPANSION", 65, tuple(reasons))

    if equity > 0 and abs(daily_pnl) / equity > 0.02 and daily_pnl < 0:
        return GlobalRegime("GLOBAL_RISK_OFF", 60, ("sharp daily loss",))

    if daily_pnl > 0 and portfolio_volatility < 1.5:
        return GlobalRegime("GLOBAL_RISK_ON", 55, ("constructive pnl with contained vol",))

    return GlobalRegime("NEUTRAL", 50, ("no dominant global signal",))
