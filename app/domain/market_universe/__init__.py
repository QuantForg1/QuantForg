"""Global multi-asset market universe — research/intelligence only.

Does not alter live XAUUSD_i execution, Opportunity 70, edge 5, Risk,
Safety, OMS, or MT5.
"""

from __future__ import annotations

from app.domain.market_universe.analytics import performance_report
from app.domain.market_universe.classification import classify_instrument
from app.domain.market_universe.config_audit import build_configuration_audit
from app.domain.market_universe.constants import (
    ALLOW_LIVE_PROMOTION,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_OPPORTUNITY_THRESHOLD,
)
from app.domain.market_universe.identity import canonical_desk, same_economic_instrument
from app.domain.market_universe.opportunity_board import build_opportunity_board
from app.domain.market_universe.registry import build_registry
from app.domain.market_universe.report import build_market_universe_report
from app.domain.market_universe.shadow_wall import (
    ResearchExecutionBlocked,
    scan_package_isolation,
    submit_order,
)

__all__ = [
    "ALLOW_LIVE_PROMOTION",
    "FROZEN_DIRECTIONAL_EDGE",
    "FROZEN_OPPORTUNITY_THRESHOLD",
    "ResearchExecutionBlocked",
    "build_configuration_audit",
    "build_market_universe_report",
    "build_opportunity_board",
    "build_registry",
    "canonical_desk",
    "classify_instrument",
    "performance_report",
    "same_economic_instrument",
    "scan_package_isolation",
    "submit_order",
]
