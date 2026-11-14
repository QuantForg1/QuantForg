"""Phase 3 — household portfolio intelligence (read + risk allocate).

Thin layer over Portfolio Engine sync, broker registry, and Risk Center prefs.
Never fabricates balances or trade permissions.
"""

from app.domain.portfolio_household.aggregation import (
    AccountMetricSlice,
    HouseholdPortfolio,
    aggregate_household,
    dedupe_positions,
)
from app.domain.portfolio_household.emergency_stops import (
    EmergencyStopStore,
    get_emergency_stop_store,
)
from app.domain.portfolio_household.exposure import (
    ExposureRollup,
    rollup_exposure,
)
from app.domain.portfolio_household.performance import (
    PerformanceReport,
    build_performance_report,
)
from app.domain.portfolio_household.risk_allocation import (
    HouseholdRiskCheck,
    evaluate_household_risk,
    household_new_entry_block_reason,
)

__all__ = [
    "AccountMetricSlice",
    "EmergencyStopStore",
    "ExposureRollup",
    "HouseholdPortfolio",
    "HouseholdRiskCheck",
    "PerformanceReport",
    "aggregate_household",
    "build_performance_report",
    "dedupe_positions",
    "evaluate_household_risk",
    "get_emergency_stop_store",
    "household_new_entry_block_reason",
    "rollup_exposure",
]
