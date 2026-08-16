"""Phase B feature flags — observe/report only. Defaults ON for telemetry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PhaseBConfig:
    mae_mfe_enabled: bool = True
    portfolio_incremental_enabled: bool = True
    execution_intel_enabled: bool = True
    regime_align_enabled: bool = True
    strategy_matrix_enabled: bool = True
    live_vs_research_enabled: bool = True
    explain_journal_enabled: bool = True
    post_trade_review_enabled: bool = True
    research_integrity_prep_enabled: bool = True
    model_monitor_prep_enabled: bool = True
    # Minimum closed trades before ranking claims
    min_sample_trades: int = 20

    def to_dict(self) -> dict[str, Any]:
        return {
            "mae_mfe_enabled": self.mae_mfe_enabled,
            "portfolio_incremental_enabled": self.portfolio_incremental_enabled,
            "execution_intel_enabled": self.execution_intel_enabled,
            "regime_align_enabled": self.regime_align_enabled,
            "strategy_matrix_enabled": self.strategy_matrix_enabled,
            "live_vs_research_enabled": self.live_vs_research_enabled,
            "explain_journal_enabled": self.explain_journal_enabled,
            "post_trade_review_enabled": self.post_trade_review_enabled,
            "min_sample_trades": self.min_sample_trades,
            "mode": "OBSERVE_ONLY",
        }


DEFAULT_PHASE_B_CONFIG = PhaseBConfig()


def phase_b_config_from_settings(settings: Any | None = None) -> PhaseBConfig:
    if settings is None:
        try:
            from core.config.settings import get_settings

            settings = get_settings()
        except Exception:
            return DEFAULT_PHASE_B_CONFIG

    def _b(name: str, default: bool) -> bool:
        return bool(getattr(settings, name, default))

    def _i(name: str, default: int) -> int:
        try:
            return int(getattr(settings, name, default))
        except Exception:
            return default

    return PhaseBConfig(
        mae_mfe_enabled=_b("phase_b_mae_mfe_enabled", True),
        portfolio_incremental_enabled=_b(
            "phase_b_portfolio_incremental_enabled", True
        ),
        execution_intel_enabled=_b("phase_b_execution_intel_enabled", True),
        regime_align_enabled=_b("phase_b_regime_align_enabled", True),
        strategy_matrix_enabled=_b("phase_b_strategy_matrix_enabled", True),
        live_vs_research_enabled=_b("phase_b_live_vs_research_enabled", True),
        explain_journal_enabled=_b("phase_b_explain_journal_enabled", True),
        post_trade_review_enabled=_b("phase_b_post_trade_review_enabled", True),
        research_integrity_prep_enabled=_b(
            "phase_b_research_integrity_prep_enabled", True
        ),
        model_monitor_prep_enabled=_b("phase_b_model_monitor_prep_enabled", True),
        min_sample_trades=_i("phase_b_min_sample_trades", 20),
    )
