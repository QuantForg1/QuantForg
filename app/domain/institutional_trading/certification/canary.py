"""Canary validator — track canary performance metrics (measurement only)."""

from __future__ import annotations

from dataclasses import replace

from app.domain.institutional_trading.certification.models import CanaryMetrics


class CanaryValidator:
    """Accumulate and snapshot canary metrics. Never places trades."""

    def __init__(self) -> None:
        self._metrics = CanaryMetrics()

    def reset(self) -> None:
        self._metrics = CanaryMetrics()

    def record(
        self,
        *,
        trade: bool = False,
        win: bool = False,
        profit_factor: float | None = None,
        expectancy: float | None = None,
        max_drawdown_pct: float | None = None,
        execution_ok: bool | None = None,
        oms_error: bool = False,
        gateway_error: bool = False,
        mt5_error: bool = False,
        duplicate_prevented: bool = False,
        duplicate_execution: bool = False,
    ) -> CanaryMetrics:
        m = self._metrics
        total = m.total_trades + (1 if trade else 0)
        wins = m.wins + (1 if trade and win else 0)
        attempts = m.execution_attempts + (1 if execution_ok is not None else 0)
        success = m.execution_success + (1 if execution_ok else 0)
        self._metrics = replace(
            m,
            total_trades=total,
            wins=wins,
            profit_factor=profit_factor if profit_factor is not None else m.profit_factor,
            expectancy=expectancy if expectancy is not None else m.expectancy,
            max_drawdown_pct=(
                max_drawdown_pct
                if max_drawdown_pct is not None
                else m.max_drawdown_pct
            ),
            execution_attempts=attempts,
            execution_success=success,
            oms_errors=m.oms_errors + (1 if oms_error else 0),
            gateway_errors=m.gateway_errors + (1 if gateway_error else 0),
            mt5_errors=m.mt5_errors + (1 if mt5_error else 0),
            duplicate_prevented=m.duplicate_prevented
            + (1 if duplicate_prevented else 0),
            duplicate_executions=m.duplicate_executions
            + (1 if duplicate_execution else 0),
        )
        return self._metrics

    def snapshot(self) -> CanaryMetrics:
        return self._metrics

    def load(self, metrics: CanaryMetrics) -> CanaryMetrics:
        self._metrics = metrics
        return self._metrics

    def summary(self) -> dict:
        return self._metrics.to_dict()
