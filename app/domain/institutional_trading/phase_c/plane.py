"""Phase C control plane — aggregates research integrity / governance stores.

Failure of this plane must never alter LIVE trading connectivity or Phase A/B.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Any

from app.domain.institutional_trading.phase_c.calibration_monitor import (
    CalibrationMonitor,
)
from app.domain.institutional_trading.phase_c.champion_challenger_shadow import (
    ChampionChallengerShadowStore,
    assert_challenger_cannot_execute,
)
from app.domain.institutional_trading.phase_c.change_control import (
    ModelChangeControlStore,
)
from app.domain.institutional_trading.phase_c.config import (
    DEFAULT_PHASE_C_CONFIG,
    PhaseCConfig,
    phase_c_config_from_settings,
)
from app.domain.institutional_trading.phase_c.drift import DriftMonitorStore
from app.domain.institutional_trading.phase_c.dsr import deflated_sharpe_ratio
from app.domain.institutional_trading.phase_c.fair_comparison import (
    compare_champion_challenger,
)
from app.domain.institutional_trading.phase_c.leakage import check_time_splits
from app.domain.institutional_trading.phase_c.monte_carlo_cert import (
    run_monte_carlo_certification,
)
from app.domain.institutional_trading.phase_c.parameter_sensitivity import (
    classify_from_scores,
)
from app.domain.institutional_trading.phase_c.parity_report import build_parity_report
from app.domain.institutional_trading.phase_c.pbo import estimate_pbo
from app.domain.institutional_trading.phase_c.promotion_gate import (
    PromotionStateMachine,
)
from app.domain.institutional_trading.phase_c.provenance import ProvenanceStore


@dataclass
class PhaseCControlPlane:
    config: PhaseCConfig = field(default_factory=lambda: DEFAULT_PHASE_C_CONFIG)
    provenance: ProvenanceStore = field(default_factory=ProvenanceStore)
    shadow: ChampionChallengerShadowStore = field(
        default_factory=ChampionChallengerShadowStore
    )
    drift: DriftMonitorStore = field(default_factory=DriftMonitorStore)
    calibration: CalibrationMonitor = field(default_factory=CalibrationMonitor)
    promotion: PromotionStateMachine = field(default_factory=PromotionStateMachine)
    change_control: ModelChangeControlStore = field(
        default_factory=ModelChangeControlStore
    )
    last_pbo: dict[str, Any] | None = None
    last_dsr: dict[str, Any] | None = None
    last_monte_carlo: dict[str, Any] | None = None
    last_sensitivity: dict[str, Any] | None = None
    last_leakage: dict[str, Any] | None = None
    last_parity: dict[str, Any] | None = None
    last_comparison: dict[str, Any] | None = None
    _lock: threading.RLock = field(default_factory=threading.RLock, repr=False)

    def __post_init__(self) -> None:
        self.drift.min_sample = int(self.config.min_sample_trades)
        self.calibration.min_sample = int(self.config.min_sample_trades)
        self.promotion.auto_approve_for_live = False
        assert_challenger_cannot_execute()

    def apply_config(self, config: PhaseCConfig) -> None:
        # Force safety bits regardless of incoming config
        self.config = PhaseCConfig(
            provenance_enabled=config.provenance_enabled,
            leakage_checks_enabled=config.leakage_checks_enabled,
            pbo_enabled=config.pbo_enabled,
            dsr_enabled=config.dsr_enabled,
            monte_carlo_enabled=config.monte_carlo_enabled,
            parameter_sensitivity_enabled=config.parameter_sensitivity_enabled,
            champion_challenger_enabled=config.champion_challenger_enabled,
            drift_enabled=config.drift_enabled,
            calibration_enabled=config.calibration_enabled,
            parity_enabled=config.parity_enabled,
            promotion_gate_enabled=config.promotion_gate_enabled,
            challenger_may_execute=False,
            auto_approve_for_live=False,
            future_degraded_to_shadow_enabled=False,
            future_critical_drift_block_enabled=False,
            min_sample_trades=config.min_sample_trades,
            min_trials_for_pbo=config.min_trials_for_pbo,
        )
        self.__post_init__()

    def run_pbo(self, matrix: list[list[float]]) -> dict[str, Any]:
        self.last_pbo = estimate_pbo(
            matrix, min_trials=self.config.min_trials_for_pbo
        )
        return self.last_pbo

    def run_dsr(
        self, returns: list[float], *, n_trials: int
    ) -> dict[str, Any]:
        self.last_dsr = deflated_sharpe_ratio(returns, n_trials=n_trials)
        return self.last_dsr

    def run_monte_carlo(self, returns: list[float], **kwargs: Any) -> dict[str, Any]:
        self.last_monte_carlo = run_monte_carlo_certification(returns, **kwargs)
        return self.last_monte_carlo

    def run_sensitivity(
        self, baseline: float, neighbors: list[float]
    ) -> dict[str, Any]:
        self.last_sensitivity = classify_from_scores(baseline, neighbors)
        return self.last_sensitivity

    def run_leakage(self, **kwargs: Any) -> dict[str, Any]:
        self.last_leakage = check_time_splits(**kwargs)
        return self.last_leakage

    def run_parity(
        self, *, research: dict[str, Any], live: dict[str, Any]
    ) -> dict[str, Any]:
        self.last_parity = build_parity_report(
            research=research,
            live=live,
            min_sample=self.config.min_sample_trades,
        )
        return self.last_parity

    def run_comparison(self, **kwargs: Any) -> dict[str, Any]:
        kwargs.setdefault("min_sample", self.config.min_sample_trades)
        self.last_comparison = compare_champion_challenger(**kwargs)
        return self.last_comparison

    def snapshot(self) -> dict[str, Any]:
        # Optionally enrich from Phase B without coupling failure
        phase_b_parity = None
        try:
            from app.domain.institutional_trading.phase_b import get_phase_b_plane

            phase_b_parity = get_phase_b_plane().parity.snapshot()
        except Exception:
            phase_b_parity = None

        return {
            "phase": "C",
            "mode": "RESEARCH_SHADOW_ONLY",
            "live_decision_authority": False,
            "policy_changes": False,
            "challenger_execution_authority": False,
            "config": self.config.to_dict(),
            "research": {
                "provenance": (
                    self.provenance.snapshot()
                    if self.config.provenance_enabled
                    else None
                ),
                "leakage": self.last_leakage,
                "PBO": self.last_pbo if self.config.pbo_enabled else None,
                "DSR": self.last_dsr if self.config.dsr_enabled else None,
                "walk_forward": "REUSE_APPLICATION_WALKFORWARD_ENGINE",
                "monte_carlo": (
                    self.last_monte_carlo
                    if self.config.monte_carlo_enabled
                    else None
                ),
                "parameter_sensitivity": (
                    self.last_sensitivity
                    if self.config.parameter_sensitivity_enabled
                    else None
                ),
            },
            "champion": {
                "version": self.shadow.champion_version,
                "note": "production champion unchanged by Phase C",
            },
            "challenger": (
                self.shadow.snapshot()
                if self.config.champion_challenger_enabled
                else None
            ),
            "comparison": self.last_comparison,
            "drift": self.drift.snapshot() if self.config.drift_enabled else None,
            "calibration": (
                self.calibration.snapshot()
                if self.config.calibration_enabled
                else None
            ),
            "parity": self.last_parity
            if self.config.parity_enabled
            else None,
            "phase_b_live_vs_research": phase_b_parity,
            "promotion": (
                self.promotion.snapshot()
                if self.config.promotion_gate_enabled
                else None
            ),
            "change_control": self.change_control.snapshot(),
        }


_PLANE: PhaseCControlPlane | None = None
_PLANE_LOCK = threading.Lock()


def get_phase_c_plane(*, refresh_config: bool = False) -> PhaseCControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        if _PLANE is None:
            _PLANE = PhaseCControlPlane(config=phase_c_config_from_settings())
        elif refresh_config:
            _PLANE.apply_config(phase_c_config_from_settings())
        return _PLANE


def reset_phase_c_plane_for_tests() -> PhaseCControlPlane:
    global _PLANE
    with _PLANE_LOCK:
        _PLANE = PhaseCControlPlane(config=DEFAULT_PHASE_C_CONFIG)
        return _PLANE
