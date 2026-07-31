"""Bridge / runtime hooks for RC1 validation execution modes.

Safe observe + paper/shadow intercept. Never changes strategy or floors.
"""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.rc1_production_validation.config import (
    ValidationExecutionMode,
    resolve_validation_runtime,
)
from app.domain.institutional_trading.rc1_production_validation.paper_engine import (
    get_paper_engine,
)
from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
    get_shadow_journal,
)
from app.domain.institutional_trading.rc1_production_validation.trade_record import (
    TradeRecord,
)
from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
    get_trade_recorder,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _safe_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _decision_fields(decision: Any) -> dict[str, Any]:
    action = getattr(decision, "action", None)
    side = str(getattr(action, "value", action) or "").lower()
    entry = None
    sl = None
    tp = None
    stop = getattr(decision, "stop_zone", None)
    target = getattr(decision, "target_zone", None)
    if side == "buy":
        entry = getattr(decision, "entry_price", None) or getattr(
            decision, "mid_price", None
        )
        if stop is not None:
            sl = getattr(stop, "low", None)
        if target is not None:
            tp = getattr(target, "high", None)
    elif side == "sell":
        entry = getattr(decision, "entry_price", None) or getattr(
            decision, "mid_price", None
        )
        if stop is not None:
            sl = getattr(stop, "high", None)
        if target is not None:
            tp = getattr(target, "low", None)
    regime = ""
    snap = getattr(decision, "snapshot", None)
    if snap is not None:
        trend = getattr(snap, "trend", None)
        if trend is not None:
            regime = str(
                getattr(trend, "regime", None) or getattr(trend, "state", None) or ""
            )
    session = ""
    if snap is not None:
        sess = getattr(snap, "session", None)
        session_val = getattr(sess, "session", None) if sess else None
        session = str(getattr(session_val, "value", None) or session_val or "")
    return {
        "symbol": str(getattr(decision, "symbol", None) or ""),
        "side": side,
        "quality": getattr(decision, "quality", None),
        "confidence": getattr(decision, "confidence", None),
        "entry": entry,
        "stop_loss": sl,
        "take_profit": tp,
        "risk_reward": getattr(decision, "estimated_rr", None),
        "lots": getattr(decision, "approved_lots", None),
        "regime": regime,
        "session": session,
        "decision_id": str(getattr(decision, "id", "") or ""),
        "risk_score": getattr(decision, "risk_score", None),
    }


def record_decision_outcome(
    *,
    decision: Any,
    accepted: bool,
    reason_accepted: str = "",
    reason_rejected: str = "",
    order_payload: dict[str, Any] | None = None,
    broker_request: dict[str, Any] | None = None,
    broker_response: dict[str, Any] | None = None,
    expected_execution: dict[str, Any] | None = None,
    fill: dict[str, Any] | None = None,
    oms_latency_ms: float | None = None,
    ai_latency_ms: float | None = None,
    gateway_latency_ms: float | None = None,
    portfolio_allocation: str | None = None,
    execution_mode: str | None = None,
) -> TradeRecord | None:
    """Persist one trade journal row. Swallow errors — never affect trading."""
    try:
        cfg = resolve_validation_runtime()
        if not cfg.enabled and execution_mode is None:
            # Still allow explicit recorder use from replay/tests
            pass
        fields = _decision_fields(decision)
        mode = execution_mode or cfg.execution_mode.value
        trade = TradeRecord(
            symbol=fields["symbol"],
            market_regime=str(fields["regime"] or ""),
            session=str(fields["session"] or ""),
            quality=(int(fields["quality"]) if fields["quality"] is not None else None),
            confidence=(
                int(fields["confidence"]) if fields["confidence"] is not None else None
            ),
            risk_profile=_safe_str(fields["risk_score"]) or "",
            entry=_safe_str(fields["entry"]),
            stop_loss=_safe_str(fields["stop_loss"]),
            take_profit=_safe_str(fields["take_profit"]),
            risk_reward=_safe_str(fields["risk_reward"]),
            expected_lot_size=_safe_str(fields["lots"]),
            portfolio_allocation=portfolio_allocation,
            reason_accepted=reason_accepted,
            reason_rejected=reason_rejected,
            accepted=accepted,
            oms_latency_ms=oms_latency_ms,
            ai_latency_ms=ai_latency_ms,
            gateway_latency_ms=gateway_latency_ms,
            execution_mode=mode,
            order_payload=dict(order_payload or {}),
            broker_request=dict(broker_request or {}),
            broker_response=dict(broker_response or {}),
            expected_execution=dict(expected_execution or {}),
            fill=dict(fill or {}),
        )
        return get_trade_recorder().record(trade)
    except Exception:
        logger.exception("rc1_record_decision_outcome_failed")
        return None


