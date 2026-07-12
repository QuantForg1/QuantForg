"""Rolling window scheduler for walk-forward validation."""

from __future__ import annotations

from dataclasses import dataclass

from app.domain.entities._guards import require
from app.domain.entities.walkforward import (
    WalkForwardWindow,
    WalkForwardWindowConfig,
)


@dataclass(frozen=True, slots=True)
class RollingWindowScheduler:
    """Build in-sample / out-of-sample rolling (or anchored) windows."""

    def build(
        self,
        *,
        bar_count: int,
        config: WalkForwardWindowConfig,
    ) -> list[WalkForwardWindow]:
        require(bar_count > 0, "bar_count must be > 0")
        min_needed = config.in_sample_bars + config.out_of_sample_bars
        require(
            bar_count >= min_needed,
            f"need at least {min_needed} bars for walk-forward",
        )
        if config.anchored:
            return self._build_anchored(bar_count=bar_count, config=config)
        return self._build_rolling(bar_count=bar_count, config=config)

    def _build_rolling(
        self,
        *,
        bar_count: int,
        config: WalkForwardWindowConfig,
    ) -> list[WalkForwardWindow]:
        windows: list[WalkForwardWindow] = []
        index = 0
        is_start = 0
        while True:
            is_end = is_start + config.in_sample_bars
            oos_start = is_end
            oos_end = oos_start + config.out_of_sample_bars
            if oos_end > bar_count:
                break
            windows.append(
                WalkForwardWindow(
                    index=index,
                    is_start=is_start,
                    is_end=is_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                )
            )
            index += 1
            is_start += config.step_bars
        return windows

    def _build_anchored(
        self,
        *,
        bar_count: int,
        config: WalkForwardWindowConfig,
    ) -> list[WalkForwardWindow]:
        windows: list[WalkForwardWindow] = []
        index = 0
        is_end = config.in_sample_bars
        while True:
            oos_start = is_end
            oos_end = oos_start + config.out_of_sample_bars
            if oos_end > bar_count:
                break
            windows.append(
                WalkForwardWindow(
                    index=index,
                    is_start=0,
                    is_end=is_end,
                    oos_start=oos_start,
                    oos_end=oos_end,
                )
            )
            index += 1
            is_end += config.step_bars
        return windows
