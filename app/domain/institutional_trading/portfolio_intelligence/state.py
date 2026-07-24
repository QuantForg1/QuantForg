"""Portfolio state snapshot — never evaluate a symbol in isolation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class PortfolioState:
    equity: float = 0.0
    free_margin: float = 0.0
    used_margin: float = 0.0
    open_positions: int = 0
    open_symbols: list[str] = field(default_factory=list)
    exposure_by_symbol: dict[str, float] = field(default_factory=dict)
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    current_drawdown_pct: float = 0.0
    portfolio_volatility: float = 0.0
    leverage: float = 0.0
    session: str = "unknown"
    correlation_matrix: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "equity": self.equity,
            "free_margin": self.free_margin,
            "used_margin": self.used_margin,
            "open_positions": self.open_positions,
            "open_symbols": list(self.open_symbols),
            "exposure_by_symbol": dict(self.exposure_by_symbol),
            "daily_pnl": self.daily_pnl,
            "weekly_pnl": self.weekly_pnl,
            "monthly_pnl": self.monthly_pnl,
            "current_drawdown_pct": self.current_drawdown_pct,
            "portfolio_volatility": self.portfolio_volatility,
            "leverage": self.leverage,
            "session": self.session,
            "correlation_matrix": self.correlation_matrix,
        }


def build_portfolio_state(
    *,
    equity: float | None = None,
    free_margin: float | None = None,
    used_margin: float | None = None,
    open_symbols: list[str] | None = None,
    exposure_by_symbol: dict[str, float] | None = None,
    daily_pnl: float | None = None,
    weekly_pnl: float | None = None,
    monthly_pnl: float | None = None,
    current_drawdown_pct: float | None = None,
    portfolio_volatility: float | None = None,
    leverage: float | None = None,
    session: str | None = None,
    correlation_matrix: dict[str, Any] | None = None,
) -> PortfolioState:
    eq = float(equity or 0)
    used = float(used_margin or 0)
    free = float(free_margin if free_margin is not None else max(0.0, eq - used))
    lev = float(leverage) if leverage is not None else (used / eq if eq > 0 else 0.0)
    return PortfolioState(
        equity=eq,
        free_margin=free,
        used_margin=used,
        open_positions=len(open_symbols or []),
        open_symbols=list(open_symbols or []),
        exposure_by_symbol=dict(exposure_by_symbol or {}),
        daily_pnl=float(daily_pnl or 0),
        weekly_pnl=float(weekly_pnl or 0),
        monthly_pnl=float(monthly_pnl or 0),
        current_drawdown_pct=float(current_drawdown_pct or 0),
        portfolio_volatility=float(portfolio_volatility or 0),
        leverage=lev,
        session=str(session or "unknown"),
        correlation_matrix=dict(correlation_matrix or {}),
    )
