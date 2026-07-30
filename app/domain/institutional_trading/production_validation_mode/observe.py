"""Safe observe-only hooks for Production Validation Mode.

Every public function swallows exceptions — never affects trading path.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Iterator

from app.domain.institutional_trading.production_validation_mode.export import (
    export_validation_report,
)
from app.domain.institutional_trading.production_validation_mode.models import (
    StageStatus,
    ValidationStage,
)
from app.domain.institutional_trading.production_validation_mode.recorder import (
    get_production_validation_recorder,
)
from core.logging import get_logger

logger = get_logger(__name__)


def begin_validation(
    *,
    symbol: str = "",
    market_session: str = "",
    execution_mode: str = "",
    signal_id: str | None = None,
) -> str | None:
    try:
        attempt = get_production_validation_recorder().begin(
            symbol=symbol,
            market_session=market_session,
            execution_mode=execution_mode,
            signal_id=signal_id,
        )
        return attempt.validation_id
    except Exception:
        logger.exception("pvm_begin_failed")
        return None


def ensure_validation(
    *,
    symbol: str = "",
    market_session: str = "",
    execution_mode: str = "",
    signal_id: str | None = None,
) -> str | None:
    """Reuse open ContextVar validation id, otherwise begin a new attempt."""
    try:
        recorder = get_production_validation_recorder()
        existing = recorder.current_id()
        if existing:
            attempt = recorder.get(existing)
            if attempt is not None and not attempt.closed:
                return existing
        return begin_validation(
            symbol=symbol,
            market_session=market_session,
            execution_mode=execution_mode,
            signal_id=signal_id,
        )
    except Exception:
        logger.exception("pvm_ensure_failed")
        return None


@contextmanager
def bind_validation(validation_id: str | None) -> Iterator[None]:
    token = None
    try:
        if validation_id:
            token = get_production_validation_recorder().bind_context(validation_id)
        yield
    except Exception:
        logger.exception("pvm_bind_failed")
        yield
    finally:
        try:
            if token is not None:
                get_production_validation_recorder().unbind_context(token)
        except Exception:
            logger.exception("pvm_unbind_failed")


def stage(
    name: ValidationStage | str,
    *,
    ok: bool,
    reason: str = "",
    latency_ms: float | None = None,
    validation_id: str | None = None,
    skip: bool = False,
) -> None:
    try:
        status = (
            StageStatus.SKIP
            if skip
            else (StageStatus.PASS if ok else StageStatus.FAIL)
        )
        get_production_validation_recorder().record_stage(
            name,
            status=status,
            reason=reason,
            latency_ms=latency_ms,
            validation_id=validation_id,
        )
    except Exception:
        logger.exception("pvm_stage_failed", stage=str(name))


def capture_signal(
    *,
    snapshot: Any = None,
    decision: Any = None,
    execution_mode: str | None = None,
    validation_id: str | None = None,
) -> None:
    try:
        get_production_validation_recorder().capture_signal(
            snapshot=snapshot,
            decision=decision,
            execution_mode=execution_mode,
            validation_id=validation_id,
        )
    except Exception:
        logger.exception("pvm_capture_signal_failed")


def record_decision_reasons(
    decision: Any,
    *,
    validation_id: str | None = None,
) -> None:
    """If AI returns NO_TRADE / WATCH, persist every reason individually."""
    try:
        action = getattr(decision, "action", None)
        action_s = str(getattr(action, "value", action) or "").upper()
        reasons: list[str] = []
        for r in tuple(getattr(decision, "reasons", ()) or ()):
            reasons.append(str(r))
        elig = getattr(decision, "eligibility", None)
        if elig is not None:
            for r in tuple(getattr(elig, "rejection_reasons", ()) or ()):
                reasons.append(str(r))
        for r in tuple(getattr(decision, "risk_reasons", ()) or ()):
            reasons.append(str(r))
        conf = getattr(decision, "confluence", None)
        if conf is not None:
            for r in tuple(getattr(conf, "rejected_rules", ()) or ()):
                reasons.append(str(r))
            for r in tuple(getattr(conf, "reasons", ()) or ()):
                # confluence reasons are informational; include when NO_TRADE
                if action_s in {"NO_TRADE", "WATCH"}:
                    reasons.append(str(r))
        if action_s in {"NO_TRADE", "WATCH"}:
            get_production_validation_recorder().record_no_trade_reasons(
                reasons, validation_id=validation_id
            )
        elif reasons and not getattr(elig, "eligible", True):
            get_production_validation_recorder().record_no_trade_reasons(
                reasons, validation_id=validation_id
            )
    except Exception:
        logger.exception("pvm_decision_reasons_failed")


def record_oms(
    *,
    payload: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    latency_ms: float | None = None,
    retry_count: int = 0,
    validation_id: str | None = None,
) -> None:
    try:
        get_production_validation_recorder().record_oms(
            payload=payload,
            response=response,
            latency_ms=latency_ms,
            retry_count=retry_count,
            validation_id=validation_id,
        )
    except Exception:
        logger.exception("pvm_oms_record_failed")


def record_gateway(
    *,
    request: dict[str, Any] | None = None,
    response: dict[str, Any] | None = None,
    http_code: int | None = None,
    gateway_latency_ms: float | None = None,
    order_send_latency_ms: float | None = None,
    validation_id: str | None = None,
) -> None:
    try:
        get_production_validation_recorder().record_gateway(
            request=request,
            response=response,
            http_code=http_code,
            gateway_latency_ms=gateway_latency_ms,
            order_send_latency_ms=order_send_latency_ms,
            validation_id=validation_id,
        )
    except Exception:
        logger.exception("pvm_gateway_record_failed")


def record_mt5(
    *,
    ticket: int | None = None,
    retcode: int | None = None,
    comment: str = "",
    execution_time_ms: float | None = None,
    fill_price: str | None = None,
    slippage: str | None = None,
    broker_response: dict[str, Any] | None = None,
    validation_id: str | None = None,
) -> None:
    try:
        get_production_validation_recorder().record_mt5(
            ticket=ticket,
            retcode=retcode,
            comment=comment,
            execution_time_ms=execution_time_ms,
            fill_price=fill_price,
            slippage=slippage,
            broker_response=broker_response,
            validation_id=validation_id,
        )
    except Exception:
        logger.exception("pvm_mt5_record_failed")


def finalize(
    *,
    validation_id: str | None = None,
    export: bool = True,
) -> dict[str, Any] | None:
    try:
        recorder = get_production_validation_recorder()
        attempt = recorder.classify_and_close(validation_id=validation_id)
        if attempt is None:
            return None
        if export:
            export_validation_report(attempt, recorder=recorder)
        return recorder.report_summary(attempt)
    except Exception:
        logger.exception("pvm_finalize_failed")
        return None


def update_live_status(**fields: Any) -> None:
    try:
        get_production_validation_recorder().update_dashboard(**fields)
    except Exception:
        logger.exception("pvm_dashboard_update_failed")


class StageTimer:
    """Simple latency helper for observe hooks."""

    def __init__(self) -> None:
        self._t0 = time.perf_counter()

    def ms(self) -> float:
        return round((time.perf_counter() - self._t0) * 1000.0, 2)
