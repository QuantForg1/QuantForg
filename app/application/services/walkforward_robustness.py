"""Robustness metrics for walk-forward validation (no AI)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from statistics import pstdev

from app.domain.entities.walkforward import (
    FoldResult,
    RobustnessReport,
)


@dataclass(frozen=True, slots=True)
class RobustnessEngine:
    """Compute parameter stability, consistency, overfitting, robustness."""

    def compute(self, folds: list[FoldResult]) -> RobustnessReport:
        if not folds:
            return RobustnessReport(
                parameter_stability=Decimal("0"),
                consistency_score=Decimal("0"),
                overfitting_score=Decimal("100"),
                robustness_score=Decimal("0"),
                regime_stability=Decimal("0"),
                notes=("no folds",),
            )

        is_returns = [float(f.is_metrics.total_return_pct) for f in folds]
        oos_returns = [float(f.oos_metrics.total_return_pct) for f in folds]
        avg_is = sum(is_returns) / len(is_returns)
        avg_oos = sum(oos_returns) / len(oos_returns)

        positive = sum(1 for r in oos_returns if r > 0)
        consistency = (positive / len(oos_returns)) * 100.0

        # Overfitting: IS outperformance vs OOS, clamped 0-100
        gap = max(0.0, avg_is - avg_oos)
        denom = abs(avg_is) + 1.0
        overfitting = min(100.0, (gap / denom) * 100.0)

        # Regime stability: inverse of OOS return dispersion
        if len(oos_returns) >= 2:
            dispersion = pstdev(oos_returns)
        else:
            dispersion = abs(oos_returns[0]) if oos_returns else 0.0
        regime = max(0.0, 100.0 - min(100.0, dispersion * 2.0))

        # Parameter stability from selected param variance across folds
        param_stability = self._parameter_stability(folds)

        # Robustness: weighted blend (OOS-focused)
        robustness = (
            0.35 * consistency
            + 0.25 * (100.0 - overfitting)
            + 0.20 * float(param_stability)
            + 0.20 * regime
        )
        # Penalize if average OOS is negative
        if avg_oos < 0:
            robustness *= 0.7

        notes: list[str] = []
        if avg_oos <= 0:
            notes.append("average OOS return is non-positive")
        if overfitting >= 50:
            notes.append("elevated IS vs OOS gap (possible overfitting)")
        if consistency < 50:
            notes.append("fewer than half of OOS folds are profitable")

        return RobustnessReport(
            parameter_stability=Decimal(str(round(param_stability, 4))),
            consistency_score=Decimal(str(round(consistency, 4))),
            overfitting_score=Decimal(str(round(overfitting, 4))),
            robustness_score=Decimal(str(round(min(100.0, max(0.0, robustness)), 4))),
            regime_stability=Decimal(str(round(regime, 4))),
            fold_count=len(folds),
            positive_oos_folds=positive,
            avg_is_return_pct=Decimal(str(round(avg_is, 4))),
            avg_oos_return_pct=Decimal(str(round(avg_oos, 4))),
            notes=tuple(notes),
        )

    def _parameter_stability(self, folds: list[FoldResult]) -> float:
        """Score 0-100 from how often selected params stay the same."""
        if not folds:
            return 0.0
        keys = sorted({k for f in folds for k in f.selected_params})
        if not keys:
            return 100.0  # single fixed config — fully stable
        scores: list[float] = []
        for key in keys:
            values = [f.selected_params.get(key, "") for f in folds]
            # Fraction matching the mode
            mode = max(set(values), key=values.count)
            scores.append(values.count(mode) / len(values) * 100.0)
        return sum(scores) / len(scores)
