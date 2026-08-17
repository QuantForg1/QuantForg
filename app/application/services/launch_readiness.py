"""OWNER launch readiness — audit blockers; promote only via Ops state machine.

Never bypasses Risk/Safety. Never flips EXECUTION_ENABLED (env only).
Never fabricates gateway/broker/market facts.

Official production policy (OWNER-approved):

    SHADOW → CANARY → LIVE

Demo Certification is optional advisory tooling — not a LIVE launch gate.
Risk Engine, Safety Engine, and remaining launch locks remain mandatory.
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
        "Promote through the official Ops state machine:\n"
        "SHADOW\n↓\nCANARY\n↓\nLIVE\n"
        "(POST /ite/ops/launch-readiness/promote or /ite/ops/mode with confirmed=true)"
    ),
    "execution_enabled": (
        "Set Railway EXECUTION_ENABLED=true\n"
        "Confirm MT5_GATEWAY_BASE_URL is set\n"
        "Redeploy / restart the API\n"
        "(No HTTP route can flip this flag)"
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
        "Restore Windows MT5 Gateway + Cloudflare tunnel\n"
        "Confirm gateway /health and Railway MT5_GATEWAY_BASE_URL"
    ),
    "broker": (
        "Attach/login MT5 session via Broker desk (Weltrade connect/attach)\n"
        "Confirm broker_connected on GET /ite/ops/auto-trading"
    ),
    "mt5_login": (
        "Complete MT5 login on the gateway host\n"
        "Renew expired session from Broker workspace"
    ),
    "market_open": (
        "Wait for market open / live XAUUSD ticks\n"
        "Confirm market_data_live on Auto Trading status"
    ),
    "trading_allowed": (
        "Enable account trading at the broker\n"
        "Confirm trade_allowed / AutoTrading in MetaTrader 5"
    ),
    "symbol_ready": (
        "Ensure XAUUSD is selectable and tradable on the attached MT5 account"
    ),
    "demo_certification": (
        "Optional advisory only — not required for LIVE under current policy.\n"
        "May still run Demo certification tooling for operator confidence:\n"
        "POST /ite/ops/auto-trading/live-certification/attempt"
    ),
    "auto_trading_run_state": (
        "OWNER/ADMIN: POST /ite/ops/auto-trading with run_state=running "
        "and confirmed=true after Ops Mode is CANARY/LIVE and "
        "EXECUTION_ENABLED=true"
    ),
    "owner_authorization": (
        "Authenticate as OWNER or ADMIN\n"
        "Pass confirmed=true on promotion / mode / auto-trading mutations"
    ),
    "burst_latch": (
        "Wait for Phase A burst-latch cooldown to expire\n"
        "Do not bypass Safety — new entries stay blocked until CLEAR"
    ),
    "reconciliation": (
        "Reconcile ambiguous OMS/MT5 order state\n"
        "New entries stay blocked until RECONCILIATION_REQUIRED clears"
    ),
}

# Shared infra/safety locks for any promotion step.
_INFRA_KEYS = frozenset(
    {
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
        "owner_authorization",
        "burst_latch",
        "reconciliation",
    }
)


@dataclass(frozen=True, slots=True)
class LaunchChecklistItem:
    key: str
    label: str
    passed: bool
    value: str
    why: str
    how_to_resolve: str
    required_for_promotion: bool = True
    required_for_canary: bool = True
    required_for_live: bool = True
    category: str = "CONFIG"
    blocks_execution: bool = True
    canonical_state: str = ""
    evaluated: bool = True
    execution_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "passed": self.passed,
            "value": self.value,
            "why": self.why,
            "how_to_resolve": self.how_to_resolve,
            "required_for_promotion": self.required_for_promotion,
            "required_for_canary": self.required_for_canary,
            "required_for_live": self.required_for_live,
            "category": self.category,
            "blocks_execution": self.blocks_execution,
            "canonical_state": self.canonical_state,
            "evaluated": self.evaluated,
            "execution_code": self.execution_code,
        }


@dataclass(frozen=True, slots=True)
class LaunchReadinessReport:
    ready_for_promotion: bool
    ready_for_canary: bool
    ready_for_live: bool
    ready_for_gate_enabled: bool
    next_promotion_target: str
    items: tuple[LaunchChecklistItem, ...]
    blockers: tuple[dict[str, str], ...]
    execution_state: dict[str, Any]
    promotion_plan: tuple[str, ...]
    demo_certified: bool
    verification: dict[str, Any] = field(default_factory=dict)
    first_blocking_lock: dict[str, Any] | None = None
    remaining_locks: tuple[dict[str, Any], ...] = ()
    execution_block_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ready_for_promotion": self.ready_for_promotion,
            "ready_for_canary": self.ready_for_canary,
            "ready_for_live": self.ready_for_live,
            "ready_for_gate_enabled": self.ready_for_gate_enabled,
            "next_promotion_target": self.next_promotion_target,
            "items": [i.to_dict() for i in self.items],
            "blockers": list(self.blockers),
            "execution_state": self.execution_state,
            "promotion_plan": list(self.promotion_plan),
            "demo_certified": self.demo_certified,
            "verification": self.verification,
            "first_blocking_lock": self.first_blocking_lock,
            "remaining_locks": list(self.remaining_locks),
            "execution_block_code": self.execution_block_code,
            "never_bypasses_risk": True,
            "never_bypasses_safety": True,
            "never_flips_execution_enabled": True,
            "state_machine_only": True,
            "demo_certification_required_for_live": False,
        }


def _item(
    key: str,
    label: str,
    *,
    passed: bool,
    value: str,
    why: str,
    required_for_promotion: bool = True,
    required_for_canary: bool = True,
    required_for_live: bool = True,
    category: str = "CONFIG",
    blocks_execution: bool = True,
    canonical_state: str = "",
    evaluated: bool = True,
    execution_code: str = "",
) -> LaunchChecklistItem:
    return LaunchChecklistItem(
        key=key,
        label=label,
        passed=passed,
        value=value,
        why=why if not passed else "",
        how_to_resolve=(
            "" if passed else _RESOLVE.get(key, "Resolve via OWNER Ops controls")
        ),
        required_for_promotion=required_for_promotion,
        required_for_canary=required_for_canary,
        required_for_live=required_for_live,
        category=category,
        blocks_execution=blocks_execution,
        canonical_state=canonical_state,
        evaluated=evaluated,
        execution_code=execution_code if not passed else "",
    )


def _phase_a_safety_flags() -> tuple[bool, bool]:
    """Burst latch / reconciliation — never invent latched."""
    try:
        from app.domain.institutional_trading.phase_a.plane import get_phase_a_plane

        snap = get_phase_a_plane().snapshot()
    except Exception:
        return False, False
    burst = snap.get("burst_latch") if isinstance(snap, dict) else None
    recon = snap.get("reconciliation") if isinstance(snap, dict) else None
    burst_latched = bool(isinstance(burst, dict) and burst.get("latched"))
    recon_required = bool(isinstance(recon, dict) and recon.get("blocking"))
    return burst_latched, recon_required


def _blocker_dict(item: LaunchChecklistItem) -> dict[str, str]:
    return {
        "key": item.key,
        "label": item.label,
        "why": item.why,
        "how_to_resolve": item.how_to_resolve,
        "value": item.value,
        "category": item.category,
        "canonical_state": item.canonical_state,
        "execution_code": item.execution_code,
        "blocks_execution": "true" if item.blocks_execution else "false",
    }


def _demo_certified() -> bool:
    """Advisory status only — never a LIVE gate under current policy."""
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

    gateway_ok = bool(facts.gateway_connected)
    broker_ok = bool(facts.broker_connected)
    mt5_login_ok = bool(gateway_ok and broker_ok)
    trading_allowed = bool(facts.account_trading_enabled)
    symbol_ready = bool(facts.symbol_tradable and facts.symbol)
    market_open = bool(facts.market_data_live)
    safety_locked = bool(plane.kill_switch_armed)
    risk_locked = bool(plane.daily_loss_exceeded)
    run_ok = policy.to_dict().get("run_state") == "running"
    mode = plane.mode
    mode_ok = mode in {OpsExecutionMode.CANARY, OpsExecutionMode.LIVE}
    exec_ok = bool(facts.execution_enabled)
    burst_latched, recon_required = _phase_a_safety_flags()

    # Independent vs dependent locks: Gateway down must not be reported as
    # broker-invalid-credentials, market-closed, or missing MT5 login.
    broker_state = (
        "CONNECTED"
        if broker_ok
        else ("GATEWAY_UNAVAILABLE" if not gateway_ok else "DISCONNECTED")
    )
    mt5_state = (
        "CONNECTED"
        if mt5_login_ok
        else ("GATEWAY_UNAVAILABLE" if not gateway_ok else "DISCONNECTED")
    )
    if not gateway_ok:
        market_state = "GATEWAY_UNAVAILABLE"
        market_code = "GATEWAY_OFFLINE"
        market_why = (
            "Not evaluated — MT5 Gateway offline "
            "(not a market-hours determination)"
        )
        market_value = "UNAVAILABLE"
        market_blocks = False
        market_eval = False
    elif not broker_ok:
        market_state = "DISCONNECTED"
        market_code = "BROKER_DISCONNECTED"
        market_why = "Not evaluated — broker/MT5 session is not connected"
        market_value = "UNAVAILABLE"
        market_blocks = False
        market_eval = False
    else:
        market_state = "CONNECTED" if market_open else "DEGRADED"
        market_code = "" if market_open else "NO_QUOTE"
        market_why = "Market data is not live (no quote / stale / closed)"
        market_value = "OPEN" if market_open else "NO_QUOTE"
        market_blocks = True
        market_eval = True

    flags_eval = bool(facts.account_flags_evaluated)
    trading_eval = bool(gateway_ok and broker_ok and flags_eval)
    trading_pass = trading_allowed if trading_eval else False
    symbol_eval = bool(broker_ok)
    symbol_pass = bool(symbol_ready) if symbol_eval else False

    items = (
        _item(
            "ops_mode",
            "Ops mode",
            passed=mode_ok,
            value=mode.value,
            why=f"Ops mode is {mode.value} — SHADOW journals only; OMS blocked",
            required_for_canary=False,
            required_for_live=False,
            required_for_promotion=False,
            category="EXECUTION",
            blocks_execution=True,
            canonical_state=mode.value,
            execution_code="",
        ),
        _item(
            "execution_enabled",
            "Execution Enabled",
            passed=exec_ok,
            value="true" if exec_ok else "false",
            why="EXECUTION_ENABLED=false — OMS not permitted",
            category="CONFIG",
            canonical_state="CONNECTED" if exec_ok else "NOT_CONFIGURED",
            execution_code="" if exec_ok else "AUTH_REQUIRED",
        ),
        _item(
            "kill_switch",
            "Kill Switch",
            passed=not plane.kill_switch_armed,
            value="ARMED" if plane.kill_switch_armed else "DISARMED",
            why="Kill switch is armed — OMS blocked",
            category="RISK",
            canonical_state=(
                "CONNECTED" if not plane.kill_switch_armed else "DISCONNECTED"
            ),
            execution_code="" if not plane.kill_switch_armed else "KILL_SWITCH",
        ),
        _item(
            "emergency_stop",
            "Emergency Stop",
            passed=not facts.emergency_stop,
            value="STOP" if facts.emergency_stop else "READY",
            why="Emergency STOP is active",
            category="RISK",
            execution_code="" if not facts.emergency_stop else "KILL_SWITCH",
        ),
        _item(
            "safety_lock",
            "Safety Lock",
            passed=not safety_locked,
            value="LOCKED" if safety_locked else "CLEAR",
            why="Safety lock active (kill switch armed)",
            category="RISK",
            execution_code="" if not safety_locked else "KILL_SWITCH",
        ),
        _item(
            "risk_lock",
            "Risk Lock",
            passed=not risk_locked,
            value="LOCKED" if risk_locked else "CLEAR",
            why="Risk lock active (daily loss exceeded)",
            category="RISK",
            execution_code="" if not risk_locked else "RISK_HALTED",
        ),
        _item(
            "daily_loss_lock",
            "Daily Loss Lock",
            passed=not plane.daily_loss_exceeded,
            value="EXCEEDED" if plane.daily_loss_exceeded else "OK",
            why="Maximum daily loss exceeded",
            category="RISK",
            execution_code="" if not plane.daily_loss_exceeded else "RISK_HALTED",
        ),
        _item(
            "burst_latch",
            "Burst Latch",
            passed=not burst_latched,
            value="LATCHED" if burst_latched else "CLEAR",
            why="Phase A burst latch is armed — new entries blocked",
            category="RISK",
            execution_code="" if not burst_latched else "BURST_LATCH",
        ),
        _item(
            "reconciliation",
            "Reconciliation",
            passed=not recon_required,
            value="REQUIRED" if recon_required else "CLEAR",
            why="Ambiguous order state — new entries blocked until reconciled",
            category="RISK",
            execution_code="" if not recon_required else "RECON_REQUIRED",
        ),
        _item(
            "gateway",
            "Gateway",
            passed=gateway_ok,
            value="CONNECTED" if gateway_ok else "OFFLINE",
            why="MT5 Gateway not connected",
            category="GATEWAY",
            canonical_state="CONNECTED" if gateway_ok else "GATEWAY_UNAVAILABLE",
            execution_code="" if gateway_ok else "GATEWAY_OFFLINE",
        ),
        _item(
            "broker",
            "Broker",
            passed=broker_ok,
            value="CONNECTED" if broker_ok else broker_state,
            why=(
                "Broker session not evaluated — Gateway unavailable "
                "(not a credential failure)"
                if not gateway_ok
                else "Broker / MT5 not connected"
            ),
            category="BROKER",
            blocks_execution=gateway_ok,
            canonical_state=broker_state,
            evaluated=gateway_ok,
            execution_code=(
                ""
                if broker_ok
                else ("GATEWAY_OFFLINE" if not gateway_ok else "BROKER_DISCONNECTED")
            ),
        ),
        _item(
            "mt5_login",
            "MT5 Login",
            passed=mt5_login_ok,
            value="OK" if mt5_login_ok else mt5_state,
            why=(
                "MT5 login not evaluated — Gateway unavailable"
                if not gateway_ok
                else "MT5 session not logged in"
            ),
            category="BROKER",
            blocks_execution=gateway_ok,
            canonical_state=mt5_state,
            evaluated=gateway_ok,
            execution_code=(
                ""
                if mt5_login_ok
                else ("GATEWAY_OFFLINE" if not gateway_ok else "MT5_NOT_READY")
            ),
        ),
        _item(
            "market_open",
            "Market Open",
            passed=market_open if market_eval else False,
            value=market_value,
            why=market_why,
            category="MARKET",
            blocks_execution=market_blocks,
            canonical_state=market_state,
            evaluated=market_eval,
            execution_code=market_code,
        ),
        _item(
            "trading_allowed",
            "Trading Allowed",
            passed=trading_pass if trading_eval else False,
            value=(
                "YES"
                if trading_pass and trading_eval
                else ("UNAVAILABLE" if not trading_eval else "NO")
            ),
            why=(
                "Account trading flags not evaluated — waiting on Gateway/Broker"
                if not trading_eval
                else "Account trading disabled"
            ),
            category="BROKER",
            blocks_execution=trading_eval,
            canonical_state=(
                "CONNECTED"
                if trading_pass and trading_eval
                else (
                    "GATEWAY_UNAVAILABLE"
                    if not gateway_ok
                    else ("DISCONNECTED" if not broker_ok else "DEGRADED")
                )
            ),
            evaluated=trading_eval,
            execution_code=(
                ""
                if trading_pass and trading_eval
                else (
                    "GATEWAY_OFFLINE"
                    if not gateway_ok
                    else (
                        "BROKER_DISCONNECTED" if not broker_ok else "MT5_NOT_READY"
                    )
                )
            ),
        ),
        _item(
            "symbol_ready",
            "Symbol Ready",
            passed=symbol_pass,
            value=(
                "XAUUSD READY"
                if symbol_pass
                else ("UNAVAILABLE" if not symbol_eval else "NOT READY")
            ),
            why=(
                "Symbol tradability not evaluated — waiting on Broker"
                if not symbol_eval
                else "Symbol XAUUSD not tradable / not ready"
            ),
            category="MARKET",
            blocks_execution=symbol_eval,
            canonical_state=(
                "CONNECTED"
                if symbol_pass
                else (
                    "GATEWAY_UNAVAILABLE"
                    if not gateway_ok
                    else ("DISCONNECTED" if not broker_ok else "DEGRADED")
                )
            ),
            evaluated=symbol_eval,
            execution_code=(
                ""
                if symbol_pass
                else (
                    "GATEWAY_OFFLINE"
                    if not gateway_ok
                    else (
                        "BROKER_DISCONNECTED" if not broker_ok else "NO_QUOTE"
                    )
                )
            ),
        ),
        _item(
            "demo_certification",
            "Demo Certification",
            passed=demo_ok,
            value=("CERTIFIED" if demo_ok else "OPTIONAL"),
            why="Optional advisory — not a LIVE launch gate (OWNER policy)",
            required_for_canary=False,
            required_for_live=False,
            required_for_promotion=False,
            category="CONFIG",
            blocks_execution=False,
        ),
        _item(
            "auto_trading_run_state",
            "Auto Trading",
            passed=run_ok,
            value=str(policy.to_dict().get("run_state", "off")).upper(),
            why="Auto Trading is not RUNNING",
            required_for_promotion=False,
            required_for_canary=False,
            required_for_live=False,
            category="EXECUTION",
            blocks_execution=False,
        ),
        _item(
            "owner_authorization",
            "OWNER Authorization",
            passed=owner_authorized,
            value="CONFIRMED" if owner_authorized else "REQUIRED",
            why="OWNER/ADMIN confirmation required for promotion",
            category="AUTH",
            blocks_execution=False,
            execution_code="" if owner_authorized else "AUTH_REQUIRED",
        ),
    )

    by_key = {i.key: i for i in items}
    execution_infra_ok = all(
        by_key[k].passed
        for k in _INFRA_KEYS
        if k in by_key and by_key[k].blocks_execution
    )
    owner_ok = bool(
        by_key.get("owner_authorization") and by_key["owner_authorization"].passed
    )
    infra_ok = execution_infra_ok and owner_ok
    ready_for_canary = infra_ok
    ready_for_live = infra_ok

    if mode is OpsExecutionMode.SHADOW:
        # Promote endpoint advances SHADOW→CANARY→LIVE in one confirmed call
        # when infra locks pass (Demo cert is not a gate).
        next_target = "LIVE" if ready_for_live else "CANARY"
        ready_for_promotion = ready_for_canary
        blockers = tuple(
            _blocker_dict(i)
            for i in items
            if not i.passed and i.required_for_canary
        )
    elif mode is OpsExecutionMode.CANARY:
        next_target = "LIVE"
        ready_for_promotion = ready_for_live
        blockers = tuple(
            _blocker_dict(i)
            for i in items
            if not i.passed and i.required_for_live
        )
    else:
        next_target = "NONE"
        ready_for_promotion = False
        blockers = tuple(
            _blocker_dict(i)
            for i in items
            if not i.passed and i.blocks_execution
        )

    exec_blockers = tuple(i for i in items if not i.passed and i.blocks_execution)
    first_blocking = exec_blockers[0] if exec_blockers else None
    remaining = tuple(_blocker_dict(i) for i in exec_blockers)
    first_dict = _blocker_dict(first_blocking) if first_blocking else None
    exec_code = (
        first_blocking.execution_code
        if first_blocking and first_blocking.execution_code
        else None
    )
    state = dict(state)
    state["first_blocking_lock"] = first_dict
    state["remaining_locks"] = list(remaining)
    state["execution_block_code"] = exec_code

    plan: list[str] = []
    if mode is OpsExecutionMode.SHADOW:
        plan.append("POST /ite/ops/mode target=CANARY (confirmed)")
        plan.append("POST /ite/ops/mode target=LIVE (confirmed)")
    elif mode is OpsExecutionMode.CANARY:
        plan.append("POST /ite/ops/mode target=LIVE (confirmed)")
    plan.append("POST /ite/ops/auto-trading run_state=running (confirmed)")
    plan.append("GET /ite/ops/auto-trading — verify Gate Enabled")

    from app.application.services.ops_state_persistence import ops_state_diagnostics

    persistence = ops_state_diagnostics()
    verification = {
        "ops_mode": mode.value,
        "gate": snap.safety.status,
        "execution_enabled": exec_ok,
        "auto_trading": str(policy.to_dict().get("run_state", "off")).upper(),
        "gateway": "CONNECTED" if facts.gateway_connected else "OFFLINE",
        "broker": "CONNECTED" if facts.broker_connected else "OFF",
        "risk": "READY" if not risk_locked else "LOCKED",
        "safety": "READY" if not safety_locked else "LOCKED",
        "demo_certified": demo_ok,
        "demo_certification_required_for_live": False,
        "next_promotion_target": next_target,
        "primary_blocker": snap.primary_blocker,
        "blocking_category": snap.blocking_category,
        "first_blocking_lock": first_dict,
        "execution_block_code": exec_code,
        "persistence": persistence,
        "persisted_ops_mode": persistence.get("persisted_ops_mode"),
        "ops_mode_matches_persistence": (
            persistence.get("persisted_ops_mode") is None
            or str(persistence.get("persisted_ops_mode")).upper() == mode.value
        ),
    }

    return LaunchReadinessReport(
        ready_for_promotion=ready_for_promotion,
        ready_for_canary=ready_for_canary,
        ready_for_live=ready_for_live,
        ready_for_gate_enabled=bool(snap.safety.allowed),
        next_promotion_target=next_target,
        items=items,
        blockers=blockers,
        execution_state=state,
        promotion_plan=tuple(plan),
        demo_certified=demo_ok,
        verification=verification,
        first_blocking_lock=first_dict,
        remaining_locks=remaining,
        execution_block_code=exec_code,
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
    """Official stepwise promote: SHADOW→CANARY→LIVE when infra locks clear.

    Never sets EXECUTION_ENABLED. Never bypasses Risk/Safety.
    Demo Certification is not required for LIVE (OWNER policy).
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

    steps: list[dict[str, Any]] = []
    try:
        if plane.mode is OpsExecutionMode.SHADOW:
            if not pre.ready_for_canary:
                return {
                    "ok": False,
                    "promoted": False,
                    "message": "launch blockers remain — CANARY promotion refused",
                    "readiness": pre.to_dict(),
                }
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
            mid = build_launch_readiness(plane, settings=cfg, owner_authorized=True)
            if not mid.ready_for_live:
                return {
                    "ok": False,
                    "promoted": False,
                    "promoted_to": "CANARY" if steps else None,
                    "message": "launch blockers remain — LIVE promotion refused",
                    "steps": steps,
                    "readiness": mid.to_dict(),
                }
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
        "promoted_to": plane.mode.value,
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
