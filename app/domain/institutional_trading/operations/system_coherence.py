"""Shared trading-system communication contract.

Does not authorize trades, call OMS, or invent a second execution path.
It standardizes identity, stage status, staleness, and current-vs-last
pipeline so UI/backend planes share one current truth.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.domain.trading.gold_only import (
    CANONICAL_GOLD_BROKER_DISPLAY,
    GOLD_SYMBOL,
    display_autonomous_symbol,
    is_gold_symbol,
)

READINESS_STAGES: tuple[str, ...] = (
    "MARKET",
    "STRATEGY",
    "DECISION",
    "SAFETY",
    "RISK",
    "SIZING",
    "PORTFOLIO",
    "OPTIMIZER",
    "OMS",
    "BROKER",
)


class StageStatus(StrEnum):
    PASS = "PASS"  # noqa: S105 — stage status, not a password
    WAIT = "WAIT"
    BLOCK = "BLOCK"
    NOT_REACHED = "NOT_REACHED"
    NOT_ASSESSED = "NOT_ASSESSED"
    DEGRADED = "DEGRADED"


class LifecycleState(StrEnum):
    MARKET_CONTEXT_NOT_READY = "MARKET_CONTEXT_NOT_READY"
    SETUP_FORMING = "SETUP_FORMING"
    SETUP_NOT_READY = "SETUP_NOT_READY"
    WAITING = "WAITING"
    CANDIDATE_READY = "CANDIDATE_READY"
    EXECUTION_READY = "EXECUTION_READY"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    ORDER_CHECKED = "ORDER_CHECKED"
    FILLED = "FILLED"
    POSITION_OPEN = "POSITION_OPEN"
    POSITION_CLOSING = "POSITION_CLOSING"
    RECONCILIATION = "RECONCILIATION"
    BLOCKED = "BLOCKED"
    TIMEOUT_NO_TRADE = "TIMEOUT_NO_TRADE"
    ERROR = "ERROR"


class FaultClass(StrEnum):
    HARD_BLOCK = "HARD_BLOCK"
    SOFT_WAIT = "SOFT_WAIT"
    CANDIDATE_BLOCK = "CANDIDATE_BLOCK"
    SYSTEM_BLOCK = "SYSTEM_BLOCK"
    RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
    DEGRADED = "DEGRADED"
    NON_BLOCKING = "NON_BLOCKING"
    STALE_STATE = "STALE_STATE"
    CONFIGURATION_ERROR = "CONFIGURATION_ERROR"
    NONE = "NONE"


class Plane(StrEnum):
    CURRENT_SCAN = "CURRENT_SCAN"
    LAST_PIPELINE = "LAST_COMPLETED_ITE_CYCLE"
    DECISION_INTELLIGENCE = "DECISION_INTELLIGENCE"
    EXECUTION_CONTRACT = "EXECUTION_CONTRACT"
    HEALTH = "HEALTH"


_IGNORED_ACTION_TOKENS = frozenset(
    {"ignored_action", "ignored action", "no_trade", "watch"}
)


def utc_now() -> datetime:
    return datetime.now(UTC)


def utc_stamp(value: datetime | None = None) -> str:
    stamp = value or utc_now()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return stamp.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def symbol_identity(code: str | None) -> tuple[str, str]:
    """Return (logical_symbol, canonical_symbol). Gold-only → XAUUSD / XAUUSD_i."""
    raw = str(code or "").strip()
    if not raw or is_gold_symbol(raw):
        return GOLD_SYMBOL, display_autonomous_symbol(
            raw or CANONICAL_GOLD_BROKER_DISPLAY
        )
    upper = raw.upper()
    return upper, raw


def is_ignored_action_token(value: Any) -> bool:
    raw = str(value or "").strip().lower().replace("-", " ").replace("_", " ")
    if not raw:
        return False
    if raw in _IGNORED_ACTION_TOKENS:
        return True
    return raw.startswith("ignored action")


def engine_bool_to_status(value: bool | None) -> StageStatus:
    """Typed engine result. None is NOT_ASSESSED, never PASS or BLOCK."""
    if value is True:
        return StageStatus.PASS
    if value is False:
        return StageStatus.BLOCK
    return StageStatus.NOT_ASSESSED


def typed_engine_status(value: bool | None) -> str:
    if value is True:
        return StageStatus.PASS.value
    if value is False:
        return StageStatus.BLOCK.value
    return StageStatus.NOT_ASSESSED.value


def sanitize_next_action(
    *,
    focus: str | None,
    next_action: str | None,
    direction: str | None = None,
) -> str:
    """Forbid ignored_action and NONE + WAIT_SAME_FOCUS."""
    action = str(next_action or "").strip().upper() or "WAITING"
    if is_ignored_action_token(action):
        action = "WAITING"
    focus_ok = bool(str(focus or "").strip()) and str(focus).upper() not in {
        "NONE",
        "NULL",
        "-",
    }
    if action == "WAIT_SAME_FOCUS" and not focus_ok:
        return "NO_EXECUTABLE_FOCUS"
    if str(direction or "").upper() == "NONE" and action == "WAIT_SAME_FOCUS":
        return "NO_EXECUTABLE_FOCUS"
    return action


def market_status_from_scan(
    *,
    has_current_scan: bool,
    scan_valid: bool,
    scan_stale: bool,
    market_hard_fail: bool,
) -> str:
    """Current scan present ≠ market FAIL. Missing scan ≠ market failed."""
    if market_hard_fail:
        return StageStatus.BLOCK.value
    if not has_current_scan:
        return StageStatus.NOT_REACHED.value
    if scan_stale:
        return StageStatus.WAIT.value
    if scan_valid:
        return StageStatus.PASS.value
    return StageStatus.WAIT.value


def lifecycle_from_scan(
    *,
    has_current_scan: bool,
    eligible: bool,
    execution_ready: bool,
    execution_authorized: bool,
) -> str:
    if execution_authorized:
        return LifecycleState.EXECUTION_AUTHORIZED.value
    if execution_ready:
        return LifecycleState.EXECUTION_READY.value
    if eligible:
        return LifecycleState.CANDIDATE_READY.value
    if has_current_scan:
        return LifecycleState.SETUP_NOT_READY.value
    return LifecycleState.MARKET_CONTEXT_NOT_READY.value


@dataclass
class CycleEvent:
    event_id: str
    parent_event_id: str | None
    event_type: str
    source: str
    plane: str
    cycle_id: str
    snapshot_id: str
    sequence: int
    symbol: str
    timestamp: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "parent_event_id": self.parent_event_id,
            "event_type": self.event_type,
            "source": self.source,
            "plane": self.plane,
            "cycle_id": self.cycle_id,
            "snapshot_id": self.snapshot_id,
            "sequence": self.sequence,
            "symbol": self.symbol,
            "timestamp": self.timestamp,
            "payload": dict(self.payload),
        }


class InFlightDedupe:
    """Share in-flight results so one cycle does not fetch the same key twice."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._inflight: dict[str, float] = {}
        self._results: dict[str, Any] = {}

    def acquire(self, key: str) -> bool:
        with self._lock:
            if key in self._inflight or key in self._results:
                return False
            self._inflight[key] = time.monotonic()
            return True

    def complete(self, key: str, result: Any) -> None:
        with self._lock:
            self._inflight.pop(key, None)
            self._results[key] = result

    def get(self, key: str) -> Any:
        with self._lock:
            return self._results.get(key)

    def reset(self) -> None:
        with self._lock:
            self._inflight.clear()
            self._results.clear()


