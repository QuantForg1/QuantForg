"""QuantForg Portfolio Manager (QPM) — V5.2 portfolio orchestration.

Completely read-only. Advisory capital allocation and ranking across
certified strategies. Never executes trades, modifies production, changes
parameters, or rebalances/allocates automatically. Human approval required.
"""

from __future__ import annotations

from app.domain.quantforg_portfolio_manager.platform import QuantForgPortfolioManager

__all__ = ["QuantForgPortfolioManager", "get_qpm"]

_QPM: QuantForgPortfolioManager | None = None


def get_qpm() -> QuantForgPortfolioManager:
    global _QPM
    if _QPM is None:
        _QPM = QuantForgPortfolioManager()
    return _QPM
