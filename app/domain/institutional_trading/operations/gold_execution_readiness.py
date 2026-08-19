"""Gold execution readiness + 30-minute opportunity tracker (observability).

Does not authorize trades, change Safety/Risk/OMS, lower quality floors,
or retry order_send. Advisory / stale / UI-only states never halt a new entry.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.domain.institutional_trading.operations.execution_halt_policy import (
    HaltClass,
    classify_halt_condition,
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

_PIPELINE_ORDER: tuple[str, ...] = (
    "SCANNER",
    "MARKET",
    "STRATEGY",
    "DECISION",
    "SAFETY",
    "RISK",
    "SIZING",
    "PORTFOLIO",
    "OPTIMIZER",
    "OMS",
    "GATEWAY",
    "BROKER",
    "RECONCILIATION",
    "ADVISORY",
    "ELIGIBILITY",
)

# Current scan older than this is annotated stale — never treated as a hard block.
SCAN_STALE_SECONDS = 180.0


class StageStatus(StrEnum):
    PASS = "PASS"
    WAIT = "WAIT"
    BLOCK = "BLOCK"
    NOT_REACHED = "NOT_REACHED"


class TrackerState(StrEnum):
    MARKET_CONTEXT_NOT_READY = "MARKET_CONTEXT_NOT_READY"
    SETUP_FORMING = "SETUP_FORMING"
    SETUP_NOT_READY = "SETUP_NOT_READY"
    WAITING = "WAITING"
    READY = "READY"
    EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
    ORDER_SUBMITTED = "ORDER_SUBMITTED"
    FILLED = "FILLED"
    RECONCILIATION = "RECONCILIATION"
    POSITION_OPEN = "POSITION_OPEN"
    BLOCKED = "BLOCKED"
    TIMEOUT_NO_TRADE = "TIMEOUT_NO_TRADE"


class BarrierClass(StrEnum):
    AUTHORITATIVE_HARD_BLOCK = "AUTHORITATIVE_HARD_BLOCK"
    SOFT_WAIT = "SOFT_WAIT"
    CANDIDATE_BLOCK = "CANDIDATE_BLOCK"
    SYSTEM_BLOCK = "SYSTEM_BLOCK"
    RECONCILIATION_BLOCK = "RECONCILIATION_BLOCK"
    ADVISORY = "ADVISORY"
    DEGRADED = "DEGRADED"
    UI_ONLY = "UI_ONLY"
    DUPLICATE = "DUPLICATE"
    STALE_STATE = "STALE_STATE"
    CONFIG_MISMATCH = "CONFIG_MISMATCH"


def parse_as_of_age_seconds(
    as_of: str | None, *, now: datetime | None = None
) -> float | None:
    raw = str(as_of or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    stamp = now if now is not None else datetime.now(UTC)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=UTC)
    return max(0.0, (stamp - parsed).total_seconds())


def _status(value: str) -> str:
    upper = str(value or "").strip().upper()
    if upper in {s.value for s in StageStatus}:
        return upper
    return StageStatus.NOT_REACHED.value


def _stage_index(name: str | None) -> int:
    key = str(name or "SCANNER").strip().upper()
    if key == "GATEWAY":
        key = "BROKER"
    if key in _PIPELINE_ORDER:
        return _PIPELINE_ORDER.index(key)
    return 0


def classify_barrier(
    *,
    fault_class: str | None,
    fault_reason: str | None,
    blocking_stage: str | None,
) -> str:
    fc = str(fault_class or "").strip().upper()
    if fc == "ADVISORY":
        return BarrierClass.ADVISORY.value
    if fc == "SYSTEM_BLOCK":
        return BarrierClass.SYSTEM_BLOCK.value
    if fc == "CANDIDATE_BLOCK":
        return BarrierClass.CANDIDATE_BLOCK.value
    if fc == "HARD_BLOCK":
        stage = str(blocking_stage or "").upper()
        if stage == "RECONCILIATION":
            return BarrierClass.RECONCILIATION_BLOCK.value
        return BarrierClass.AUTHORITATIVE_HARD_BLOCK.value
    halt = classify_halt_condition(str(fault_reason or ""))
    if halt is HaltClass.ADVISORY:
        return BarrierClass.ADVISORY.value
    if halt is HaltClass.HARD_BLOCK:
        return BarrierClass.AUTHORITATIVE_HARD_BLOCK.value
    if fc in {"WAIT", "NONE", ""}:
        return BarrierClass.SOFT_WAIT.value
    return BarrierClass.SOFT_WAIT.value


def build_readiness_matrix(
    *,
    has_current_scan: bool,
    eligible_count: int,
    execution_ready: bool,
    blocking_stage: str | None,
    fault_class: str | None,
    next_action: str | None,
    named_reject: str | None,
    last_classification: dict[str, Any] | None = None,
    scan_age_seconds: float | None = None,
    forwarded_to_oms: bool = False,
    broker_ready: bool | None = None,
) -> dict[str, Any]:
    """Fresh per-snapshot matrix. Stale last-pipeline Safety is not current truth."""
    cls = dict(last_classification or {})
    stage = str(blocking_stage or cls.get("blocking_stage") or "SCANNER").upper()
    fc = str(fault_class or cls.get("fault_class") or "").upper()
    nxt = str(next_action or cls.get("next_action") or "").upper()
    eligible = int(eligible_count or 0) > 0
    barrier = classify_barrier(
        fault_class=fc,
        fault_reason=named_reject or str(cls.get("fault_reason") or ""),
        blocking_stage=stage,
    )
    hard = barrier in {
        BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
        BarrierClass.SYSTEM_BLOCK.value,
        BarrierClass.RECONCILIATION_BLOCK.value,
    }
    advisory = barrier in {
        BarrierClass.ADVISORY.value,
        BarrierClass.DEGRADED.value,
        BarrierClass.UI_ONLY.value,
        BarrierClass.DUPLICATE.value,
        BarrierClass.STALE_STATE.value,
    }
    reached_idx = _stage_index(stage)
    later_reached = eligible and (
        execution_ready
        or forwarded_to_oms
        or str(cls.get("decision_state") or "")
        in {"EXECUTION_READY", "EXECUTION_AUTHORIZED", "ORDER_SUBMITTED", "POSITION_OPEN"}
    )

    def later(name: str) -> str:
        idx = _stage_index(name)
        if not has_current_scan or not eligible:
            return StageStatus.NOT_REACHED.value
        if advisory:
            return StageStatus.PASS.value if later_reached or idx <= reached_idx else StageStatus.NOT_REACHED.value
        if hard and idx == reached_idx:
            return StageStatus.BLOCK.value
        if hard and idx > reached_idx:
            return StageStatus.NOT_REACHED.value
        if later_reached and idx < _stage_index("OMS"):
            return StageStatus.PASS.value
        if idx < reached_idx:
            return StageStatus.PASS.value
        if idx == reached_idx:
            return StageStatus.WAIT.value if not hard else StageStatus.BLOCK.value
        return StageStatus.NOT_REACHED.value

    market = StageStatus.WAIT.value
    if has_current_scan:
        market = StageStatus.PASS.value
        if scan_age_seconds is not None and scan_age_seconds > SCAN_STALE_SECONDS:
            market = StageStatus.WAIT.value
        if hard and stage in {"MARKET", "GATEWAY", "BROKER"} and not eligible:
            market = StageStatus.BLOCK.value

    strategy = StageStatus.NOT_REACHED.value
    if has_current_scan:
        if eligible:
            strategy = StageStatus.PASS.value
        elif named_reject:
            strategy = StageStatus.WAIT.value
        else:
            strategy = StageStatus.WAIT.value

    decision = StageStatus.NOT_REACHED.value
    if has_current_scan:
        if eligible and nxt in {"HOLD_FOCUS", "WAIT_SAME_FOCUS", "CONTINUE", "HOLD"}:
            decision = StageStatus.PASS.value
        elif eligible:
            decision = StageStatus.WAIT.value
        else:
            decision = StageStatus.WAIT.value

    safety = later("SAFETY")
    risk = later("RISK")
    sizing = later("SIZING")
    portfolio = later("PORTFOLIO")
    optimizer = later("OPTIMIZER")
    oms = later("OMS")
    if forwarded_to_oms:
        oms = StageStatus.PASS.value
    broker = later("BROKER")
    if broker_ready is True and eligible:
        broker = StageStatus.PASS.value if broker != StageStatus.BLOCK.value else broker
    elif broker_ready is False and hard and stage in {"GATEWAY", "BROKER", "OMS"}:
        broker = StageStatus.BLOCK.value

    stages = {
        "MARKET": market,
        "STRATEGY": strategy,
        "DECISION": decision,
        "SAFETY": safety,
        "RISK": risk,
        "SIZING": sizing,
        "PORTFOLIO": portfolio,
        "OPTIMIZER": optimizer,
        "OMS": oms,
        "BROKER": broker,
    }
    first_block = next(
        (name for name in READINESS_STAGES if stages[name] == StageStatus.BLOCK.value),
        None,
    )
    first_wait = next(
        (name for name in READINESS_STAGES if stages[name] == StageStatus.WAIT.value),
        None,
    )
    return {
        "stages": stages,
        "as_of": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "scan_age_seconds": round(scan_age_seconds, 1) if scan_age_seconds is not None else None,
        "scan_stale": bool(
            scan_age_seconds is not None and scan_age_seconds > SCAN_STALE_SECONDS
        ),
        "barrier_class": barrier,
        "first_block_stage": first_block,
        "first_wait_stage": first_wait,
        "execution_ready": bool(execution_ready and eligible),
        "stale_status_used": False,
    }


def resolve_tracker_state(
    *,
    has_current_scan: bool,
    eligible_count: int,
    execution_ready: bool,
    current_focus: str | None,
    next_action: str | None,
    fault_class: str | None,
    decision_state: str | None,
    named_reject: str | None,
    window_active: bool,
    first_natural_trade: bool,
    window_started: bool = False,
    forwarded_to_oms: bool = False,
) -> str:
    ds = str(decision_state or "").upper()
    fc = str(fault_class or "").upper()
    nxt = str(next_action or "").upper()
    eligible = int(eligible_count or 0) > 0
    if first_natural_trade or ds in {"POSITION_OPEN", "FILLED"}:
        return TrackerState.POSITION_OPEN.value
    if ds == "RECONCILIATION_REQUIRED" or ds == "ORDER_UNKNOWN":
        return TrackerState.RECONCILIATION.value
    if ds == "ORDER_SUBMITTED" or forwarded_to_oms:
        return TrackerState.ORDER_SUBMITTED.value
    if ds == "EXECUTION_AUTHORIZED":
        return TrackerState.EXECUTION_AUTHORIZED.value
    if window_started and not window_active and not first_natural_trade:
        return TrackerState.TIMEOUT_NO_TRADE.value
    if fc in {"HARD_BLOCK", "SYSTEM_BLOCK"} or nxt == "FAIL_CLOSED":
        return TrackerState.BLOCKED.value
    if ds == "EXECUTION_READY" or execution_ready:
        return TrackerState.READY.value
    if not has_current_scan:
        return TrackerState.MARKET_CONTEXT_NOT_READY.value
    if eligible and nxt == "WAIT_SAME_FOCUS" and current_focus:
        return TrackerState.WAITING.value
    if eligible:
        return TrackerState.SETUP_FORMING.value
    if named_reject or nxt in {"NO_EXECUTABLE_FOCUS", "SETUP_NOT_READY"}:
        return TrackerState.SETUP_NOT_READY.value
    return TrackerState.SETUP_NOT_READY.value


def production_feature_inventory() -> list[dict[str, Any]]:
    """Runtime feature table for Gold-only production. Observability only."""
    gold_only = True
    execution_on = False
    force_first = False
    risk_override = False
    scan_on = True
    continuous = True
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        from app.domain.trading.gold_only import gold_only_enabled

        gold_only = bool(gold_only_enabled())
        execution_on = bool(getattr(settings, "execution_enabled", False))
        force_first = bool(getattr(settings, "force_first_trade", False))
        risk_override = bool(getattr(settings, "allow_risk_lock_override", False))
    except Exception:
        pass
    try:
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )

        scan_on = bool(
            getattr(DEFAULT_AI_SCALPING_CONFIG, "multi_asset_scan_enabled", True)
        )
        continuous = bool(
            getattr(DEFAULT_AI_SCALPING_CONFIG, "continuous_operation_enabled", True)
        )
    except Exception:
        pass

    def row(
        feature: str,
        current: str,
        intended: str,
        action: str,
        *,
        authoritative: bool,
        can_block: bool,
        classification: str,
        source: str,
        path: str,
    ) -> dict[str, Any]:
        return {
            "feature": feature,
            "current": current,
            "intended": intended,
            "action": action,
            "authoritative": authoritative,
            "can_block_new_entry": can_block,
            "classification": classification,
            "source": source,
            "file": path,
        }

    return [
        row(
            "GOLD_ONLY_MODE",
            "ON" if gold_only else "OFF",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
            source="ENV/CONFIG",
            path="app/domain/trading/gold_only.py",
        ),
        row(
            "Gold scanner (existing multi-asset scan, universe clamped)",
            "ON" if scan_on else "OFF",
            "ON",
            "ENABLE" if not scan_on else "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.SOFT_WAIT.value,
            source="CONFIG",
            path="app/domain/institutional_trading/ai_scalping/config.py",
        ),
        row(
            "CURRENT_SCAN publication",
            "ON",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=False,
            classification=BarrierClass.SOFT_WAIT.value,
            source="POLICY",
            path="app/domain/institutional_trading/operations/fast_decision_path.py",
        ),
        row(
            "Focused Pair Watch",
            "ON",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.SOFT_WAIT.value,
            source="POLICY",
            path="app/domain/institutional_trading/operations/fast_decision_path.py",
        ),
        row(
            "Continuous ITE scheduler",
            "ON" if continuous else "OFF",
            "ON",
            "ENABLE" if not continuous else "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.SOFT_WAIT.value,
            source="CONFIG",
            path="app/domain/institutional_trading/ai_scalping/profiles/scalping_v1.py",
        ),
        row(
            "Safety",
            "ON",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
            source="POLICY",
            path="app/application/services/institutional_ite_runtime.py",
        ),
        row(
            "Risk",
            "ON",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
            source="POLICY",
            path="app/application/services/risk_engine.py",
        ),
        row(
            "OMS",
            "ON",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
            source="POLICY",
            path="app/application/services/institutional_oms_adapter.py",
        ),
        row(
            "Gateway / MT5",
            "ON",
            "ON",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.SYSTEM_BLOCK.value,
            source="ENV",
            path="app/infrastructure/brokers/mt5/gateway_client.py",
        ),
        row(
            "EXECUTION_ENABLED",
            "ON" if execution_on else "OFF",
            "ON if gateway+token configured",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
            source="ENV",
            path="core/config/settings.py",
        ),
        row(
            "MAX_LEVERAGE=1000",
            "1000",
            "1000",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.AUTHORITATIVE_HARD_BLOCK.value,
            source="POLICY",
            path="app/domain/trading/xauusd_specs.py",
        ),
        row(
            "SCALPING_V1 quality floors",
            "structure 60 / momentum 55 / quality 74 / confidence 71",
            "unchanged",
            "KEEP",
            authoritative=True,
            can_block=True,
            classification=BarrierClass.SOFT_WAIT.value,
            source="CONFIG",
            path="app/domain/institutional_trading/ai_scalping/profiles/scalping_v1.py",
        ),
        row(
            "Forced Trade",
            "ON" if force_first else "OFF",
            "OFF",
            "KEEP OFF",
            authoritative=True,
            can_block=False,
            classification=BarrierClass.ADVISORY.value,
            source="ENV",
            path="core/config/settings.py",
        ),
        row(
            "Risk lock override",
            "ON" if risk_override else "OFF",
            "OFF",
            "KEEP OFF",
            authoritative=True,
            can_block=False,
            classification=BarrierClass.ADVISORY.value,
            source="ENV",
            path="core/config/settings.py",
        ),
        row(
            "Blind order_send retry",
            "OFF",
            "OFF",
            "KEEP OFF",
            authoritative=True,
            can_block=False,
            classification=BarrierClass.ADVISORY.value,
            source="POLICY",
            path="app/domain/institutional_trading/operations/fast_decision_path.py",
        ),
        row(
            "Advisory / UI telemetry",
            "DEGRADED only",
            "never halt entry",
            "KEEP",
            authoritative=False,
            can_block=False,
            classification=BarrierClass.ADVISORY.value,
            source="POLICY",
            path="app/domain/institutional_trading/operations/execution_halt_policy.py",
        ),
    ]


def bottleneck_report(
    *,
    tracker_state: str,
    readiness: dict[str, Any],
    window: dict[str, Any],
    named_reject: str | None,
    first_blocking_gate: str | None,
    dwell_ms: dict[str, float] | None = None,
) -> dict[str, Any]:
    stages = dict(readiness.get("stages") or {})
    first_block = readiness.get("first_block_stage")
    first_wait = readiness.get("first_wait_stage")
    first = first_block or first_wait or "STRATEGY"
    latency = dict(window.get("cycle_latency_ms") or {})
    return {
        "tracker_state": tracker_state,
        "best_gold_state": tracker_state,
        "first_authoritative_blocker": first_blocking_gate or named_reject or first,
        "first_blocking_stage": first,
        "barrier_class": readiness.get("barrier_class"),
        "hard_blocks": int(window.get("hard_blocks") or 0),
        "soft_waits": int(window.get("candidate_blocks") or 0)
        + int(window.get("soft_waits") or 0),
        "degraded_states": int(window.get("advisory_degradations") or 0),
        "candidates_evaluated": int(window.get("candidates_evaluated") or 0),
        "execution_ready_moments": int(window.get("execution_ready") or 0),
        "oms_ready_moments": int(window.get("oms_ready") or 0),
        "broker_ready_moments": int(window.get("broker_ready") or 0),
        "orders_submitted": int(window.get("orders_submitted") or 0),
        "time_in_state_ms": dict(dwell_ms or {}),
        "cycle_latency_ms": latency,
        "why_no_order": (
            None
            if tracker_state
            in {
                TrackerState.ORDER_SUBMITTED.value,
                TrackerState.FILLED.value,
                TrackerState.POSITION_OPEN.value,
            }
            else (
                first_blocking_gate
                or named_reject
                or f"{first} {readiness.get('barrier_class') or 'SOFT_WAIT'}"
            )
        ),
        "forces_trades": False,
    }
