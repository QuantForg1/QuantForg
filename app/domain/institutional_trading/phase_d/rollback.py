"""Deterministic canary rollback evaluation — fail closed for new risk."""

from __future__ import annotations

from typing import Any


def evaluate_rollback_triggers(
    *,
    unexpected_loss_burst: bool = False,
    drawdown_breach: bool = False,
    execution_degradation: bool = False,
    slippage_anomaly: bool = False,
    broker_rejection_anomaly: bool = False,
    reconciliation_failure: bool = False,
    data_quality_degradation: bool = False,
    severe_performance_divergence: bool = False,
    system_health_regression: bool = False,
    open_positions: int = 0,
) -> dict[str, Any]:
    triggers = {
        "unexpected_loss_burst": unexpected_loss_burst,
        "drawdown_breach": drawdown_breach,
        "execution_degradation": execution_degradation,
        "slippage_anomaly": slippage_anomaly,
        "broker_rejection_anomaly": broker_rejection_anomaly,
        "reconciliation_failure": reconciliation_failure,
        "data_quality_degradation": data_quality_degradation,
        "severe_performance_divergence": severe_performance_divergence,
        "system_health_regression": system_health_regression,
    }
    fired = [k for k, v in triggers.items() if v]
    if not fired:
        return {
            "action": "CONTINUE",
            "target": None,
            "triggers": triggers,
            "new_risk_allowed": True,
            "phase_a_disabled": False,
            "why_rolled_back": None,
        }
    # Fail closed for NEW risk; open positions remain under PME / Phase A
    return {
        "action": "ROLLBACK",
        "target": "SHADOW_ONLY",
        "triggers": triggers,
        "fired": fired,
        "new_risk_allowed": False,
        "phase_a_disabled": False,
        "open_positions_remain_managed": True,
        "open_positions": int(open_positions),
        "why_rolled_back": ",".join(fired),
    }
