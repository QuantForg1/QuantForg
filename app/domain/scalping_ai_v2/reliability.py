"""Controller, supervisor, watchdog, recovery, duplicate protection."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from threading import Lock
from typing import Any
from uuid import uuid4

from app.domain.scalping_ai_v2.config import ScalpingAiV2Config
from app.domain.scalping_ai_v2.types import ModuleResult, ScalpCycleInput


@dataclass
class DuplicateProtection:
    """Guarantee unique execution identity — no duplicate orders/fills/retries."""

    _seen: set[str] = field(default_factory=set)
    _lock: Lock = field(default_factory=Lock)

    def claim(self, execution_identity: str | None) -> dict[str, Any]:
        if not execution_identity:
            eid = f"exec_{uuid4().hex}"
            with self._lock:
                self._seen.add(eid)
            return {
                "allowed": True,
                "execution_identity": eid,
                "duplicate": False,
                "reason": "Issued new unique execution identity",
            }
        with self._lock:
            if execution_identity in self._seen:
                return {
                    "allowed": False,
                    "execution_identity": execution_identity,
                    "duplicate": True,
                    "reason": "Duplicate execution identity blocked",
                }
            self._seen.add(execution_identity)
        return {
            "allowed": True,
            "execution_identity": execution_identity,
            "duplicate": False,
            "reason": "Identity claimed",
        }

    def export_identities(self) -> list[str]:
        with self._lock:
            return sorted(self._seen)

    def import_identities(self, identities: list[str] | None) -> int:
        if not identities:
            return 0
        added = 0
        with self._lock:
            for eid in identities:
                if not eid or eid in self._seen:
                    continue
                self._seen.add(str(eid))
                added += 1
        return added


def supervise_active_trade(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    trade = inp.active_trade
    if trade is None:
        return ModuleResult(
            module="active_trade_supervisor",
            status="empty",
            score=None,
            passed=None,
            recommendation="No active trade",
            reasons=("No active trade to supervise",),
        )
    reasons: list[str] = []
    actions: list[str] = []
    score = Decimal("60")
    pnl = trade.get("unrealized_pnl")
    dd = trade.get("drawdown")
    time_in = trade.get("time_in_trade_sec")
    r_multiple = trade.get("r_multiple")
    if pnl is not None:
        reasons.append(f"Unrealized PnL {pnl}")
    if dd is not None:
        reasons.append(f"Drawdown {dd}")
        score -= Decimal("5")
    if time_in is not None:
        reasons.append(f"Time in trade {time_in}s")
    if trade.get("spread_changed") is True:
        reasons.append("Spread changed — monitor")
        score -= Decimal("5")
    if trade.get("volatility_spike") is True:
        reasons.append("Volatility spike — supervise tightly")
        score -= Decimal("10")
    if trade.get("structure_invalidated") is True:
        reasons.append("Structure invalidated — review exit")
        score -= Decimal("20")
        actions.append("review_exit")

    try:
        r_val = Decimal(str(r_multiple)) if r_multiple is not None else None
    except Exception:
        r_val = None
    if r_val is not None:
        reasons.append(f"R-multiple {r_val}")
        if config.break_even_enabled and r_val >= config.break_even_at_r:
            actions.append("break_even_advisory")
        if config.trailing_enabled and r_val >= config.trail_after_r:
            actions.append("trailing_stop_advisory")
        if config.partial_exit_enabled and r_val >= config.partial_exit_at_r:
            actions.append(
                f"partial_exit_advisory_{config.partial_exit_pct}pct"
            )

    reasons.append(
        "Management is policy-driven advisory only — no order_send"
    )
    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    return ModuleResult(
        module="active_trade_supervisor",
        status="available",
        score=score,
        passed=score >= Decimal("40"),
        recommendation="Supervise",
        reasons=tuple(reasons),
        details={"actions": actions, "policy_driven_only": True},
    )


def run_auto_controller(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    state = (inp.run_state or "stopped").lower()
    reasons: list[str] = [f"Run state {state}"]
    if inp.kill_switch is True:
        return ModuleResult(
            module="continuous_auto_trading_controller",
            status="available",
            score=Decimal("0"),
            passed=False,
            recommendation="No Trade",
            reasons=("Kill switch — pause trading",),
            details={"run_state": "safe_mode", "recoverable": False},
        )
    if state in {"stopped", "paused", "safe_mode"}:
        return ModuleResult(
            module="continuous_auto_trading_controller",
            status="available",
            score=Decimal("30"),
            passed=False,
            recommendation="No Trade",
            reasons=(
                *reasons,
                "Controller not in running state — no new scans/trades",
            ),
            details={
                "run_state": state,
                "scan_interval_sec": config.controller_scan_interval_sec,
                "auto_resume_on_recovery": True,
            },
        )
    reasons.append("Continuous scan enabled for recoverable operation")
    reasons.append(
        f"Scan interval {config.controller_scan_interval_sec}s (configurable)"
    )
    reasons.append("Recoverable errors must not permanently stop the loop")
    return ModuleResult(
        module="continuous_auto_trading_controller",
        status="available",
        score=Decimal("80"),
        passed=True,
        recommendation="Scan",
        reasons=tuple(reasons),
        details={
            "run_state": "running",
            "scan_interval_sec": config.controller_scan_interval_sec,
            "never_order_send": True,
        },
    )


def run_watchdog(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    health = inp.health if isinstance(inp.health, dict) else {}
    probes = {
        "execution_loop": health.get("execution_loop"),
        "broker_connection": health.get("broker_connection", inp.broker_connected),
        "gateway": health.get("gateway", inp.gateway_healthy),
        "database": health.get("database"),
        "analytics": health.get("analytics"),
        "risk_engine": health.get("risk_engine", inp.risk_engine_passed),
        "safety_engine": health.get("safety_engine", inp.safety_engine_passed),
        "decision_engine": health.get(
            "decision_engine", inp.decision_approved
        ),
    }
    if all(v is None for v in probes.values()):
        return ModuleResult(
            module="production_watchdog",
            status="unavailable",
            score=None,
            passed=None,
            recommendation="Await probes",
            reasons=("No health probes supplied — never invents health",),
            details={"interval_sec": config.watchdog_interval_sec},
        )
    unhealthy = [k for k, v in probes.items() if v is False]
    reasons: list[str] = []
    for k, v in probes.items():
        if v is True:
            label = "ok"
        elif v is None:
            label = "unknown"
        else:
            label = "UNHEALTHY"
        reasons.append(f"{k}: {label}")
    if unhealthy:
        critical = any(
            k in unhealthy
            for k in (
                "risk_engine",
                "safety_engine",
                "broker_connection",
                "gateway",
            )
        )
        return ModuleResult(
            module="production_watchdog",
            status="available",
            score=Decimal("20"),
            passed=False,
            recommendation="Safe mode" if critical else "Recover",
            reasons=(
                *reasons,
                f"Unhealthy: {', '.join(unhealthy)}",
                "Attempt recovery; pause trading if critical risk",
            ),
            details={
                "unhealthy": unhealthy,
                "safe_mode": critical,
                "interval_sec": config.watchdog_interval_sec,
            },
        )
    return ModuleResult(
        module="production_watchdog",
        status="available",
        score=Decimal("90"),
        passed=True,
        recommendation="Healthy",
        reasons=tuple(reasons),
        details={"unhealthy": [], "safe_mode": False},
    )


def plan_incident_recovery(
    inp: ScalpCycleInput, config: ScalpingAiV2Config
) -> ModuleResult:
    health = inp.health if isinstance(inp.health, dict) else {}
    incident = health.get("incident") or health.get("last_incident")
    broker_ok = inp.broker_connected is not False
    gateway_ok = inp.gateway_healthy is not False
    if not incident and broker_ok and gateway_ok:
        return ModuleResult(
            module="incident_recovery",
            status="empty",
            score=None,
            passed=True,
            recommendation="No incident",
            reasons=("No recoverable incident reported",),
        )
    incident_type = str(
        incident
        if isinstance(incident, str)
        else (incident or {}).get("type")
        if isinstance(incident, dict)
        else "unknown"
    )
    reasons = [
        f"Incident {incident_type}",
        "Recovery must never duplicate trades",
        f"Max retries {config.max_retries} with exponential backoff "
        f"({config.retry_backoff_ms}ms → {config.max_retry_backoff_ms}ms)",
    ]
    steps = [
        "log_incident",
        "start_recovery",
        "reconnect_if_needed",
        "verify_no_duplicate_execution_identity",
        "resume_scan_if_healthy",
        "log_recovery_completed",
    ]
    return ModuleResult(
        module="incident_recovery",
        status="available",
        score=Decimal("70"),
        passed=True,
        recommendation="Recover",
        reasons=tuple(reasons),
        details={
            "steps": steps,
            "never_duplicate_trades": True,
            "max_retries": config.max_retries,
        },
    )


def next_backoff_ms(attempt: int, config: ScalpingAiV2Config) -> int:
    """Exponential backoff with hard cap — prevents unbounded retries."""
    if attempt < 0:
        attempt = 0
    if attempt >= config.max_retries:
        return -1  # stop
    delay = config.retry_backoff_ms * (2**attempt)
    return min(delay, config.max_retry_backoff_ms)


@dataclass
class RecoveryLog:
    entries: list[dict[str, Any]] = field(default_factory=list)
    _lock: Lock = field(default_factory=Lock)

    def record(
        self,
        *,
        incident: str,
        attempt: int,
        duration_ms: int,
        outcome: str,
        detail: str,
    ) -> dict[str, Any]:
        row = {
            "recovery_id": f"rc_{uuid4().hex[:10]}",
            "incident": incident,
            "attempt": attempt,
            "duration_ms": duration_ms,
            "outcome": outcome,
            "detail": detail,
            "created_at": datetime.now(UTC).isoformat(),
        }
        with self._lock:
            self.entries.insert(0, row)
            self.entries = self.entries[:200]
        return row
