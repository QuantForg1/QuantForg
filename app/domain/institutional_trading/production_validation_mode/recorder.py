"""In-memory Production Validation recorder — thread-safe, observe-only."""

from __future__ import annotations

from contextvars import ContextVar, Token
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.domain.institutional_trading.production_validation_mode.models import (
    ACCEPTANCE_STAGES,
    PIPELINE_ORDER,
    GatewayRecord,
    Mt5Record,
    OmsRecord,
    StageRecord,
    StageStatus,
    ValidationAttempt,
    ValidationStage,
)

_current_validation_id: ContextVar[str | None] = ContextVar(
    "pvm_validation_id", default=None
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_dict(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return value.to_dict()
        except Exception:
            return str(value)
    if isinstance(value, (dict, list, str, int, float, bool)):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return str(value)


class ProductionValidationRecorder:
    """Assigns Validation IDs and captures stage / OMS / Gateway / MT5 evidence."""

    def __init__(self, *, max_attempts: int = 200) -> None:
        self._lock = Lock()
        self._max_attempts = max(20, int(max_attempts))
        self._attempts: dict[str, ValidationAttempt] = {}
        self._order: list[str] = []
        self._current_id: str | None = None
        self._dashboard: dict[str, Any] = {
            "current_session": "—",
            "execution_state": "—",
            "last_signal": "—",
            "last_quality": None,
            "current_blocker": None,
            "gateway_status": "UNKNOWN",
            "oms_status": "UNKNOWN",
            "mt5_status": "UNKNOWN",
            "broker_status": "UNKNOWN",
            "last_validation_id": None,
        }

    def begin(
        self,
        *,
        symbol: str = "",
        market_session: str = "",
        execution_mode: str = "",
        signal_id: str | None = None,
    ) -> ValidationAttempt:
        attempt = ValidationAttempt(
            symbol=symbol or "",
            market_session=market_session or "",
            execution_mode=execution_mode or "",
            signal_id=signal_id,
        )
        with self._lock:
            self._attempts[attempt.validation_id] = attempt
            self._order.append(attempt.validation_id)
            self._current_id = attempt.validation_id
            while len(self._order) > self._max_attempts:
                old = self._order.pop(0)
                self._attempts.pop(old, None)
            self._dashboard["last_validation_id"] = attempt.validation_id
            if market_session:
                self._dashboard["current_session"] = market_session
            if execution_mode:
                self._dashboard["execution_state"] = execution_mode
        return attempt

    def bind_context(self, validation_id: str | None) -> Token[str | None]:
        return _current_validation_id.set(validation_id)

    def unbind_context(self, token: Token[str | None]) -> None:
        _current_validation_id.reset(token)

    def current_id(self) -> str | None:
        ctx = _current_validation_id.get()
        if ctx:
            return ctx
        with self._lock:
            return self._current_id

    def get(self, validation_id: str | None = None) -> ValidationAttempt | None:
        vid = validation_id or self.current_id()
        if not vid:
            return None
        with self._lock:
            return self._attempts.get(vid)

    def record_stage(
        self,
        stage: ValidationStage | str,
        *,
        status: StageStatus | str,
        reason: str = "",
        latency_ms: float | None = None,
        validation_id: str | None = None,
        timestamp: str | None = None,
    ) -> None:
        vid = validation_id or self.current_id()
        if not vid:
            return
        stage_enum = (
            stage if isinstance(stage, ValidationStage) else ValidationStage(str(stage))
        )
        status_enum = (
            status if isinstance(status, StageStatus) else StageStatus(str(status))
        )
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None or attempt.closed:
                return
            attempt.stages[stage_enum.value] = StageRecord(
                stage=stage_enum,
                status=status_enum,
                timestamp=timestamp or _now_iso(),
                latency_ms=latency_ms,
                reason=reason or "",
            )
            if status_enum is StageStatus.FAIL and not attempt.first_blocker:
                attempt.first_blocker = f"{stage_enum.value}: {reason or 'FAIL'}"
                self._dashboard["current_blocker"] = attempt.first_blocker

    def capture_signal(
        self,
        *,
        snapshot: Any = None,
        decision: Any = None,
        validation_id: str | None = None,
        execution_mode: str | None = None,
    ) -> None:
        vid = validation_id or self.current_id()
        if not vid:
            return
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None or attempt.closed:
                return
            if execution_mode:
                attempt.execution_mode = execution_mode
                self._dashboard["execution_state"] = execution_mode
            if snapshot is not None:
                attempt.symbol = str(
                    getattr(snapshot, "symbol", None) or attempt.symbol or ""
                )
                session = getattr(snapshot, "session", None)
                session_val = getattr(session, "session", None) if session else None
                attempt.market_session = str(
                    getattr(session_val, "value", None)
                    or session_val
                    or attempt.market_session
                    or ""
                )
                self._dashboard["current_session"] = attempt.market_session or "—"
                if getattr(snapshot, "spread", None) is not None:
                    attempt.spread = str(snapshot.spread)
                if getattr(snapshot, "atr", None) is not None:
                    attempt.atr = str(snapshot.atr)
                attempt.liquidity = _safe_dict(getattr(snapshot, "liquidity", None))
                attempt.order_blocks = _safe_dict(
                    getattr(snapshot, "order_blocks", None)
                )
                attempt.fvg = _safe_dict(getattr(snapshot, "fair_value_gaps", None))
                structure = getattr(snapshot, "primary_structure", None)
                if structure is not None:
                    bos = getattr(structure, "breaks_of_structure", None)
                    choch = getattr(structure, "changes_of_character", None)
                    attempt.bos = _safe_dict(bos)
                    attempt.choch = _safe_dict(choch)
                trend = getattr(snapshot, "trend", None)
                if (
                    trend is not None
                    and getattr(trend, "alignment_score", None) is not None
                ):
                    attempt.mtf_alignment = int(trend.alignment_score)
                tq = getattr(snapshot, "trade_quality", None)
                if tq is not None:
                    tq_score = getattr(tq, "total", None)
                    if tq_score is None:
                        tq_score = getattr(tq, "score", None)
                    if tq_score is not None:
                        attempt.quality_score = int(tq_score)
                attempt.signal_id = attempt.signal_id or str(
                    getattr(snapshot, "id", "") or ""
                )
            if decision is not None:
                attempt.signal_id = attempt.signal_id or str(
                    getattr(decision, "id", "") or ""
                )
                attempt.symbol = str(
                    getattr(decision, "symbol", None) or attempt.symbol or ""
                )
                action = getattr(decision, "action", None)
                attempt.ai_action = str(getattr(action, "value", action) or "")
                attempt.ai_confidence = (
                    int(decision.confidence)
                    if getattr(decision, "confidence", None) is not None
                    else attempt.ai_confidence
                )
                if getattr(decision, "quality", None) is not None:
                    attempt.quality_score = int(decision.quality)
                if getattr(decision, "risk_score", None) is not None:
                    attempt.risk_score = int(decision.risk_score)
                if getattr(decision, "estimated_rr", None) is not None:
                    attempt.expected_rr = str(decision.estimated_rr)
                conf = getattr(decision, "confluence", None)
                if conf is not None:
                    if getattr(conf, "confidence", None) is not None:
                        attempt.confluence = int(conf.confidence)
                    factors = getattr(conf, "factors", None) or {}
                    if isinstance(factors, dict):
                        for key in ("mtf", "alignment", "mtf_alignment"):
                            if factors.get(key) is not None:
                                attempt.mtf_alignment = int(factors[key])
                                break
                self._dashboard["last_signal"] = attempt.ai_action or "—"
                self._dashboard["last_quality"] = attempt.quality_score

    def record_no_trade_reasons(
        self,
        reasons: list[str] | tuple[str, ...] | None,
        *,
        validation_id: str | None = None,
    ) -> None:
        """Persist every NO_TRADE reason individually — never summarize."""
        vid = validation_id or self.current_id()
        if not vid:
            return
        items = [str(r).strip() for r in (reasons or ()) if str(r).strip()]
        if not items:
            return
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None or attempt.closed:
                return
            seen = set(attempt.no_trade_reasons)
            for item in items:
                if item not in seen:
                    attempt.no_trade_reasons.append(item)
                    seen.add(item)

    def record_oms(
        self,
        *,
        payload: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        latency_ms: float | None = None,
        retry_count: int = 0,
        validation_id: str | None = None,
    ) -> None:
        vid = validation_id or self.current_id()
        if not vid:
            return
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None or attempt.closed:
                return
            existing = attempt.oms or OmsRecord()
            if payload is not None:
                existing.payload = dict(payload)
            if response is not None:
                existing.response = dict(response)
            if latency_ms is not None:
                existing.latency_ms = latency_ms
            existing.retry_count = int(retry_count or existing.retry_count or 0)
            attempt.oms = existing
            outcome = str((response or {}).get("outcome") or "").lower()
            if outcome in {"success", "filled", "ok"}:
                self._dashboard["oms_status"] = "PASS"
            elif response:
                self._dashboard["oms_status"] = "FAIL"
            else:
                self._dashboard["oms_status"] = "REACHED"

    def record_gateway(
        self,
        *,
        request: dict[str, Any] | None = None,
        response: dict[str, Any] | None = None,
        http_code: int | None = None,
        gateway_latency_ms: float | None = None,
        order_send_latency_ms: float | None = None,
        validation_id: str | None = None,
    ) -> None:
        vid = validation_id or self.current_id()
        if not vid:
            return
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None or attempt.closed:
                return
            existing = attempt.gateway or GatewayRecord()
            if request is not None:
                existing.request = dict(request)
            if response is not None:
                existing.response = dict(response)
            if http_code is not None:
                existing.http_code = http_code
            if gateway_latency_ms is not None:
                existing.gateway_latency_ms = gateway_latency_ms
            if order_send_latency_ms is not None:
                existing.order_send_latency_ms = order_send_latency_ms
            attempt.gateway = existing
            if http_code is not None and 200 <= int(http_code) < 300:
                self._dashboard["gateway_status"] = "PASS"
            elif http_code is not None:
                self._dashboard["gateway_status"] = "FAIL"
            else:
                self._dashboard["gateway_status"] = "REACHED"

    def record_mt5(
        self,
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
        vid = validation_id or self.current_id()
        if not vid:
            return
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None or attempt.closed:
                return
            existing = attempt.mt5 or Mt5Record()
            if ticket is not None:
                existing.ticket = int(ticket)
            if retcode is not None:
                existing.retcode = int(retcode)
            if comment:
                existing.comment = comment
            if execution_time_ms is not None:
                existing.execution_time_ms = execution_time_ms
            if fill_price is not None:
                existing.fill_price = str(fill_price)
            if slippage is not None:
                existing.slippage = str(slippage)
            if broker_response is not None:
                existing.broker_response = dict(broker_response)
            attempt.mt5 = existing
            # Common MT5 done/placed codes
            ok_codes = {10008, 10009, 10010}
            if existing.retcode in ok_codes and existing.ticket:
                self._dashboard["mt5_status"] = "PASS"
                self._dashboard["broker_status"] = "PASS"
            elif existing.retcode is not None:
                self._dashboard["mt5_status"] = "FAIL"
                self._dashboard["broker_status"] = "FAIL"
            else:
                self._dashboard["mt5_status"] = "REACHED"

    def classify_and_close(
        self, *, validation_id: str | None = None
    ) -> ValidationAttempt | None:
        """Accept only natural BUY/SELL with ticket through broker; else blocker."""
        vid = validation_id or self.current_id()
        if not vid:
            return None
        with self._lock:
            attempt = self._attempts.get(vid)
            if attempt is None:
                return None
            if attempt.closed:
                return attempt

            action = (attempt.ai_action or "").upper()
            ticket = attempt.mt5.ticket if attempt.mt5 else None
            stages_ok = True
            first_fail: str | None = None
            for stage in PIPELINE_ORDER:
                rec = attempt.stages.get(stage.value)
                if rec is None:
                    continue
                if rec.status is StageStatus.FAIL:
                    stages_ok = False
                    if first_fail is None:
                        first_fail = f"{stage.value}: {rec.reason or 'FAIL'}"
                    # Still scan for acceptance stages below
            acceptance_ok = True
            for stage in ACCEPTANCE_STAGES:
                rec = attempt.stages.get(stage.value)
                if rec is None or rec.status is not StageStatus.PASS:
                    acceptance_ok = False
                    if first_fail is None:
                        reason = rec.reason if rec else "not reached"
                        first_fail = f"{stage.value}: {reason}"
                    break

            ai_ok = action in {"BUY", "SELL"}
            ticket_ok = ticket is not None and int(ticket) > 0
            if acceptance_ok and ai_ok and ticket_ok and stages_ok:
                # Position Close may still be pending — acceptance is open ticket path
                pos_close = attempt.stages.get(ValidationStage.POSITION_CLOSE.value)
                if pos_close is not None and pos_close.status is StageStatus.FAIL:
                    attempt.accepted = False
                    attempt.final_result = "BLOCKED"
                    attempt.first_blocker = (
                        attempt.first_blocker
                        or f"Position Close: {pos_close.reason or 'FAIL'}"
                    )
                else:
                    attempt.accepted = True
                    attempt.final_result = "ACCEPTED"
                    attempt.first_blocker = None
                    self._dashboard["current_blocker"] = None
            else:
                attempt.accepted = False
                attempt.final_result = "BLOCKED"
                if not ai_ok and action in {"NO_TRADE", "WATCH", ""}:
                    # Prefer explicit NO_TRADE reasons as blocker detail
                    if attempt.no_trade_reasons and first_fail is None:
                        first_fail = f"AI: {attempt.no_trade_reasons[0]}"
                    elif first_fail is None:
                        first_fail = f"AI: action={action or 'NONE'} (not BUY/SELL)"
                attempt.first_blocker = attempt.first_blocker or first_fail
                self._dashboard["current_blocker"] = attempt.first_blocker

            self._dashboard["last_validation_id"] = attempt.validation_id
            self._dashboard["last_signal"] = attempt.ai_action or "—"
            self._dashboard["last_quality"] = attempt.quality_score
            attempt.closed = True
            return attempt

    def update_dashboard(self, **fields: Any) -> None:
        with self._lock:
            for key, value in fields.items():
                if value is not None:
                    self._dashboard[key] = value

    def dashboard(self) -> dict[str, Any]:
        with self._lock:
            last = None
            if self._order:
                last = self._attempts.get(self._order[-1])
            return {
                **dict(self._dashboard),
                "last_validation": last.to_dict() if last else None,
                "attempts_count": len(self._order),
                "observe_only": True,
                "never_modifies_trading": True,
                "never_fabricates_evidence": True,
            }

    def recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            ids = list(reversed(self._order))[: max(1, min(limit, 100))]
            return [self._attempts[i].to_dict() for i in ids if i in self._attempts]

    def report_summary(self, attempt: ValidationAttempt) -> dict[str, Any]:
        ticket = attempt.mt5.ticket if attempt.mt5 else None
        exec_lat = None
        if attempt.gateway and attempt.gateway.order_send_latency_ms is not None:
            exec_lat = attempt.gateway.order_send_latency_ms
        elif attempt.oms and attempt.oms.latency_ms is not None:
            exec_lat = attempt.oms.latency_ms
        pipeline_lines = []
        for stage in PIPELINE_ORDER:
            rec = attempt.stages.get(stage.value)
            if rec is None:
                continue
            pipeline_lines.append(
                {
                    "stage": stage.value,
                    "status": rec.status.value,
                    "latency_ms": rec.latency_ms,
                    "reason": rec.reason,
                }
            )
        return {
            "validation_id": attempt.validation_id,
            "pipeline_summary": pipeline_lines,
            "execution_latency_ms": exec_lat,
            "broker_ticket": ticket,
            "final_result": attempt.final_result,
            "accepted": attempt.accepted,
            "first_blocker": attempt.first_blocker,
            "ai_action": attempt.ai_action,
            "no_trade_reasons": list(attempt.no_trade_reasons),
        }


_RECORDER: ProductionValidationRecorder | None = None
_RECORDER_LOCK = Lock()


def get_production_validation_recorder() -> ProductionValidationRecorder:
    global _RECORDER
    with _RECORDER_LOCK:
        if _RECORDER is None:
            _RECORDER = ProductionValidationRecorder()
        return _RECORDER


def reset_production_validation_recorder_for_tests() -> ProductionValidationRecorder:
    global _RECORDER
    with _RECORDER_LOCK:
        _RECORDER = ProductionValidationRecorder()
        return _RECORDER
