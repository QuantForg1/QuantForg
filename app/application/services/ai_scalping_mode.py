"""Apply / inspect AI Scalping Mode on the live ITE runtime."""

from __future__ import annotations

from dataclasses import replace
from typing import Any

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    scalping_ite_config,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.management.config import (
    DEFAULT_PME_CONFIG,
    PositionManagementConfig,
)
from core.logging import get_logger

logger = get_logger(__name__)


def pme_config_for_scalping(
    scalp: AiScalpingConfig | None = None,
) -> PositionManagementConfig:
    cfg = scalp or DEFAULT_AI_SCALPING_CONFIG
    return replace(
        DEFAULT_PME_CONFIG,
        config_version=f"{DEFAULT_PME_CONFIG.config_version}+scalping",
        break_even_at_r=cfg.break_even_at_r,
        partial_at_r=cfg.partial_at_r,
        partial_close_pct=cfg.partial_close_pct,
        trail_after_r=cfg.trail_after_r,
        volume_step=cfg.broker_lot_step,
        min_volume=cfg.broker_min_lot,
    )


def apply_trading_mode_to_runtime(
    runtime: Any,
    *,
    mode: str,
    scalp: AiScalpingConfig | None = None,
) -> dict[str, Any]:
    """Switch ITE decision + PME knobs between swing, scalping, and alpha."""
    mode_l = (mode or "swing").strip().lower()
    if mode_l not in {"swing", "scalping", "alpha"}:
        raise ValueError("trading_mode must be 'swing', 'scalping', or 'alpha'")

    from app.application.services.institutional_alpha_engine import set_alpha_enabled

    if mode_l == "scalping":
        ite = scalping_ite_config(DEFAULT_ITE_CONFIG, scalp=scalp)
        pme = pme_config_for_scalping(scalp)
        set_alpha_enabled(False)
    elif mode_l == "alpha":
        # Alpha uses scalping-style MTF for speed + multi-symbol scanner
        ite = scalping_ite_config(DEFAULT_ITE_CONFIG, scalp=scalp)
        from dataclasses import replace as _replace

        ite = _replace(
            ite,
            trading_mode="alpha",
            config_version=f"{ite.config_version}+alpha",
            max_open_trades=max(3, ite.max_open_trades),
        )
        pme = pme_config_for_scalping(scalp)
        set_alpha_enabled(True)
    else:
        ite = DEFAULT_ITE_CONFIG
        pme = DEFAULT_PME_CONFIG
        set_alpha_enabled(False)

    if runtime is not None:
        runtime.decision_pipeline.config = ite
        from app.application.services.institutional_decision_pipeline import (
            risk_config_from_ite,
        )
        from app.application.services.risk_engine import RiskEngine

        runtime.decision_pipeline.risk_engine = RiskEngine(
            config=risk_config_from_ite(ite)
        )
        if hasattr(runtime.position_management, "engine") and hasattr(
            runtime.position_management.engine, "config"
        ):
            runtime.position_management.engine.config = pme
        logger.warning(
            "trading_mode_applied",
            mode=mode_l,
            ite_version=ite.config_version,
            max_open=ite.max_open_trades,
            tfs=[t.value for t in ite.analysis_timeframes()],
        )

    return {
        "trading_mode": mode_l,
        "ite": ite.to_dict(),
        "pme": pme.to_dict(),
        "ai_scalping": (scalp or DEFAULT_AI_SCALPING_CONFIG).to_dict()
        if mode_l in {"scalping", "alpha"}
        else None,
        "alpha_enabled": mode_l == "alpha",
    }


def current_mode_snapshot(runtime: Any) -> dict[str, Any]:
    ite: ITEConfig = DEFAULT_ITE_CONFIG
    ai_score = None
    if runtime is not None:
        ite = getattr(runtime.decision_pipeline, "config", DEFAULT_ITE_CONFIG)
        getter = getattr(runtime.decision_pipeline, "last_ai_score", None)
        if callable(getter):
            ai_score = getter()
    learning = None
    try:
        from app.domain.institutional_trading.ai_scalping.learning import (
            get_scalping_learning_store,
        )

        learning = get_scalping_learning_store().summary()
    except Exception:
        learning = None
    return {
        "trading_mode": getattr(ite, "trading_mode", "swing"),
        "ite": ite.to_dict() if hasattr(ite, "to_dict") else {},
        "ai_score": ai_score,
        "ai_scalping_config": DEFAULT_AI_SCALPING_CONFIG.to_dict()
        if getattr(ite, "is_scalping", lambda: False)()
        else None,
        "learning": learning,
    }
