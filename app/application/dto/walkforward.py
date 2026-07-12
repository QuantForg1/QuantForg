"""Application DTOs for Walk-Forward Validation."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from app.domain.entities.walkforward import WalkForwardRun


@dataclass(frozen=True, slots=True)
class WalkForwardBarCommand:
    open_time: str
    open: str
    high: str
    low: str
    close: str
    volume: str = "0"
    close_time: str | None = None


@dataclass(frozen=True, slots=True)
class RunWalkForwardCommand:
    user_id: UUID
    request_id: str
    symbol: str
    timeframe: str = "m15"
    initial_balance: str = "10000"
    bars: tuple[WalkForwardBarCommand, ...] = ()
    in_sample_bars: int = 40
    out_of_sample_bars: int = 20
    step_bars: int = 20
    anchored: bool = False
    optimize_params: bool = True
    auto_analysis: bool = True
    ip_address: str = ""
    user_agent: str = ""


@dataclass(frozen=True, slots=True)
class WalkForwardRunDTO:
    id: UUID
    request_id: str
    symbol: str
    timeframe: str
    status: str
    promotion: str | None
    window_config: dict[str, object]
    folds: list[dict[str, object]]
    aggregated_is: dict[str, object]
    aggregated_oos: dict[str, object]
    robustness: dict[str, object]
    combined_equity: list[dict[str, object]]
    report: dict[str, object]
    bar_count: int
    fold_count: int
    error_message: str
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_entity(cls, run: WalkForwardRun) -> WalkForwardRunDTO:
        return cls(
            id=run.id,
            request_id=run.request_id,
            symbol=run.symbol,
            timeframe=run.timeframe,
            status=run.status.value,
            promotion=run.promotion.value if run.promotion else None,
            window_config=dict(run.window_config),
            folds=list(run.folds),
            aggregated_is=dict(run.aggregated_is),
            aggregated_oos=dict(run.aggregated_oos),
            robustness=dict(run.robustness),
            combined_equity=list(run.combined_equity),
            report=dict(run.report),
            bar_count=run.bar_count,
            fold_count=run.fold_count,
            error_message=run.error_message,
            started_at=run.started_at,
            finished_at=run.finished_at,
        )


@dataclass(frozen=True, slots=True)
class ListWalkForwardCommand:
    user_id: UUID
    limit: int = 50


@dataclass(frozen=True, slots=True)
class GetWalkForwardCommand:
    user_id: UUID
    run_id: UUID


@dataclass(frozen=True, slots=True)
class WalkForwardListDTO:
    items: list[WalkForwardRunDTO] = field(default_factory=list)
    count: int = 0
