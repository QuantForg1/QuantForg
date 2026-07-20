"""Historical replay controller — pause/resume/step/speed over candle series."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from app.domain.institutional_trading.research.config import REPLAY_SPEEDS
from app.domain.institutional_trading.research.models import ResearchBar


class ReplayState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


@dataclass
class HistoricalReplayController:
    """Candle-by-candle replay with institutional speed presets."""

    bars: list[ResearchBar] = field(default_factory=list)
    index: int = 0
    speed: float = 1.0
    state: ReplayState = ReplayState.IDLE

    def load(self, bars: list[ResearchBar]) -> None:
        self.bars = list(bars)
        self.index = 0
        self.state = ReplayState.IDLE

    def start(self) -> None:
        if not self.bars:
            self.state = ReplayState.COMPLETED
            return
        self.index = 0
        self.state = ReplayState.RUNNING

    def pause(self) -> None:
        if self.state is ReplayState.RUNNING:
            self.state = ReplayState.PAUSED

    def resume(self) -> None:
        if self.state is ReplayState.PAUSED:
            self.state = ReplayState.RUNNING

    def set_speed(self, speed: float) -> None:
        if speed not in REPLAY_SPEEDS:
            raise ValueError(f"speed must be one of {REPLAY_SPEEDS}")
        self.speed = speed

    def step(self) -> ResearchBar | None:
        if self.state is ReplayState.PAUSED:
            # step allowed while paused
            pass
        elif self.state not in {ReplayState.RUNNING, ReplayState.IDLE, ReplayState.PAUSED}:
            return None
        if self.index >= len(self.bars):
            self.state = ReplayState.COMPLETED
            return None
        bar = self.bars[self.index]
        self.index += 1
        if self.index >= len(self.bars):
            self.state = ReplayState.COMPLETED
        elif self.state is ReplayState.IDLE:
            self.state = ReplayState.RUNNING
        return bar

    def remaining(self) -> int:
        return max(0, len(self.bars) - self.index)

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "total": len(self.bars),
            "speed": self.speed,
            "state": self.state.value,
            "remaining": self.remaining(),
        }