def handle_validation_execution(
    *,
    decision: Any,
    intent: Any,
    latency_ms: float | None = None,
) -> dict[str, Any] | None:
    """If validation paper/shadow is active, handle without MT5 submit.

    Returns a result dict when intercepted; None when live / disabled.
    """
    try:
        cfg = resolve_validation_runtime()
        if not cfg.enabled or not cfg.blocks_broker_submit:
            return None

        if hasattr(intent, "to_dict"):
            payload = intent.to_dict()
        else:
            payload = {"intent": str(intent)}
        side = str(payload.get("side") or "").lower()
        broker_request = {
            "action": "order_send",
            "payload": dict(payload),
            "would_submit": True,
            "submitted": False,
        }
        expected = {
            "symbol": payload.get("symbol"),
            "side": side,
            "volume": payload.get("volume"),
            "sl": payload.get("stop_loss"),
            "tp": payload.get("take_profit"),
            "mode": cfg.execution_mode.value,
        }

        fill_info: dict[str, Any] = {}
        if cfg.execution_mode is ValidationExecutionMode.PAPER:
            paper = get_paper_engine()
            entry_px: Any = payload.get("price")
            if entry_px in (None, "", 0, "0"):
                try:
                    sl = float(payload.get("stop_loss") or 0)
                    tp = float(payload.get("take_profit") or 0)
                    if sl and tp:
                        entry_px = (sl + tp) / 2.0
                except (TypeError, ValueError):
                    entry_px = 0
            fill_info = paper.simulate_fill(
                symbol=str(payload.get("symbol") or ""),
                side=side or "buy",
                entry=entry_px or 0,
                stop_loss=payload.get("stop_loss") or 0,
                take_profit=payload.get("take_profit") or 0,
                lots=payload.get("volume") or 0.01,
                fill_price=entry_px,
            )
            reason = "paper_simulated_fill"
            broker_response = {"status": "simulated", "mode": "paper"}
        else:
            shadow = get_shadow_journal()
            shadow.record(
                order_payload=dict(payload),
                broker_request=broker_request,
                broker_response={"status": "not_sent", "mode": "shadow"},
                expected_execution=expected,
                symbol=str(payload.get("symbol") or ""),
                decision_id=str(getattr(decision, "id", "") or ""),
            )
            reason = "shadow_recorded_not_sent"
            broker_response = {"status": "not_sent", "mode": "shadow"}

        record_decision_outcome(
            decision=decision,
            accepted=True,
            reason_accepted=reason,
            order_payload=dict(payload),
            broker_request=broker_request,
            broker_response=broker_response,
            expected_execution=expected,
            fill=fill_info,
            oms_latency_ms=latency_ms,
            execution_mode=cfg.execution_mode.value,
        )
        return {
            "intercepted": True,
            "execution_mode": cfg.execution_mode.value,
            "forwarded_to_oms": False,
            "broker_submitted": False,
            "fill": fill_info,
            "order_payload": payload,
            "broker_request": broker_request,
            "message": reason,
        }
    except Exception:
        logger.exception("rc1_handle_validation_execution_failed")
        return None
