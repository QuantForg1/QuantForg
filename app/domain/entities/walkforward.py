"""Walk-Forward Validation domain models — offline validation only."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Self
from uuid import UUID

from app.domain.entities._guards import require
from app.domain.entities.base import Entity
from app.domain.enums.walkforward import PromotionDecision, WalkForwardStatus


@dataclass(frozen=True, slots=True)
class WalkForwardWindowConfig:
    """Configurable rolling IS/OOS schedule."""

    in_sample_bars: int = 40
    out_of_sample_bars: int = 20
    step_bars: int = 20  # roll forward by this many bars
    anchored: bool = False  # if True, IS always starts at 0

    def __post_init__(self) -> None:
        require(self.in_sample_bars >= 5, "in_sample_bars must be >= 5")
        require(self.out_of_sample_bars >= 2, "out_of_sample_bars must be >= 2")
        require(self.step_bars >= 1, "step_bars must be >= 1")

    def to_dict(self) -> dict[str, object]:
        return {
            "in_sample_bars": self.in_sample_bars,
            "out_of_sample_bars": self.out_of_sample_bars,
            "step_bars": self.step_bars,
            "anchored": self.anchored,
        }


@dataclass(frozen=True, slots=True)
class WalkForwardWindow:
    """One IS + OOS fold in the rolling schedule."""

    index: int
    is_start: int
    is_end: int  # exclusive
    oos_start: int
    oos_end: int  # exclusive

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "is_start": self.is_start,
            "is_end": self.is_end,
            "oos_start": self.oos_start,
            "oos_end": self.oos_end,
            "is_bars": self.is_end - self.is_start,
            "oos_bars": self.oos_end - self.oos_start,
        }


@dataclass(frozen=True, slots=True)
class FoldMetrics:
    """Metrics captured for one IS or OOS segment."""

    total_return_pct: Decimal = Decimal("0")
    max_drawdown_pct: Decimal = Decimal("0")
    win_rate: Decimal = Decimal("0")
    profit_factor: Decimal | None = None
    expectancy: Decimal = Decimal("0")
    sharpe_ratio: Decimal | None = None
    trade_count: int = 0

    def to_dict(self) -> dict[str, object]:
        return {
            "total_return_pct": str(self.total_return_pct),
            "max_drawdown_pct": str(self.max_drawdown_pct),
            "win_rate": str(self.win_rate),
            "profit_factor": (
                str(self.profit_factor) if self.profit_factor is not None else None
            ),
            "expectancy": str(self.expectancy),
            "sharpe_ratio": (
                str(self.sharpe_ratio) if self.sharpe_ratio is not None else None
            ),
            "trade_count": self.trade_count,
        }

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> Self:
        pf = data.get("profit_factor")
        sh = data.get("sharpe_ratio")
        return cls(
            total_return_pct=Decimal(str(data.get("total_return_pct", "0"))),
            max_drawdown_pct=Decimal(str(data.get("max_drawdown_pct", "0"))),
            win_rate=Decimal(str(data.get("win_rate", "0"))),
            profit_factor=Decimal(str(pf)) if pf is not None else None,
            expectancy=Decimal(str(data.get("expectancy", "0"))),
            sharpe_ratio=Decimal(str(sh)) if sh is not None else None,
            trade_count=int(str(data.get("trade_count", 0) or 0)),
        )


@dataclass(frozen=True, slots=True)
class FoldResult:
    """Result of one walk-forward fold (IS backtest + OOS validation)."""

    window: WalkForwardWindow
    is_metrics: FoldMetrics
    oos_metrics: FoldMetrics
    selected_params: dict[str, str] = field(default_factory=dict)
    is_equity: tuple[dict[str, object], ...] = ()
    oos_equity: tuple[dict[str, object], ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "window": self.window.to_dict(),
            "is_metrics": self.is_metrics.to_dict(),
            "oos_metrics": self.oos_metrics.to_dict(),
            "selected_params": dict(self.selected_params),
            "is_equity": list(self.is_equity),
            "oos_equity": list(self.oos_equity),
        }


@dataclass(frozen=True, slots=True)
class RobustnessReport:
    """Robustness / overfitting diagnostics across OOS folds."""

    parameter_stability: Decimal  # 0-100 (higher = more stable)
    consistency_score: Decimal  # 0-100 (% of OOS folds with positive return)
    overfitting_score: Decimal  # 0-100 (higher = more overfit)
    robustness_score: Decimal  # 0-100 overall
    regime_stability: Decimal  # 0-100 (higher = more stable across folds)
    fold_count: int = 0
    positive_oos_folds: int = 0
    avg_is_return_pct: Decimal = Decimal("0")
    avg_oos_return_pct: Decimal = Decimal("0")
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        return {
            "parameter_stability": str(self.parameter_stability),
            "consistency_score": str(self.consistency_score),
            "overfitting_score": str(self.overfitting_score),
            "robustness_score": str(self.robustness_score),
            "regime_stability": str(self.regime_stability),
            "fold_count": self.fold_count,
            "positive_oos_folds": self.positive_oos_folds,
            "avg_is_return_pct": str(self.avg_is_return_pct),
            "avg_oos_return_pct": str(self.avg_oos_return_pct),
            "notes": list(self.notes),
        }


@dataclass(frozen=True, slots=True)
class WalkForwardPromotionRules:
    """Deterministic thresholds for promotion decisions."""

    min_robustness_promote: Decimal = Decimal("60")
    max_overfitting_promote: Decimal = Decimal("40")
    min_consistency_promote: Decimal = Decimal("50")
    require_positive_avg_oos: bool = True
    max_robustness_reject: Decimal = Decimal("30")
    min_overfitting_reject: Decimal = Decimal("70")
    max_consistency_reject: Decimal = Decimal("20")


@dataclass(eq=False, kw_only=True)
class WalkForwardRun(Entity):
    """Persisted walk-forward validation run — decisions only, never live trades."""

    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str
    status: WalkForwardStatus
    promotion: PromotionDecision | None = None
    window_config: dict[str, object] = field(default_factory=dict)
    folds: list[dict[str, object]] = field(default_factory=list)
    aggregated_oos: dict[str, object] = field(default_factory=dict)
    aggregated_is: dict[str, object] = field(default_factory=dict)
    robustness: dict[str, object] = field(default_factory=dict)
    combined_equity: list[dict[str, object]] = field(default_factory=list)
    report: dict[str, object] = field(default_factory=dict)
    bar_count: int = 0
    fold_count: int = 0
    error_message: str = ""
    started_at: datetime | None = None
    finished_at: datetime | None = None

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.timeframe = self.timeframe.strip().lower()
        self.request_id = self.request_id.strip()
        require(len(self.request_id) > 0, "request_id is required")
        require(len(self.symbol) > 0, "symbol is required")

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        request_id: str,
        symbol: str,
        timeframe: str,
        window_config: WalkForwardWindowConfig,
        bar_count: int = 0,
        entity_id: UUID | None = None,
    ) -> Self:
        kwargs: dict[str, object] = {
            "user_id": user_id,
            "request_id": request_id,
            "symbol": symbol,
            "timeframe": timeframe,
            "status": WalkForwardStatus.PENDING,
            "window_config": window_config.to_dict(),
            "bar_count": bar_count,
        }
        if entity_id is not None:
            kwargs["id"] = entity_id
        return cls(**kwargs)  # type: ignore[arg-type]

    def mark_running(self, *, at: datetime | None = None) -> None:
        self.status = WalkForwardStatus.RUNNING
        self.started_at = at or datetime.now(UTC)
        self.touch()

    def mark_completed(
        self,
        *,
        promotion: PromotionDecision,
        folds: list[FoldResult],
        aggregated_is: FoldMetrics,
        aggregated_oos: FoldMetrics,
        robustness: RobustnessReport,
        combined_equity: list[dict[str, object]],
        at: datetime | None = None,
    ) -> None:
        self.status = WalkForwardStatus.COMPLETED
        self.promotion = promotion
        self.folds = [f.to_dict() for f in folds]
        self.fold_count = len(folds)
        self.aggregated_is = aggregated_is.to_dict()
        self.aggregated_oos = aggregated_oos.to_dict()
        self.robustness = robustness.to_dict()
        self.combined_equity = list(combined_equity)
        self.report = {
            "is_metrics": aggregated_is.to_dict(),
            "oos_metrics": aggregated_oos.to_dict(),
            "robustness_summary": robustness.to_dict(),
            "promotion": promotion.value,
            "fold_count": len(folds),
            "combined_equity_points": len(combined_equity),
        }
        self.finished_at = at or datetime.now(UTC)
        self.touch()

    def mark_failed(self, *, message: str, at: datetime | None = None) -> None:
        self.status = WalkForwardStatus.FAILED
        self.error_message = message.strip()[:1000]
        self.finished_at = at or datetime.now(UTC)
        self.touch()

    def to_dict(self) -> dict[str, object]:
        base = super().to_dict()
        base.update(
            {
                "user_id": str(self.user_id),
                "request_id": self.request_id,
                "symbol": self.symbol,
                "timeframe": self.timeframe,
                "status": self.status.value,
                "promotion": self.promotion.value if self.promotion else None,
                "window_config": dict(self.window_config),
                "folds": list(self.folds),
                "aggregated_oos": dict(self.aggregated_oos),
                "aggregated_is": dict(self.aggregated_is),
                "robustness": dict(self.robustness),
                "combined_equity": list(self.combined_equity),
                "report": dict(self.report),
                "bar_count": self.bar_count,
                "fold_count": self.fold_count,
                "error_message": self.error_message,
                "started_at": (
                    self.started_at.isoformat() if self.started_at else None
                ),
                "finished_at": (
                    self.finished_at.isoformat() if self.finished_at else None
                ),
            }
        )
        return base
