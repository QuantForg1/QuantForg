"""Phase B control plane facade — aggregates observation stores."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.phase_b.config import (
    DEFAULT_PHASE_B_CONFIG,
    PhaseBConfig,
    phase_b_config_from_settings,
)
from app.domain.institutional_trading.phase_b.execution_intel import ExecutionIntelStore
from app.domain.institutional_trading.phase_b.explain_journal import ExplainJournal
from app.domain.institutional_trading.phase_b.live_vs_research import LiveVsResearchStore
from app.domain.institutional_trading.phase_b.mae_mfe import LiveMaeMfeTracker
from app.domain.institutional_trading.phase_b.model_monitor_prep import (
    ModelMonitorPrepStore,
)
from app.domain.institutional_trading.phase_b.portfolio_incremental import (
    evaluate_incremental_risk,
)
from app.domain.institutional_trading.phase_b.post_trade_review import (
    PostTradeReviewStore,
)
from app.domain.institutional_trading.phase_b.regime_align import regime_align_snapshot
from app.domain.institutional_trading.phase_b.research_integrity_prep import (
    ResearchIntegrityPrepStore,
)
from app.domain.institutional_trading.phase_b.strategy_matrix import StrategyMatrixStore


@dataclass
class PhaseBControlPlane:
    config: PhaseBConfig = field(default_factory=lambda: DEFAULT_PHASE_B_CONFIG)
    mae_mfe: LiveMaeMfeTracker = field(default_factory=LiveMaeMfeTracker)
    execution: ExecutionIntelStore = field(default_factory=ExecutionIntelStore)
    explain: ExplainJournal = field(default_factory=ExplainJournal)
    matrix: StrategyMatrixStore = field(default_factory=StrategyMatrixStore)
    parity: LiveVsResearchStore = field(default_factory=LiveVsResearchStore)
    post_trade: PostTradeReviewStore = field(default_factory=PostTradeReviewStore)
    research_prep: ResearchIntegrityPrepStore = field(
        default_factory=ResearchIntegrityPrepStore
    )
    model_monitor: ModelMonitorPrepStore = field(default_factory=ModelMonitorPrepStore)
    last_incremental: dict[str, Any] | None = None
    last_regime: dict[str, Any] | None = None
    last_small_account: dict[str, Any] | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.matrix.min_sample = int(self.config.min_sample_trades)
        self.parity.min_sample = int(self.config.min_sample_trades)

    def apply_config(self, config: PhaseBConfig) -> None:
        self.config = config
        self.__post_init__()

    def observe_incremental_risk(self, **kwargs: Any) -> dict[str, Any]:
        view = evaluate_incremental_risk(**kwargs)
        self.last_incremental = view.to_dict()
        return self.last_incremental

    def observe_regime(self, raw: str | None) -> dict[str, Any]:
        self.last_regime = regime_align_snapshot(raw)
        return self.last_regime

    def snapshot(self) -> dict[str, Any]:
        return {
            "phase": "B",
            "mode": "OBSERVE_ONLY",
            "policy_changes": False,
            "config": self.config.to_dict(),
            "portfolio": self.last_incremental,
            "mae_mfe": self.mae_mfe.snapshot() if self.config.mae_mfe_enabled else None,
            "execution": (
                self.execution.snapshot()
                if self.config.execution_intel_enabled
                else None
            ),
            "regime": self.last_regime,
            "strategies": (
                self.matrix.snapshot()
                if self.config.strategy_matrix_enabled
                else None
            ),
            "live_vs_research": (
                self.parity.snapshot()
                if self.config.live_vs_research_enabled
                else None
            ),
            "explain_journal": (
                self.explain.recent(15)
                if self.config.explain_journal_enabled
                else None
            ),
            "post_trade": (
                self.post_trade.snapshot()
                if self.config.post_trade_review_enabled
                else None
            ),
            "small_account": self.last_small_account,
            "research_integrity_prep": (
                self.research_prep.snapshot()
                if self.config.research_integrity_prep_enabled
                else None
            ),
            "model_monitor_prep": (
                self.model_monitor.snapshot()
                if self.config.model_monitor_prep_enabled
                else None
            ),
        }


_PLANE: PhaseBControlPlane | None = None
_PLANE_LOCK = threading.Lock()


def get_phase_b_plane(*, refresh_config: bool = False) -> PhaseBControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        if _PLANE is None:
            _PLANE = PhaseBControlPlane(config=phase_b_config_from_settings())
        elif refresh_config:
            _PLANE.apply_config(phase_b_config_from_settings())
        return _PLANE


def reset_phase_b_plane_for_tests() -> PhaseBControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        _PLANE = PhaseBControlPlane(config=DEFAULT_PHASE_B_CONFIG)
        return _PLANE