class CoherenceStore:
    """Newer sequence wins. Older snapshots never overwrite newer plane state."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._planes: dict[str, dict[str, Any]] = {}
        self._seq: dict[str, int] = {}
        self._events: list[dict[str, Any]] = []
        self.cycle_id: str = f"cycle-{uuid.uuid4().hex[:12]}"
        self.global_seq: int = 0

    def new_cycle(self) -> str:
        with self._lock:
            self.cycle_id = f"cycle-{uuid.uuid4().hex[:12]}"
            self.global_seq = 0
            self._planes.clear()
            self._seq.clear()
            self._events.clear()
            return self.cycle_id

    def publish(
        self,
        plane: str,
        payload: dict[str, Any],
        *,
        sequence: int | None = None,
        source: str = "system",
        event_type: str = "state",
        parent_event_id: str | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            current_seq = int(self._seq.get(plane) or 0)
            incoming = int(sequence) if sequence is not None else current_seq + 1
            if incoming < current_seq:
                return {
                    "accepted": False,
                    "reason": "STALE_SEQUENCE",
                    "plane": plane,
                    "stored_sequence": current_seq,
                    "incoming_sequence": incoming,
                }
            self.global_seq += 1
            self._seq[plane] = incoming
            snapshot_id = f"{plane.lower()}-{incoming}"
            logical, canonical = symbol_identity(str(payload.get("symbol") or ""))
            body = dict(payload)
            body["label"] = plane
            body["logical_symbol"] = logical
            body["canonical_symbol"] = canonical
            body["cycle_id"] = self.cycle_id
            body["snapshot_id"] = snapshot_id
            body["sequence"] = incoming
            body["source"] = source
            body["as_of"] = body.get("as_of") or utc_stamp()
            body["age_ms"] = 0
            self._planes[plane] = body
            event = CycleEvent(
                event_id=str(uuid.uuid4()),
                parent_event_id=parent_event_id,
                event_type=event_type,
                source=source,
                plane=plane,
                cycle_id=self.cycle_id,
                snapshot_id=snapshot_id,
                sequence=incoming,
                symbol=canonical,
                timestamp=str(body["as_of"]),
                payload={"keys": sorted(body.keys())[:24]},
            )
            self._events.append(event.to_dict())
            self._events = self._events[-120:]
            return {"accepted": True, **body}

    def get(self, plane: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._planes.get(plane)
            return dict(row) if row else None

    def events(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._events)


_STORE = CoherenceStore()
_DEDUPE = InFlightDedupe()
_STORE_LOCK = threading.Lock()


def get_coherence_store() -> CoherenceStore:
    return _STORE


def get_request_dedupe() -> InFlightDedupe:
    return _DEDUPE


def reset_system_coherence() -> None:
    global _STORE, _DEDUPE
    with _STORE_LOCK:
        _STORE = CoherenceStore()
        _DEDUPE = InFlightDedupe()


def _empty_stages() -> dict[str, str]:
    return dict.fromkeys(READINESS_STAGES, StageStatus.NOT_REACHED.value)


def compose_system_snapshot(
    *,
    current_scan: dict[str, Any] | None,
    last_pipeline: dict[str, Any] | None,
    contract: dict[str, Any] | None = None,
    health: dict[str, Any] | None = None,
    decision_intelligence: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """One operator-facing truth. CURRENT_SCAN and LAST_PIPELINE never overwrite."""
    scan = dict(current_scan or {})
    last = dict(last_pipeline or {})
    contract = dict(contract or {})
    health = dict(health or {})
    di = dict(decision_intelligence or {})
    has_scan = bool(scan) and (
        str(scan.get("label") or "") == "CURRENT_SCAN"
        or bool(
            str(scan.get("current_scan_symbol") or scan.get("symbol") or "").strip()
        )
    )
    scan_symbol = str(
        scan.get("canonical_symbol")
        or scan.get("current_scan_symbol")
        or scan.get("symbol")
        or ""
    ).strip()
    logical, canonical = symbol_identity(scan_symbol or CANONICAL_GOLD_BROKER_DISPLAY)
    eligible = int(scan.get("eligible_count") or 0) > 0
    direction = str(
        (scan.get("best_candidate") or {}).get("direction")
        if isinstance(scan.get("best_candidate"), dict)
        else scan.get("direction")
        or ""
    ).upper() or "NONE"
    focus = str(scan.get("executable_focus") or scan_symbol or "").strip() or None
    next_action = sanitize_next_action(
        focus=focus,
        next_action=str(scan.get("next_action") or ""),
        direction=direction,
    )
    stages = _empty_stages()
    scan_stale = False
    as_of = str(scan.get("as_of") or "")
    if as_of:
        try:
            parsed = datetime.fromisoformat(as_of.replace("Z", "+00:00"))
            stamp = now or utc_now()
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
            scan_stale = (stamp - parsed.astimezone(UTC)).total_seconds() > 180
        except ValueError:
            scan_stale = False

    stages["MARKET"] = market_status_from_scan(
        has_current_scan=has_scan,
        scan_valid=bool(scan_symbol) and is_gold_symbol(scan_symbol or canonical),
        scan_stale=scan_stale,
        market_hard_fail=False,
    )
    if has_scan:
        stages["STRATEGY"] = (
            StageStatus.PASS.value if eligible else StageStatus.WAIT.value
        )
        stages["DECISION"] = (
            StageStatus.PASS.value if eligible else StageStatus.WAIT.value
        )
    # Last pipeline Safety/Optimizer are LAST, never current unless same cycle.
    last_safety = str(last.get("safety_state") or StageStatus.NOT_REACHED.value)
    last_opt = str(last.get("optimizer_state") or "NOT_RUN")
    stages["SAFETY"] = StageStatus.NOT_REACHED.value
    stages["OPTIMIZER"] = StageStatus.NOT_REACHED.value
    same_symbol = False
    last_sym = str(last.get("canonical_symbol") or last.get("symbol") or "")
    if last_sym and is_gold_symbol(last_sym) and is_gold_symbol(canonical):
        same_symbol = True
    last_as_of = str(last.get("as_of") or last.get("timestamp") or "")
    last_is_current = bool(same_symbol and last_as_of and as_of and last_as_of == as_of)
    if last_is_current:
        if last_safety.upper() == "PASS":
            stages["SAFETY"] = StageStatus.PASS.value
        elif last_safety.upper() in {"FAIL", "BLOCK"}:
            stages["SAFETY"] = StageStatus.BLOCK.value
        elif last_safety.upper() == "NOT_ASSESSED":
            stages["SAFETY"] = StageStatus.NOT_ASSESSED.value
        if last_opt.upper() in {"EXECUTE_NOW", "PASS"}:
            stages["OPTIMIZER"] = StageStatus.PASS.value
        elif last_opt.upper() not in {"NOT_RUN", ""}:
            stages["OPTIMIZER"] = StageStatus.WAIT.value

    if contract:
        c_stages = contract.get("stages")
        if isinstance(c_stages, dict):
            for name in READINESS_STAGES:
                raw = str(c_stages.get(name) or "").upper()
                if raw in {s.value for s in StageStatus}:
                    stages[name] = raw
        if contract.get("may_submit_oms") is True:
            stages["OMS"] = StageStatus.PASS.value

    di_risk = di.get("risk") if isinstance(di.get("risk"), dict) else {}
    di_safety = di.get("safety") if isinstance(di.get("safety"), dict) else {}
    risk_state = str(di_risk.get("state") or "")
    if risk_state in {s.value for s in StageStatus} or risk_state == "FAIL":
        stages["RISK"] = (
            StageStatus.BLOCK.value if risk_state == "FAIL" else risk_state
        )
    safety_state = str(di_safety.get("state") or "")
    if safety_state:
        stages["SAFETY"] = (
            StageStatus.BLOCK.value if safety_state == "FAIL" else safety_state
        )

    gateway_healthy = bool(health.get("gateway_connected") or health.get("healthy"))
    execution_ready = bool(contract.get("may_submit_oms")) and all(
        stages[s] == StageStatus.PASS.value for s in READINESS_STAGES
    )
    execution_authorized = execution_ready and str(direction) in {"BUY", "SELL"}
    lifecycle = lifecycle_from_scan(
        has_current_scan=has_scan,
        eligible=eligible,
        execution_ready=execution_ready,
        execution_authorized=execution_authorized,
    )
    if has_scan and lifecycle == LifecycleState.MARKET_CONTEXT_NOT_READY.value:
        lifecycle = LifecycleState.SETUP_NOT_READY.value

    fault_code = str(scan.get("fault_code") or "")
    if is_ignored_action_token(fault_code):
        fault_code = "NO_CURRENT_BLOCK"
    fault_reason = str(scan.get("fault_reason") or "")
    if is_ignored_action_token(fault_reason):
        fault_reason = str(scan.get("first_blocking_gate") or "NO_CURRENT_BLOCK")

    snapshot = {
        "cycle_id": scan.get("cycle_id") or last.get("cycle_id") or _STORE.cycle_id,
        "snapshot_id": scan.get("snapshot_id") or f"compose-{_STORE.global_seq}",
        "sequence": int(scan.get("sequence") or _STORE.global_seq or 0),
        "session_id": scan.get("session_id"),
        "logical_symbol": logical,
        "canonical_symbol": canonical,
        "symbol": canonical,
        "as_of": as_of or utc_stamp(now),
        "source": "system_coherence.compose",
        "age_ms": 0,
        "current_scan": scan or None,
        "last_pipeline": last or None,
        "planes_separate": True,
        "stages": stages,
        "direction": direction,
        "opportunity_score": (
            (scan.get("best_candidate") or {}).get("opportunity_score")
            if isinstance(scan.get("best_candidate"), dict)
            else scan.get("opportunity_score")
        ),
        "confidence": (
            (scan.get("best_candidate") or {}).get("confidence")
            if isinstance(scan.get("best_candidate"), dict)
            else scan.get("confidence")
        ),
        "quality": (
            (scan.get("best_candidate") or {}).get("quality")
            if isinstance(scan.get("best_candidate"), dict)
            else scan.get("quality")
        ),
        "blocking_stage": scan.get("blocking_stage") or "SCANNER",
        "fault_class": scan.get("fault_class") or FaultClass.SOFT_WAIT.value,
        "fault_code": fault_code or None,
        "fault_reason": fault_reason or None,
        "next_action": next_action,
        "execution_ready": execution_ready,
        "execution_authorized": execution_authorized,
        "execute_now_required": False,
        "lifecycle": lifecycle,
        "health": {
            "gateway_connected": gateway_healthy,
            "broker_connected": bool(health.get("broker_connected")),
            "note": "HEALTH is not EXECUTION AUTHORITY",
        },
        "last_pipeline_safety_state": last_safety,
        "last_pipeline_optimizer_state": last_opt,
        "current_safety_state": stages["SAFETY"],
        "current_optimizer_state": stages["OPTIMIZER"],
        "ignored_action": False,
        "roles": {
            "probability_center": "opportunity evidence only",
            "strategy": "strategy evidence",
            "decision": "interpret opportunity",
            "risk": "financial risk",
            "safety": "execution safety",
            "optimizer": "timing of authorized candidate",
            "oms": "application execution authority",
            "gateway": "broker transport",
        },
    }
    return snapshot
