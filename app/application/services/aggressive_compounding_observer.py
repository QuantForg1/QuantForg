"""Shadow-only compounding observer. Never calls OMS or broker mutations."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.institutional_trading.compounding.models import CompoundingInputs
from app.domain.institutional_trading.compounding.observe import (
    get_compounding_shadow_store,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except Exception:
        return None


def observe_aggressive_compounding_shadow(
    *,
    signal: dict[str, Any] | None = None,
    score: dict[str, Any] | None = None,
    forwarded_to_oms: bool = False,
    blocking_stage: str | None = None,
    fault_code: str | None = None,
    equity: Any = None,
    peak_equity: Any = None,
    daily_pnl: Any = None,
    daily_loss_pct: Any = None,
    open_positions: int = 0,
    quantforg_open_count: int = 0,
    remaining_capacity: int | None = None,
    configured_max_open: int = 10,
    exposure_pct: Any = None,
    free_margin: Any = None,
    risk_approved_volume: Any = None,
    same_symbol_blocked: bool = False,
    candidate_allowed: bool = True,
    cycle_id: str | None = None,
) -> dict[str, Any] | None:
    """Record a shadow compounding observation. Failures never abort the cycle."""
    try:
        sig = dict(signal or {})
        score_row = dict(score or {})
        rr = _dec(sig.get("expected_rr") or score_row.get("expected_rr"))
        inputs = CompoundingInputs(
            symbol=str(sig.get("symbol") or score_row.get("symbol") or ""),
            direction=str(sig.get("direction") or ""),
            trade_class=str(sig.get("trade_class") or "SCALP"),
            score=score_row,
            confidence=_int(sig.get("confidence") or score_row.get("ai_confidence")),
            quality=_int(
                sig.get("signal_quality")
                or sig.get("quality")
                or score_row.get("trade_quality")
            ),
            expected_rr=rr,
            equity=_dec(equity),
            peak_equity=_dec(peak_equity),
            daily_pnl=_dec(daily_pnl),
            daily_loss_pct=_dec(daily_loss_pct),
            open_positions=int(open_positions or 0),
            quantforg_open_count=int(quantforg_open_count or 0),
            remaining_capacity=remaining_capacity,
            configured_max_open=int(configured_max_open or 10),
            exposure_pct=_dec(exposure_pct),
            free_margin=_dec(free_margin),
            risk_approved_volume=_dec(risk_approved_volume) or _dec(
                sig.get("approved_lot")
            ),
            same_symbol_blocked=bool(same_symbol_blocked),
            candidate_allowed=bool(candidate_allowed),
            min_lot_classification=str(sig.get("min_lot_feasibility") or "") or None,
            forwarded_to_oms=bool(forwarded_to_oms),
            blocking_stage=blocking_stage,
            fault_code=fault_code,
            sequential_scale_in_live_enabled=False,
            cycle_id=cycle_id,
        )
        obs = get_compounding_shadow_store().observe(inputs)
        payload = obs.to_dict()
        logger.warning(
            "aggressive_compounding_shadow",
            live_activation=obs.live_activation,
            mutates_engines=False,
            mode=obs.mode,
            drawdown_state=obs.drawdown_state,
            compounding_bias=obs.compounding_bias,
            conviction_score=obs.conviction.conviction_score,
            effective_count=obs.counts.effective_count,
            suggested_volume=str(obs.sizing.suggested_volume),
            risk_approved_volume=str(obs.sizing.risk_approved_volume),
            scale_in_allowed=obs.scale_in.scale_in_allowed,
            scale_in_block_reason=obs.scale_in.scale_in_block_reason,
            forwarded_to_oms=bool(forwarded_to_oms),
        )
        return payload
    except Exception:
        logger.exception("aggressive_compounding_shadow_failed")
        return None
