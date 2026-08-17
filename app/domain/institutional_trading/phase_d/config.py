"""Phase D feature flags — governance only. Never grants order authority."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PhaseDConfig:
    alpha_governance_enabled: bool = True
    promotion_gates_enabled: bool = True
    sample_governance_enabled: bool = True
    canary_enabled: bool = True
    rollback_enabled: bool = True
    execution_quality_gate_enabled: bool = True
    small_account_gate_enabled: bool = True
    # HARD — never flip via settings
    candidate_may_execute: bool = False
    auto_promote_to_live: bool = False
    auto_degraded_to_shadow: bool = False
    auto_critical_drift_block_new_entries: bool = False
    min_total_trades: int = 30
    min_oos_trades: int = 20
    min_shadow_trades: int = 20
    min_live_matched: int = 20
    canary_max_symbols: int = 1
    canary_max_duration_hours: int = 72
    canary_max_exposure_pct: float = 0.25
    small_account_equity_floor: float = 50.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "EVIDENCE_GATED_PROMOTION",
            "live_decision_authority": False,
            "candidate_may_execute": False,
            "auto_promote_to_live": False,
            "auto_degraded_to_shadow": False,
            "auto_critical_drift_block_new_entries": False,
            "min_total_trades": self.min_total_trades,
            "min_oos_trades": self.min_oos_trades,
            "min_shadow_trades": self.min_shadow_trades,
            "min_live_matched": self.min_live_matched,
            "canary_max_symbols": self.canary_max_symbols,
            "canary_max_duration_hours": self.canary_max_duration_hours,
            "canary_max_exposure_pct": self.canary_max_exposure_pct,
        }


DEFAULT_PHASE_D_CONFIG = PhaseDConfig()


def phase_d_config_from_settings(settings: Any | None = None) -> PhaseDConfig:
    if settings is None:
        try:
            from core.config.settings import get_settings

            settings = get_settings()
        except Exception:
            return DEFAULT_PHASE_D_CONFIG

    def _b(name: str, default: bool) -> bool:
        return bool(getattr(settings, name, default))

    def _i(name: str, default: int) -> int:
        try:
            return int(getattr(settings, name, default))
        except Exception:
            return default

    def _f(name: str, default: float) -> float:
        try:
            return float(getattr(settings, name, default))
        except Exception:
            return default

    return PhaseDConfig(
        alpha_governance_enabled=_b("phase_d_alpha_governance_enabled", True),
        promotion_gates_enabled=_b("phase_d_promotion_gates_enabled", True),
        sample_governance_enabled=_b("phase_d_sample_governance_enabled", True),
        canary_enabled=_b("phase_d_canary_enabled", True),
        rollback_enabled=_b("phase_d_rollback_enabled", True),
        execution_quality_gate_enabled=_b(
            "phase_d_execution_quality_gate_enabled", True
        ),
        small_account_gate_enabled=_b("phase_d_small_account_gate_enabled", True),
        candidate_may_execute=False,
        auto_promote_to_live=False,
        auto_degraded_to_shadow=False,
        auto_critical_drift_block_new_entries=False,
        min_total_trades=_i("phase_d_min_total_trades", 30),
        min_oos_trades=_i("phase_d_min_oos_trades", 20),
        min_shadow_trades=_i("phase_d_min_shadow_trades", 20),
        min_live_matched=_i("phase_d_min_live_matched", 20),
        canary_max_symbols=_i("phase_d_canary_max_symbols", 1),
        canary_max_duration_hours=_i("phase_d_canary_max_duration_hours", 72),
        canary_max_exposure_pct=_f("phase_d_canary_max_exposure_pct", 0.25),
        small_account_equity_floor=_f("phase_d_small_account_equity_floor", 50.0),
    )
