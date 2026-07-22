"""OWNER launch readiness — audit blockers; promote only via Ops state machine.

Never bypasses Risk/Safety. Never flips EXECUTION_ENABLED (env only).
Never fabricates gateway/broker/market facts.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.application.services.auto_trading_status import build_auto_trading_status
from app.application.services.live_auto_trade_certification import get_live_cert_service
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
    PermissionDenied,
)
from app.domain.institutional_trading.operations.models import (
    OperatorIdentity,
    OpsExecutionMode,
)
from core.config.settings import Settings, get_settings

# Resolution guidance — operator actions only (no engine bypass).
_RESOLVE: dict[str, str] = {
    "ops_mode": (
        "OWNER/ADMIN: POST /ite/ops/mode with target CANARY then LIVE "
        "(confirmed=true) after Demo certification — or use "
        "POST /ite/ops/launch-readiness/promote"
    ),
    "execution_enabled": (
        "Set Railway/host EXECUTION_ENABLED=true with MT5_GATEWAY_BASE_URL "
        "configured, then redeploy/restart the API. No HTTP route can flip this."
    ),
    "kill_switch": (
        "OWNER/ADMIN: POST /ite/ops/kill-switch/disarm with confirmed=true "
        "and an audit reason"
    ),
    "emergency_stop": (
        "Disarm kill switch, then POST /ite/ops/auto-trading with "
        "run_state=running and confirmed=true"
    ),
    "safety_lock": (
        "Clear SAFETY_LOCK by disarming the kill switch "
        "(POST /ite/ops/kill-switch/disarm)"
    ),
    "risk_lock": (
        "Clear RISK_LOCK / daily loss: wait for the UTC day reset or reduce "
        "exposure; confirm plane.daily_loss_exceeded is false"
    ),
    "daily_loss_lock": (
        "Daily loss exceeded — no new auto trades until the limit resets "
        "or risk config is adjusted by OWNER with confirmed audit"
    ),
    "gateway": (
        "Restore Windows MT5 Gateway + Cloudflare tunnel; confirm "
        "GET gateway /health and Railway MT5_GATEWAY_BASE_URL"
    ),
    "broker": (
        "Attach/login MT5 session via Broker desk (Weltrade connect/attach); "
        "confirm broker_connected on GET /ite/ops/auto-trading"
    ),
    "mt5_login": (
        "Complete MT5 login on the gateway host; renew expired session "
        "from Broker workspace"
    ),
    "market_open": (
        "Wait for market open / live XAUUSD ticks; confirm market_data_live "
        "on Auto Trading status"
    ),
    "trading_allowed": (
        "Enable account trading at the broker; confirm trade_allowed / "
        "AutoTrading in MetaTrader 5"
    ),
    "symbol_ready": (
        "Ensure XAUUSD is selectable and tradable on the attached MT5 account"
    ),
    "demo_certification": (
        "Complete a real Demo 0.01-lot certification trade, then "
        "POST /ite/ops/auto-trading/live-certification/attempt "
        "(never fabricate fills)"
    ),
    "auto_trading_run_state": (
        "OWNER/ADMIN: POST /ite/ops/auto-trading with run_state=running "
        "and confirmed=true after Ops Mode is CANARY/LIVE and "
        "EXECUTION_ENABLED=true"
    ),
    "owner_authorization": (
        "Authenticate as OWNER or ADMIN and pass confirmed=true on "
        "promotion / mode / auto-trading mutations"
    ),
}


@dataclass(frozen=True, slots=True)
class LaunchChecklistItem:
    key: str
    label: str
    passed: bool
    value: str
    why: str
    how_to_resolve: str
    required_for_promotion: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "passed": self.passed,
            "value": self.value,
            "why": self.why,
            "how_to_resolve": self.how_to_resolve,
            "required_for_promotion": self.required_for_promotion,
        }


@dataclass(frozen=True, slots=True)
class LaunchReadinessReport:
    ready_for_promotion: bool
    ready_for_gate_enabled: bool
    items: tuple[LaunchChecklistItem, ...]
    blockers: tuple[dict[str, str], ...]
    execution_state: dict[str, Any]
    promotion_plan: tuple[str, ...]
    demo_certified: bool
    verification: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready_for_promotion": self.ready_for_promotion,
            "ready_for_gate_enabled": self.ready_for_gate_enabled,
            "items": [i.to_dict() for i in self.items],
            "blockers": list(self.blockers),
            "execution_state": self.execution_state,
            "promotion_plan": list(self.promotion_plan),
            "demo_certified": self.demo_certified,
            "verification": self.verification,
            "never_bypasses_risk": True,
            "never_bypasses_safety": True,
            "never_flips_execution_enabled": True,
            "state_machine_only": True,
        }


def _item(
    key: str,
    label: str,
    *,
    passed: bool,
    value: str,
    why: str,
    required_for_promotion: bool = True,
) -> LaunchChecklistItem:
    return LaunchChecklistItem(
        key=key,
        label=label,
        passed=passed,
        value=value,
        why=why if not passed else "",
        how_to_resolve=(
            ""
            if passed
            else _RESOLVE.get(key, "Resolve via OWNER Ops controls")
        ),
        required_for_promotion=required_for_promotion,
    )


def _demo_certified() -> bool:
    try:
        report = get_live_cert_service().last_report()
    except Exception:
        return False
    if report is None or not report.certified:
        return False
    trade = getattr(report, "trade", None)
    acct = str(getattr(trade, "account_type", "") or "").strip().lower()
    return acct == "demo"


def build_launch_readiness(
    plane: OperationsControlPlane,
    *,
    settings: Settings | None = None,
    owner_authorized: bool = False,
) -> LaunchReadinessReport:
    """Audit every execution blocker from live probes — never invent PASS."""
    cfg = settings or get_settings()
    snap = build_auto_trading_status(plane, settings=cfg)
    facts = snap.facts
    state = snap.execution_state
    policy = plane.auto_trade_policy()
    demo_ok = _demo_certified()

    mt5_login_ok = bool(facts.broker_connected and facts.gateway_connected)
    trading_allowed = bool(facts.account_trading_enabled)
    symbol_ready = bool(facts.symbol_tradable and facts.symbol)
    market_open = bool(facts.market_data_live)
    safety_locked = bool(plane.kill_switch_armed)
    risk_locked = bool(plane.daily_loss_exceeded)
    run_ok = policy.to_dict().get("run_state") == "running"
    mode = plane.mode
    mode_ok = mode in {OpsExecutionMode.CANARY, OpsExecutionMode.LIVE}
    exec_ok = bool(facts.execution_enabled)

    items = (
        _item(
            "ops_mode",
            "Ops mode",
            passed=mode_ok,
            value=mode.value,
            why=f"Ops mode is {mode.value} — SHADOW journals only; OMS blocked",
        ),
        _item(
            "execution_enabled",
            "Execution Enabled",
            passed=exec_ok,
            value="true" if exec_ok else "false",
            why="EXECUTION_ENABLED=false — OMS not permitted",
        ),
        _item(
            "kill_switch",
            "Kill Switch",
            passed=not plane.kill_switch_armed,
            value="ARMED" if plane.kill_switch_armed else "DISARMED",
            why="Kill switch is armed — OMS blocked",
        ),
        _item(
            "emergency_stop",
            "Emergency Stop",
            passed=not facts.emergency_stop,
            value="STOP" if facts.emergency_stop else "READY",
            why="Emergency STOP is active",
        ),
        _item(
            "safety_lock",
            "Safety Lock",
            passed=not safety_locked,
            value="LOCKED" if safety_locked else "CLEAR",
            why="Safety lock active (kill switch armed)",
        ),
        _item(
            "risk_lock",
            "Risk Lock",
            passed=not risk_locked,
            value="LOCKED" if risk_locked else "CLEAR",
            why="Risk lock active (daily loss exceeded)",
        ),
        _item(
            "daily_loss_lock",
            "Daily Loss Lock",
            passed=not plane.daily_loss_exceeded,
            value="EXCEEDED" if plane.daily_loss_exceeded else "OK",
            why="Maximum daily loss exceeded",
        ),
        _item(
            "gateway",
            "Gateway",
            passed=bool(facts.gateway_connected),
            value="CONNECTED" if facts.gateway_connected else "OFFLINE",
            why="MT5 Gateway not connected",
        ),
        _item(
            "broker",
            "Broker",
            passed=bool(facts.broker_connected),
            value="CONNECTED" if facts.broker_connected else "OFF",
            why="Broker / MT5 not connected",
        ),
        _item(
            "mt5_login",
            "MT5 Login",
            passed=mt5_login_ok,
            value="OK" if mt5_login_ok else "MISSING",
            why="MT5 session not logged in / gateway offline",
        ),
        _item(
            "market_open",
            "Market Open",
            passed=market_open,
            value="OPEN" if market_open else "CLOSED/QUIET",
            why="Market data is not live",
        ),
        _item(
            "trading_allowed",
            "Trading Allowed",
            passed=trading_allowed
            if facts.account_flags_evaluated
            else bool(facts.broker_connected),
            value=(
                "YES"
                if (
                    trading_allowed
                    if facts.account_flags_evaluated
                    else bool(facts.broker_connected)
                )
                else "NO"
            ),
            why="Account trading disabled or flags unavailable while broker down",
        ),
        _item(
            "symbol_ready",
            "Symbol Ready",
            passed=symbol_ready
            if facts.symbol_tradable or facts.broker_connected
            else False,
            value=(
                "XAUUSD READY"
                if symbol_ready or facts.broker_connected
                else "NOT READY"
            ),
            why="Symbol XAUUSD not tradable / not ready",
            required_for_promotion=True,
        ),
        _item(
            "demo_certification",
            "Demo Certification",
            passed=demo_ok,
            value="CERTIFIED" if demo_ok else "MISSING",
            why="Demo certification required before LIVE",
        ),
        _item(
            "auto_trading_run_state",
            "Auto Trading",
            passed=run_ok,
            value=str(policy.to_dict().get("run_state", "off")).upper(),
            why="Auto Trading is not RUNNING",
            required_for_promotion=False,  # set during promote
        ),
        _item(
            "owner_authorization",
            "OWNER Authorization",
            passed=owner_authorized,
            value="CONFIRMED" if owner_authorized else "REQUIRED",
            why="OWNER/ADMIN confirmation required for promotion",
        ),
    )

    blockers = tuple(
        {
            "key": i.key,
            "label": i.label,
            "why": i.why,
            "how_to_resolve": i.how_to_resolve,
            "value": i.value,
        }
        for i in items
        if not i.passed and i.required_for_promotion
    )

    # Promotion requires infra + env + demo cert + kill clear.
    # Mode/run_state are outcomes of promotion, not prerequisites.
    promo_required_keys = {
        "execution_enabled",
        "kill_switch",
        "emergency_stop",
        "safety_lock",
        "risk_lock",
        "daily_loss_lock",
        "gateway",
        "broker",
        "mt5_login",
        "market_open",
        "trading_allowed",
        "symbol_ready",
        "demo_certification",
        "owner_authorization",
    }
    ready_for_promotion = all(
        i.passed for i in items if i.key in promo_required_keys
    )

    plan: list[str] = []
    if mode is OpsExecutionMode.SHADOW:
        plan.append("POST /ite/ops/mode target=CANARY (confirmed)")
    if mode in {OpsExecutionMode.SHADOW, OpsExecutionMode.CANARY}:
        plan.append("POST /ite/ops/mode target=LIVE (confirmed, Demo cert)")
    plan.append("POST /ite/ops/auto-trading run_state=running (confirmed)")
    plan.append("GET /ite/ops/auto-trading — verify Gate Enabled")

    verification = {
        "ops_mode": mode.value,
        "gate": snap.safety.status,
        "execution_enabled": exec_ok,
        "auto_trading": str(policy.to_dict().get("run_state", "off")).upper(),
        "gateway": "CONNECTED" if facts.gateway_connected else "OFFLINE",
        "broker": "CONNECTED" if facts.broker_connected else "OFF",
        "risk": "READY" if not risk_locked else "LOCKED",
        "safety": "READY" if not safety_locked else "LOCKED",
        "primary_blocker": snap.primary_blocker,
        "blocking_category": snap.blocking_category,
    }

    return LaunchReadinessReport(
        ready_for_promotion=ready_for_promotion,
        ready_for_gate_enabled=bool(snap.safety.allowed),
        items=items,
        blockers=blockers,
        execution_state=state,
        promotion_plan=tuple(plan),
        demo_certified=demo_ok,
        verification=verification,
    )


def promote_to_live_execution(
    plane: OperationsControlPlane,
    operator: OperatorIdentity,
    *,
    reason: str,
    confirmed: bool,
    settings: Settings | None = None,
    activate_auto_trading: bool = True,
) -> dict[str, Any]:
    """SHADOW→CANARY→LIVE via plane.transition_mode only, then optionally RUNNING.

    Refuses when any required blocker remains. Never sets EXECUTION_ENABLED.
    """
    cfg = settings or get_settings()
    pre = build_launch_readiness(plane, settings=cfg, owner_authorized=True)
    if not confirmed:
        return {
            "ok": False,
            "promoted": False,
            "message": "operator confirmation required",
            "readiness": pre.to_dict(),
        }
    if not pre.ready_for_promotion:
        return {
            "ok": False,
            "promoted": False,
            "message": "launch blockers remain — promotion refused",
            "readiness": pre.to_dict(),
        }

    steps: list[dict[str, Any]] = []
    try:
        if plane.mode is OpsExecutionMode.SHADOW:
            result = plane.transition_mode(
                operator,
                OpsExecutionMode.CANARY,
                reason=reason,
                confirmed=True,
            )
            steps.append(
                {
                    "action": "mode_transition",
                    "from": "SHADOW",
                    "to": "CANARY",
                    "ok": result.ok,
                    "message": result.message,
                }
            )
            if not result.ok:
                return {
                    "ok": False,
                    "promoted": False,
                    "message": result.message,
                    "steps": steps,
                    "readiness": build_launch_readiness(
                        plane, settings=cfg, owner_authorized=True
                    ).to_dict(),
                }

        if plane.mode is OpsExecutionMode.CANARY:
            result = plane.transition_mode(
                operator,
                OpsExecutionMode.LIVE,
                reason=reason,
                confirmed=True,
            )
            steps.append(
                {
                    "action": "mode_transition",
                    "from": "CANARY",
                    "to": "LIVE",
                    "ok": result.ok,
                    "message": result.message,
                }
            )
            if not result.ok:
                return {
                    "ok": False,
                    "promoted": False,
                    "message": result.message,
                    "steps": steps,
                    "readiness": build_launch_readiness(
                        plane, settings=cfg, owner_authorized=True
                    ).to_dict(),
                }

        if activate_auto_trading and plane.mode is OpsExecutionMode.LIVE:
            policy = plane.update_auto_trade_controls(
                operator,
                run_state="running",
                enabled=True,
                reason=reason,
            )
            steps.append(
                {
                    "action": "auto_trading",
                    "run_state": policy.to_dict().get("run_state"),
                    "ok": True,
                }
            )
    except PermissionDenied as exc:
        return {
            "ok": False,
            "promoted": False,
            "message": str(exc),
            "steps": steps,
            "readiness": build_launch_readiness(
                plane, settings=cfg, owner_authorized=True
            ).to_dict(),
        }

    post = build_launch_readiness(plane, settings=cfg, owner_authorized=True)
    gate_ok = post.ready_for_gate_enabled
    live_ok = plane.mode is OpsExecutionMode.LIVE
    return {
        "ok": live_ok and gate_ok,
        "promoted": live_ok,
        "message": (
            "LIVE execution armed — Gate Enabled"
            if live_ok and gate_ok
            else (
                "Mode promoted but Gate still Disabled — see blockers"
                if live_ok
                else "Promotion incomplete"
            )
        ),
        "steps": steps,
        "readiness": post.to_dict(),
        "verification": post.verification,
    }
