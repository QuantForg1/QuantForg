"""Phase A institutional safety hardening — config & feature flags.

Enforcement flags default ON. Disabling a flag turns off ONLY that new
enforcement layer; recording / persisted state is retained.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PhaseAConfig:
    """Tunables — reuse existing production defaults where possible."""

    # Feature flags (rollback = set False)
    kill_persistence_enabled: bool = True
    recon_gate_enabled: bool = True
    md_firewall_enabled: bool = True
    burst_latch_enabled: bool = True
    control_vocab_enabled: bool = True
    decision_journal_enabled: bool = True

    # Market-data freshness — matches StrategyRuntimeConfig.max_tick_age_seconds
    max_tick_age_seconds: float = 120.0
    # Soft degraded band (still blocks new entries when enforcement on)
    degraded_tick_age_seconds: float = 60.0

    # Burst latch — align with LiveHealthMonitor / ProductionIncidentDetector
    entry_burst_window_seconds: float = 60.0
    max_entries_per_minute: int = 6
    reject_burst_window_seconds: float = 120.0
    reject_burst_threshold: int = 5
    failure_burst_threshold: int = 5
    ambiguous_burst_threshold: int = 3
    burst_cooldown_seconds: float = 300.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "kill_persistence_enabled": self.kill_persistence_enabled,
            "recon_gate_enabled": self.recon_gate_enabled,
            "md_firewall_enabled": self.md_firewall_enabled,
            "burst_latch_enabled": self.burst_latch_enabled,
            "control_vocab_enabled": self.control_vocab_enabled,
            "decision_journal_enabled": self.decision_journal_enabled,
            "max_tick_age_seconds": self.max_tick_age_seconds,
            "degraded_tick_age_seconds": self.degraded_tick_age_seconds,
            "max_entries_per_minute": self.max_entries_per_minute,
            "reject_burst_threshold": self.reject_burst_threshold,
            "burst_cooldown_seconds": self.burst_cooldown_seconds,
        }


DEFAULT_PHASE_A_CONFIG = PhaseAConfig()


def phase_a_config_from_settings(settings: Any | None = None) -> PhaseAConfig:
    """Build config from Settings env overrides when present."""
    if settings is None:
        try:
            from core.config.settings import get_settings

            settings = get_settings()
        except Exception:
            return DEFAULT_PHASE_A_CONFIG

    def _b(name: str, default: bool) -> bool:
        return bool(getattr(settings, name, default))

    def _f(name: str, default: float) -> float:
        try:
            return float(getattr(settings, name, default))
        except Exception:
            return default

    def _i(name: str, default: int) -> int:
        try:
            return int(getattr(settings, name, default))
        except Exception:
            return default

    return PhaseAConfig(
        kill_persistence_enabled=_b("phase_a_kill_persistence_enabled", True),
        recon_gate_enabled=_b("phase_a_recon_gate_enabled", True),
        md_firewall_enabled=_b("phase_a_md_firewall_enabled", True),
        burst_latch_enabled=_b("phase_a_burst_latch_enabled", True),
        control_vocab_enabled=_b("phase_a_control_vocab_enabled", True),
        decision_journal_enabled=_b("phase_a_decision_journal_enabled", True),
        max_tick_age_seconds=_f("phase_a_max_tick_age_seconds", 120.0),
        degraded_tick_age_seconds=_f("phase_a_degraded_tick_age_seconds", 60.0),
        max_entries_per_minute=_i("phase_a_max_entries_per_minute", 6),
        reject_burst_threshold=_i("phase_a_reject_burst_threshold", 5),
        failure_burst_threshold=_i("phase_a_failure_burst_threshold", 5),
        ambiguous_burst_threshold=_i("phase_a_ambiguous_burst_threshold", 3),
        burst_cooldown_seconds=_f("phase_a_burst_cooldown_seconds", 300.0),
    )
