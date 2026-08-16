"""Phase C feature flags — research/shadow only. Never gates LIVE orders."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PhaseCConfig:
    provenance_enabled: bool = True
    leakage_checks_enabled: bool = True
    pbo_enabled: bool = True
    dsr_enabled: bool = True
    monte_carlo_enabled: bool = True
    parameter_sensitivity_enabled: bool = True
    champion_challenger_enabled: bool = True
    drift_enabled: bool = True
    calibration_enabled: bool = True
    parity_enabled: bool = True
    promotion_gate_enabled: bool = True
    # Hard: challenger must never execute
    challenger_may_execute: bool = False
    # Hard: no automatic APPROVED_FOR_LIVE
    auto_approve_for_live: bool = False
    # Future Phase D policies — DISABLED in Phase C
    future_degraded_to_shadow_enabled: bool = False
    future_critical_drift_block_enabled: bool = False
    min_sample_trades: int = 20
    min_trials_for_pbo: int = 8

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "RESEARCH_SHADOW_ONLY",
            "live_decision_authority": False,
            "challenger_may_execute": False,
            "auto_approve_for_live": False,
            "pbo_in_live": False,
            "dsr_in_live": False,
            "min_sample_trades": self.min_sample_trades,
            "min_trials_for_pbo": self.min_trials_for_pbo,
            "future_policies_disabled": True,
        }


DEFAULT_PHASE_C_CONFIG = PhaseCConfig()


def phase_c_config_from_settings(settings: Any | None = None) -> PhaseCConfig:
    if settings is None:
        try:
            from core.config.settings import get_settings

            settings = get_settings()
        except Exception:
            return DEFAULT_PHASE_C_CONFIG

    def _b(name: str, default: bool) -> bool:
        return bool(getattr(settings, name, default))

    def _i(name: str, default: int) -> int:
        try:
            return int(getattr(settings, name, default))
        except Exception:
            return default

    # Never allow challenger_may_execute or auto_approve to become True via env
    return PhaseCConfig(
        provenance_enabled=_b("phase_c_provenance_enabled", True),
        leakage_checks_enabled=_b("phase_c_leakage_checks_enabled", True),
        pbo_enabled=_b("phase_c_pbo_enabled", True),
        dsr_enabled=_b("phase_c_dsr_enabled", True),
        monte_carlo_enabled=_b("phase_c_monte_carlo_enabled", True),
        parameter_sensitivity_enabled=_b(
            "phase_c_parameter_sensitivity_enabled", True
        ),
        champion_challenger_enabled=_b("phase_c_champion_challenger_enabled", True),
        drift_enabled=_b("phase_c_drift_enabled", True),
        calibration_enabled=_b("phase_c_calibration_enabled", True),
        parity_enabled=_b("phase_c_parity_enabled", True),
        promotion_gate_enabled=_b("phase_c_promotion_gate_enabled", True),
        challenger_may_execute=False,
        auto_approve_for_live=False,
        future_degraded_to_shadow_enabled=False,
        future_critical_drift_block_enabled=False,
        min_sample_trades=_i("phase_c_min_sample_trades", 20),
        min_trials_for_pbo=_i("phase_c_min_trials_for_pbo", 8),
    )
