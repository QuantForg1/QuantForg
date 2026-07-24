"""QuantForg Strategy Marketplace & Registry (QSMR) — V5.1.

Completely read-only centralized strategy registry.
Never executes trades, modifies strategies/production, approves
certifications, or deploys strategies.
"""

from __future__ import annotations

from app.domain.quantforg_strategy_marketplace.platform import (
    QuantForgStrategyMarketplace,
)

__all__ = ["QuantForgStrategyMarketplace", "get_qsmr"]

_QSMR: QuantForgStrategyMarketplace | None = None


def get_qsmr() -> QuantForgStrategyMarketplace:
    global _QSMR
    if _QSMR is None:
        _QSMR = QuantForgStrategyMarketplace()
    return _QSMR
