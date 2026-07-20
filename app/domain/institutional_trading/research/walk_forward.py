"""Walk-forward engine — rolling / anchored windows; never peek into future."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from app.domain.institutional_trading.research.config import (
    DEFAULT_RESEARCH_CONFIG,
    ResearchConfig,
)
from app.domain.institutional_trading.research.models import (
    ResearchBar,
    SimulationResult,
    WalkForwardMode,
)
from app.domain.institutional_trading.research.simulation_engine import (
    SignalProvider,
    SimulationEngine,
)


@dataclass(frozen=True, slots=True)
class WalkForwardFold:
    fold_index: int
    train_start: int
    train_end: int  # exclusive
    test_start: int
    test_end: int  # exclusive
    oos_result: SimulationResult
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "fold_index": self.fold_index,
            "train_start": self.train_start,
            "train_end": self.train_end,
            "test_start": self.test_start,
            "test_end": self.test_end,
            "passed": self.passed,
            "oos_profit_factor": (
                str(self.oos_result.analytics.profit_factor)
                if self.oos_result.analytics.profit_factor is not None
                else None
            ),
            "oos_trades": self.oos_result.analytics.trade_count,
        }


@dataclass(frozen=True, slots=True)
class WalkForwardReport:
    mode: WalkForwardMode
    folds: tuple[WalkForwardFold, ...]
    passed: bool
    pass_ratio: Decimal

    def to_dict(self) -> dict[str, object]:
        return {
            "mode": self.mode.value,
            "folds": [f.to_dict() for f in self.folds],
            "passed": self.passed,
            "pass_ratio": str(self.pass_ratio),
        }


@dataclass
class WalkForwardEngine:
    """Split bars into train/validation/test without future leakage."""

    config: ResearchConfig = field(default_factory=lambda: DEFAULT_RESEARCH_CONFIG)
    simulation: SimulationEngine = field(default_factory=SimulationEngine)

    def run(
        self,
        bars: list[ResearchBar],
        signal_provider: SignalProvider,
        *,
        mode: WalkForwardMode = WalkForwardMode.ROLLING,
        train_size: int = 40,
        test_size: int = 20,
        step: int = 20,
    ) -> WalkForwardReport:
        if train_size <= 0 or test_size <= 0:
            raise ValueError("train_size and test_size must be > 0")
        folds: list[WalkForwardFold] = []
        fold_i = 0
        start = 0
        n = len(bars)

        while True:
            if mode is WalkForwardMode.ANCHORED:
                train_start = 0
                train_end = start + train_size
            else:
                train_start = start
                train_end = start + train_size
            test_start = train_end
            test_end = test_start + test_size
            if test_end > n:
                break
            # OOS only — never train on test bars; simulation uses test window alone
            # (parameters assumed fixed; optimization happens outside on train only)
            oos_bars = bars[test_start:test_end]
            oos = self.simulation.run(oos_bars, signal_provider=signal_provider)
            pf = oos.analytics.profit_factor
            passed = pf is not None and pf >= self.config.wf_min_oos_profit_factor
            folds.append(
                WalkForwardFold(
                    fold_index=fold_i,
                    train_start=train_start,
                    train_end=train_end,
                    test_start=test_start,
                    test_end=test_end,
                    oos_result=oos,
                    passed=passed,
                )
            )
            fold_i += 1
            start += step if mode is WalkForwardMode.ROLLING else step
            if mode is WalkForwardMode.ANCHORED:
                # grow train window; advance test
                pass

        if not folds:
            return WalkForwardReport(
                mode=mode,
                folds=(),
                passed=False,
                pass_ratio=Decimal("0"),
            )
        ratio = Decimal(sum(1 for f in folds if f.passed)) / Decimal(len(folds))
        overall = ratio >= self.config.wf_min_folds_pass_ratio
        return WalkForwardReport(
            mode=mode,
            folds=tuple(folds),
            passed=overall,
            pass_ratio=ratio.quantize(Decimal("0.0001")),
        )
