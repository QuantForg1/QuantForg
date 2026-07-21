"""Historical Replay Engine — supplied bars only; never invents candles."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum

from app.domain.strategy_research_lab.config import StrategyLabConfig


class ReplayState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass(frozen=True, slots=True)
class ReplayBar:
    index: int
    time: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "time": self.time,
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": str(self.volume) if self.volume is not None else None,
        }


@dataclass
class HistoricalReplayEngine:
    """Lab replay over caller-supplied bars — never touches production."""

    config: StrategyLabConfig
    bars: list[ReplayBar] = field(default_factory=list)
    index: int = 0
    state: ReplayState = ReplayState.IDLE
    strategy_key: str | None = None

    def load(
        self,
        *,
        strategy_key: str,
        bars: list[dict[str, object]],
    ) -> dict[str, object]:
        capped = bars[: self.config.max_replay_bars]
        loaded: list[ReplayBar] = []
        for i, row in enumerate(capped):
            try:
                loaded.append(
                    ReplayBar(
                        index=i,
                        time=str(row.get("time") or row.get("timestamp") or ""),
                        open=Decimal(str(row["open"])),
                        high=Decimal(str(row["high"])),
                        low=Decimal(str(row["low"])),
                        close=Decimal(str(row["close"])),
                        volume=(
                            Decimal(str(row["volume"]))
                            if row.get("volume") is not None
                            else None
                        ),
                    )
                )
            except (KeyError, TypeError, ValueError):
                # Skip malformed supplied bars — never invent replacements.
                continue
        self.bars = loaded
        self.index = 0
        self.state = ReplayState.IDLE
        self.strategy_key = strategy_key
        return self.snapshot()

    def start(self) -> dict[str, object]:
        if not self.bars:
            self.state = ReplayState.COMPLETED
        else:
            self.index = 0
            self.state = ReplayState.RUNNING
        return self.snapshot()

    def pause(self) -> dict[str, object]:
        if self.state is ReplayState.RUNNING:
            self.state = ReplayState.PAUSED
        return self.snapshot()

    def resume(self) -> dict[str, object]:
        if self.state is ReplayState.PAUSED:
            self.state = ReplayState.RUNNING
        return self.snapshot()

    def step(self) -> dict[str, object]:
        if not self.bars:
            self.state = ReplayState.COMPLETED
            return self.snapshot(current=None)
        if self.index >= len(self.bars):
            self.state = ReplayState.COMPLETED
            return self.snapshot(current=None)
        current = self.bars[self.index]
        self.index += 1
        if self.index >= len(self.bars):
            self.state = ReplayState.COMPLETED
        elif self.state is ReplayState.IDLE:
            self.state = ReplayState.RUNNING
        return self.snapshot(current=current)

    def snapshot(self, current: ReplayBar | None = None) -> dict[str, object]:
        return {
            "strategy_key": self.strategy_key,
            "state": self.state.value,
            "index": self.index,
            "total_bars": len(self.bars),
            "current": current.to_dict() if current else None,
            "lab_only": True,
            "affects_production_positions": False,
            "note": (
                "Historical replay uses supplied bars only. "
                "Never invents market data. Never submits orders."
            ),
        }
