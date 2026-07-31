"""Named institutional risk aggression profiles.

Profiles set configured ceilings only. Dynamic sizing still requires
exceptional quality + full market/portfolio conditions to use the max.
Weak setups remain rejected. Broker / DD / news / AI gates stay intact.
"""

from __future__ import annotations

from dataclasses import replace
from decimal import Decimal
from threading import RLock
from typing import Literal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
)

RiskAggressionProfileId = Literal["STANDARD", "ULTRA_AGGRESSIVE"]

VALID_RISK_PROFILES: frozenset[str] = frozenset({"STANDARD", "ULTRA_AGGRESSIVE"})

# Hard absolute ceilings by profile — never silently raise beyond these.
_PROFILE_RISK_CEILING: dict[str, Decimal] = {
    "STANDARD": Decimal("0.75"),
    "ULTRA_AGGRESSIVE": Decimal("8.00"),
}

_LOCK = RLock()
_ACTIVE_CONFIG: AiScalpingConfig | None = None


def normalize_risk_profile_id(profile_id: str | None) -> RiskAggressionProfileId:
    raw = (profile_id or "STANDARD").strip().upper().replace("-", "_")
    if raw in {"ULTRA", "ULTRA_AGGRESSIVE"}:
        return "ULTRA_AGGRESSIVE"
    return "STANDARD"


def max_risk_ceiling_for_profile(profile_id: str | None) -> Decimal:
    pid = normalize_risk_profile_id(profile_id)
    return _PROFILE_RISK_CEILING[pid]


def ultra_aggressive_ai_scalping_config(
    *,
    base: AiScalpingConfig | None = None,
) -> AiScalpingConfig:
    """Production ULTRA_AGGRESSIVE profile — high ceilings, quality still gates."""
    src = base or DEFAULT_AI_SCALPING_CONFIG
    return replace(
        src,
        risk_profile_id="ULTRA_AGGRESSIVE",
        risk_per_trade_pct=Decimal("8.00"),
        max_daily_exposure_pct=Decimal("20.00"),
        max_symbol_exposure_pct=Decimal("8.00"),
        max_correlated_exposure_pct=Decimal("16.00"),
        max_sector_exposure_pct=Decimal("16.00"),
        max_currency_exposure_pct=Decimal("20.00"),
        max_open_trades=10,
        max_positions_per_symbol=5,
        pyramid_winners_only=True,
        dynamic_sizing_v2_enabled=True,
        portfolio_risk_engine_v2_enabled=True,
        # Margin headroom must accommodate larger risk — still a hard gate
        max_margin_usage_pct=Decimal("60"),
        # Keep quality floors unchanged — never weaken AI filters
        risk_increase_locked=False,
    )


def ai_scalping_config_for_profile(
    profile_id: str | None,
    *,
    base: AiScalpingConfig | None = None,
    compounding_enabled: bool | None = None,
) -> AiScalpingConfig:
    """Resolve named profile onto an AiScalpingConfig."""
    pid = normalize_risk_profile_id(profile_id)
    src = base or DEFAULT_AI_SCALPING_CONFIG
    if pid == "ULTRA_AGGRESSIVE":
        cfg = ultra_aggressive_ai_scalping_config(base=src)
    else:
        cfg = replace(src, risk_profile_id="STANDARD")
    if compounding_enabled is not None:
        cfg = replace(cfg, compounding_enabled=bool(compounding_enabled))
    return cfg


def set_active_ai_scalping_config(config: AiScalpingConfig) -> AiScalpingConfig:
    """Install process-scoped active scalp config used by the decision pipeline."""
    global _ACTIVE_CONFIG
    with _LOCK:
        _ACTIVE_CONFIG = config
        return _ACTIVE_CONFIG


def get_active_ai_scalping_config() -> AiScalpingConfig:
    """Return active scalp config, hydrating from ops plane when unset."""
    global _ACTIVE_CONFIG
    with _LOCK:
        if _ACTIVE_CONFIG is not None:
            return _ACTIVE_CONFIG
    # Lazy hydrate from control plane (restart continuity)
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        plane = get_control_plane()
        pid = getattr(plane, "risk_profile_id", "STANDARD")
        compounding = bool(getattr(plane, "compounding_enabled", False))
        cfg = ai_scalping_config_for_profile(
            pid, compounding_enabled=compounding
        )
    except Exception:
        cfg = DEFAULT_AI_SCALPING_CONFIG
    with _LOCK:
        if _ACTIVE_CONFIG is None:
            _ACTIVE_CONFIG = cfg
        return _ACTIVE_CONFIG


def apply_risk_profile(
    profile_id: str | None,
    *,
    compounding_enabled: bool | None = None,
) -> AiScalpingConfig:
    """Resolve + install named profile as the active scalp config."""
    cfg = ai_scalping_config_for_profile(
        profile_id, compounding_enabled=compounding_enabled
    )
    return set_active_ai_scalping_config(cfg)


def profile_summary(profile_id: str | None) -> dict[str, object]:
    cfg = ai_scalping_config_for_profile(profile_id)
    return {
        "risk_profile_id": cfg.risk_profile_id,
        "risk_per_trade_pct": str(cfg.risk_per_trade_pct),
        "max_daily_exposure_pct": str(cfg.max_daily_exposure_pct),
        "max_symbol_exposure_pct": str(cfg.max_symbol_exposure_pct),
        "max_correlated_exposure_pct": str(cfg.max_correlated_exposure_pct),
        "max_open_trades": cfg.max_open_trades,
        "max_positions_per_symbol": cfg.max_positions_per_symbol,
        "pyramid_winners_only": cfg.pyramid_winners_only,
        "dynamic_sizing_v2_enabled": cfg.dynamic_sizing_v2_enabled,
        "portfolio_risk_engine_v2_enabled": cfg.portfolio_risk_engine_v2_enabled,
        "max_risk_ceiling_pct": str(max_risk_ceiling_for_profile(cfg.risk_profile_id)),
        "quality_floors_unchanged": True,
        "never_force_broker_min_lot": True,
        "scaling_enabled": True,
        "winner_pyramiding": cfg.pyramid_winners_only,
    }


def news_risk_multiplier_for_snapshot(
    *,
    news_blocked: bool,
    news_reason: str | None,
    config: AiScalpingConfig | None = None,
) -> Decimal:
    """Map news protection status to a reduce-only risk multiplier."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    if news_blocked:
        return Decimal("0")
    reason = (news_reason or "").strip().lower()
    if "medium" in reason or "elevated" in reason:
        return min(Decimal("1"), max(Decimal("0"), cfg.news_medium_risk_mult))
    return Decimal("1")
