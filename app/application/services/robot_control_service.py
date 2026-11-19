"""Account-scoped robot controls: Start, Pause, Resume, Stop, Emergency Stop.

The stored state is the source of truth. It is read at the execution dispatch
boundary for every NEW entry (``entry_block``); closes and SL/TP management
are never blocked by it, and no control closes a position.

States
- RUNNING: new entries allowed (owner risk policy still applies).
- PAUSED: new entries blocked; Resume returns to RUNNING after readiness.
- STOPPED: new entries blocked; only Start returns to RUNNING (readiness).
- EMERGENCY_STOPPED: new entries blocked; only Start after an explicit reason.

Each user can only act on broker accounts they own. Every change writes an
audit event. One user's control never touches another user's account or the
global LIVE switch.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)

RUNNING = "RUNNING"
PAUSED = "PAUSED"
STOPPED = "STOPPED"
EMERGENCY_STOPPED = "EMERGENCY_STOPPED"
STATES = frozenset({RUNNING, PAUSED, STOPPED, EMERGENCY_STOPPED})

# action -> (allowed from-states, to-state, needs readiness)
TRANSITIONS: dict[str, tuple[frozenset[str], str, bool]] = {
    "pause": (frozenset({RUNNING}), PAUSED, False),
    "resume": (frozenset({PAUSED}), RUNNING, True),
    "stop": (frozenset({RUNNING, PAUSED}), STOPPED, False),
    "start": (frozenset({STOPPED, EMERGENCY_STOPPED}), RUNNING, True),
    "emergency_stop": (frozenset({RUNNING, PAUSED, STOPPED}), EMERGENCY_STOPPED, False),
}


class RobotControlError(Exception):
    def __init__(self, code: str, message: str, status: int = 409) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True, slots=True)
class Readiness:
    ready: bool
    checks: dict[str, Any] = field(default_factory=dict)
    reasons: tuple[str, ...] = ()


def _db() -> Any | None:
    from app.infrastructure.persistence import direct_postgres as dp

    return dp if dp.direct_postgres_available() else None


def _owned_account(
    dp: Any, *, user_id: UUID, broker_account_id: UUID
) -> dict[str, Any]:
    rows = dp.fetch(
        """
        SELECT a.id, a.user_id, a.external_account_id, a.server, a.environment,
               a.status, a.metadata, b.slug AS broker_slug
          FROM public.broker_accounts a
          LEFT JOIN public.brokers b ON b.id = a.broker_id
         WHERE a.id = $1::uuid AND a.user_id = $2::uuid
         LIMIT 1
        """,
        str(broker_account_id),
        str(user_id),
    )
    if not rows:
        raise RobotControlError("account_not_found", "Broker account not found", 404)
    return dict(rows[0])


def current_state(dp: Any, *, broker_account_id: UUID) -> str:
    rows = dp.fetch(
        "SELECT state FROM public.robot_account_controls"
        " WHERE broker_account_id = $1::uuid",
        str(broker_account_id),
    )
    return str(rows[0]["state"]) if rows else RUNNING


def list_accounts(*, user_id: UUID) -> list[dict[str, Any]]:
    """The caller's own broker accounts with robot state (no secrets)."""
    dp = _db()
    if dp is None:
        return []
    rows = dp.fetch(
        """
        SELECT a.id, a.external_account_id, a.server, a.environment, a.status,
               a.metadata, b.slug AS broker_slug, b.name AS broker_name,
               coalesce(c.state, 'RUNNING') AS robot_state,
               coalesce(c.reason, '') AS robot_reason, c.updated_at AS robot_updated_at
          FROM public.broker_accounts a
          LEFT JOIN public.brokers b ON b.id = a.broker_id
          LEFT JOIN public.robot_account_controls c ON c.broker_account_id = a.id
         WHERE a.user_id = $1::uuid AND lower(a.status) <> 'revoked'
         ORDER BY a.created_at
        """,
        str(user_id),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        meta = r.get("metadata") or {}
        if isinstance(meta, str):
            import json

            try:
                meta = json.loads(meta)
            except ValueError:
                meta = {}
        login = str(r.get("external_account_id") or "")
        out.append(
            {
                "broker_account_id": str(r["id"]),
                "_login": login,  # popped by the router; never returned
                "broker": str(r.get("broker_name") or r.get("broker_slug") or ""),
                "broker_slug": str(r.get("broker_slug") or ""),
                "login_masked": f"•••{login[-3:]}" if login else "",
                "server": str(r.get("server") or ""),
                "environment": str(r.get("environment") or "").upper(),
                "account_status": str(r.get("status") or ""),
                "trade_allowed_reported": str(meta.get("trade_allowed") or "unknown"),
                "verification": str(meta.get("verification") or ""),
                "robot_state": str(r.get("robot_state") or RUNNING),
                "robot_reason": str(r.get("robot_reason") or ""),
                "robot_updated_at": (
                    r["robot_updated_at"].isoformat()
                    if r.get("robot_updated_at") is not None
                    else None
                ),
            }
        )
    return out


def recent_events(*, user_id: UUID, limit: int = 50) -> list[dict[str, Any]]:
    dp = _db()
    if dp is None:
        return []
    rows = dp.fetch(
        """
        SELECT broker_account_id, action, state_before, state_after, reason,
               readiness, created_at
          FROM public.robot_control_events
         WHERE user_id = $1::uuid
         ORDER BY created_at DESC
         LIMIT $2
        """,
        str(user_id),
        int(max(1, min(limit, 200))),
    )
    return [
        {
            "broker_account_id": str(r["broker_account_id"]),
            "action": r["action"],
            "state_before": r["state_before"],
            "state_after": r["state_after"],
            "reason": r["reason"],
            "readiness": r.get("readiness") or {},
            "at": r["created_at"].isoformat(),
        }
        for r in rows
    ]


# -- Customer-facing activity and status (no owner policy details) ---------

# Execution intents carry internal block reasons (e.g. OWNER_MIN_RR with the
# threshold). Customers see a category only; the reason text never leaves
# the server through this API.
_ACTIVITY_OUTCOME = {
    "filled": "Executed",
    "executed": "Executed",
    "acked": "Executed",
    "submitted": "Sent to broker",
    "dispatched": "Sent to broker",
    "leased": "Sent to broker",
    "pending": "Queued",
    "queued": "Queued",
    "blocked": "Blocked by risk checks",
    "rejected": "Blocked by risk checks",
    "failed": "Failed at broker",
    "expired": "Expired",
    "cancelled": "Cancelled",
}


def activity_outcome(state: str, block_reason: str | None) -> str:
    key = str(state or "").strip().lower()
    if block_reason and key not in {"filled", "executed", "acked"}:
        reason = block_reason.upper()
        if "SUBSCRIPTION" in reason:
            return "Blocked: subscription inactive"
        if "ROBOT_" in reason:
            return "Blocked: robot paused or stopped"
        if "TRADE_ALLOWED" in reason or "PERMISSION" in reason:
            return "Blocked: trading disabled by broker"
        return "Blocked by risk checks"
    return _ACTIVITY_OUTCOME.get(key, "Recorded")


def recent_activity(*, user_id: UUID, limit: int = 20) -> list[dict[str, Any]]:
    """The caller's own recent execution attempts, sanitized."""
    dp = _db()
    if dp is None:
        return []
    rows = dp.fetch(
        """
        SELECT broker_account_id, state, block_reason, planned_volume,
               broker_ticket, payload, created_at
          FROM public.account_execution_intents
         WHERE user_id = $1::uuid
         ORDER BY created_at DESC
         LIMIT $2
        """,
        str(user_id),
        int(max(1, min(limit, 100))),
    )
    out: list[dict[str, Any]] = []
    for r in rows:
        payload = r.get("payload") or {}
        if isinstance(payload, str):
            import json

            try:
                payload = json.loads(payload)
            except ValueError:
                payload = {}
        out.append(
            {
                "broker_account_id": str(r["broker_account_id"]),
                "symbol": str(payload.get("symbol") or ""),
                "side": str(payload.get("side") or "").upper(),
                "volume": (
                    str(r["planned_volume"])
                    if r.get("planned_volume") is not None
                    else None
                ),
                "ticket": r.get("broker_ticket"),
                "outcome": activity_outcome(
                    str(r.get("state") or ""), r.get("block_reason")
                ),
                "at": r["created_at"].isoformat(),
            }
        )
    return out


# What the customer sees as the robot's real status. RUNNING is shown only
# when the control state is RUNNING *and* the backend has evidence that the
# account can trade *and* the subscription is active.
ROBOT_RUNNING = "ROBOT_RUNNING"
WAITING = "WAITING"


def robot_status(
    *,
    control_state: str,
    connection: dict[str, Any],
    entitled: bool | None,
    execution_enabled: bool | None = True,
) -> dict[str, str]:
    """``execution_enabled``: whether the platform path serving this account
    may submit orders right now (owner gateway: Live Trading Control; worker
    accounts: multi-account dispatch / LIVE submit flags). None = unknown."""
    if control_state in {PAUSED, STOPPED, EMERGENCY_STOPPED}:
        labels = {
            PAUSED: "Paused · no new entries",
            STOPPED: "Stopped",
            EMERGENCY_STOPPED: "Emergency stopped",
        }
        return {"code": control_state, "label": labels[control_state]}
    conn = str(connection.get("state") or "")
    if entitled is False:
        return {
            "code": WAITING,
            "label": "Not trading · subscription required",
        }
    if conn == ROBOT_READY and entitled is True:
        if execution_enabled is True:
            return {"code": ROBOT_RUNNING, "label": "Running"}
        return {
            "code": WAITING,
            "label": (
                "Not trading · automated execution is paused by the platform"
                if execution_enabled is False
                else "Not trading · execution status not confirmed"
            ),
        }
    reason = {
        UNAVAILABLE: "broker data unavailable",
        NOT_CONNECTED: "account not connected to a trading terminal yet",
        TRADING_PERMISSION_DISABLED: "trading disabled by the broker",
        REQUIRES_USER_ACTION: "check your MT5 login details",
        DEGRADED: "terminal degraded",
        CONNECTED: "trade permission not yet confirmed",
        BROKER_VERIFIED: "starting a trading terminal for your account",
    }.get(conn, "status not yet confirmed")
    return {"code": WAITING, "label": f"Not trading · {reason}"}


def apply_action(
    *,
    user_id: UUID,
    broker_account_id: UUID,
    action: str,
    reason: str = "",
    readiness_probe: Any | None = None,
) -> dict[str, Any]:
    """Validate ownership and transition, then persist state + audit event."""
    if action not in TRANSITIONS:
        raise RobotControlError("unknown_action", f"Unknown action {action}", 400)
    dp = _db()
    if dp is None:
        raise RobotControlError(
            "control_store_unavailable", "Robot control storage is unavailable", 503
        )
    account = _owned_account(dp, user_id=user_id, broker_account_id=broker_account_id)
    before = current_state(dp, broker_account_id=broker_account_id)
    allowed_from, after, needs_ready = TRANSITIONS[action]
    if before not in allowed_from:
        raise RobotControlError(
            "invalid_transition",
            f"Cannot {action.replace('_', ' ')} while the robot is {before}",
        )
    if action == "start" and before == EMERGENCY_STOPPED and not reason.strip():
        raise RobotControlError(
            "reason_required",
            "A reason is required to start after an emergency stop",
            400,
        )
    if action in {"resume", "start"}:
        from app.application.services.entitlements import check_trading_entitlement

        ent = check_trading_entitlement(user_id=user_id)
        if not ent.allowed:
            raise RobotControlError(
                "subscription_required",
                "Choose a subscription plan to activate your QuantForg Robot. "
                "Your broker connection stays saved.",
                402,
            )
    readiness = Readiness(ready=True)
    if needs_ready:
        probe = readiness_probe or account_readiness
        readiness = probe(account)
        if not readiness.ready:
            raise RobotControlError(
                "not_ready",
                "Account is not ready: " + ", ".join(readiness.reasons),
            )
    dp.execute_transaction(
        [
            (
                """
                INSERT INTO public.robot_account_controls
                    (broker_account_id, user_id, state, reason, updated_by, updated_at)
                VALUES ($1::uuid, $2::uuid, $3, $4, $2::uuid, now())
                ON CONFLICT (broker_account_id) DO UPDATE
                   SET state = EXCLUDED.state, reason = EXCLUDED.reason,
                       updated_by = EXCLUDED.updated_by, updated_at = now()
                 WHERE public.robot_account_controls.user_id = EXCLUDED.user_id
                """,
                (str(broker_account_id), str(user_id), after, reason[:300]),
            ),
            (
                """
                INSERT INTO public.robot_control_events
                    (broker_account_id, user_id, action, state_before, state_after,
                     reason, actor_id, readiness)
                VALUES ($1::uuid, $2::uuid, $3, $4, $5, $6, $2::uuid, $7::jsonb)
                """,
                (
                    str(broker_account_id),
                    str(user_id),
                    action,
                    before,
                    after,
                    reason[:300],
                    _json(readiness.checks),
                ),
            ),
        ]
    )
    logger.info(
        "robot_control_changed",
        broker_account_id=str(broker_account_id),
        action=action,
        state_before=before,
        state_after=after,
    )
    return {
        "broker_account_id": str(broker_account_id),
        "state_before": before,
        "state": after,
        "readiness": readiness.checks,
        "positions_closed": False,
    }


def _json(value: Any) -> str:
    import json

    return json.dumps(value, default=str)


def account_readiness(
    account: dict[str, Any],
    *,
    gateway_account: Any | None = None,
    workers: list[dict[str, Any]] | None = None,
) -> Readiness:
    """Revalidate before Resume/Start using real broker evidence.

    The owner's attached account is checked live on the gateway (same login,
    MT5 trade_allowed). Other accounts need a READY multi-account worker bound
    to them that reports trade_allowed. Anything unknown is not ready.
    """
    checks: dict[str, Any] = {}
    reasons: list[str] = []
    login = str(account.get("external_account_id") or "")
    gw_login = (
        str(getattr(gateway_account, "login", "") or "")
        if gateway_account is not None
        else ""
    )
    if gw_login and gw_login == login:
        allowed = getattr(gateway_account, "trade_allowed", None) is True
        checks.update(source="gateway", connected=True, trade_allowed=allowed)
        if not allowed:
            reasons.append("mt5_trade_allowed_false")
        return Readiness(ready=not reasons, checks=checks, reasons=tuple(reasons))
    bound = [
        w
        for w in (workers or [])
        if str(w.get("broker_account_id")) == str(account.get("id"))
    ]
    ready = [w for w in bound if w.get("dispatch_ready") and w.get("trade_allowed")]
    checks.update(source="worker", workers=len(bound), ready_workers=len(ready))
    if not bound:
        reasons.append("no_worker_assigned")
    elif not ready:
        reasons.append("worker_not_ready")
    return Readiness(ready=not reasons, checks=checks, reasons=tuple(reasons))


def entry_block(
    *,
    user_id: UUID | None,
    broker_account_id: UUID | None = None,
    login: int | None = None,
) -> str | None:
    """Reason string when NEW entries are blocked for this account, else None.

    Fail closed: when durable storage is configured but the state cannot be
    read, new entries are blocked. Without durable storage (local/tests) the
    robot is RUNNING.
    """
    if user_id is None:
        return None
    try:
        dp = _db()
    except Exception:
        return "ROBOT_CONTROL_UNAVAILABLE: robot state could not be read"
    if dp is None:
        return None
    try:
        if broker_account_id is not None:
            rows = dp.fetch(
                """
                SELECT state FROM public.robot_account_controls
                 WHERE broker_account_id = $1::uuid AND user_id = $2::uuid
                """,
                str(broker_account_id),
                str(user_id),
            )
        elif login is not None:
            rows = dp.fetch(
                """
                SELECT c.state FROM public.robot_account_controls c
                  JOIN public.broker_accounts a ON a.id = c.broker_account_id
                 WHERE c.user_id = $1::uuid AND a.external_account_id = $2
                """,
                str(user_id),
                str(int(login)),
            )
        else:
            return None
    except Exception:
        logger.exception("robot_control_read_failed")
        return "ROBOT_CONTROL_UNAVAILABLE: robot state could not be read"
    states = {str(r["state"]) for r in rows}
    blocked = states - {RUNNING}
    if not blocked:
        return None
    state = sorted(blocked)[0]
    return f"ROBOT_{state}: new entries are blocked for this account"


# --- verified connection state (never inferred from a "Connected" badge) -----

NOT_CONNECTED = "NOT_CONNECTED"
CONNECTED = "CONNECTED"
TRADING_PERMISSION_DISABLED = "TRADING_PERMISSION_DISABLED"
ROBOT_READY = "ROBOT_READY"
DEGRADED = "DEGRADED"
REQUIRES_USER_ACTION = "REQUIRES_USER_ACTION"
# Broker evidence could not be read (gateway/worker status timed out). Never
# shown as connected; new entries stay blocked by the execution path.
UNAVAILABLE = "UNAVAILABLE"
# MT5 accepted the login (verified); no live terminal session is held for it
# right now, e.g. no active subscription. The connection stays shown.
BROKER_VERIFIED = "BROKER_VERIFIED"

_USER_ACTION_ERRORS = ("login_failed", "password", "server_required", "invalid_account")


def connection_state(
    account: dict[str, Any],
    *,
    gateway_account: Any | None = None,
    workers: list[dict[str, Any]] | None = None,
    evidence_available: bool = True,
) -> dict[str, Any]:
    """Separate verified states from real MT5 evidence.

    CONNECTED means MT5 authenticated the login; it is not trading
    permission. ROBOT_READY additionally needs MT5 trade_allowed=true and a
    dispatch-ready session. Investor/read-only logins report
    trade_allowed=false and therefore stay TRADING_PERMISSION_DISABLED.
    """
    login = str(account.get("external_account_id") or "")
    gw_login = (
        str(getattr(gateway_account, "login", "") or "")
        if gateway_account is not None
        else ""
    )
    if gw_login and gw_login == login:
        allowed = getattr(gateway_account, "trade_allowed", None)
        if allowed is True:
            return {"state": ROBOT_READY, "source": "gateway", "trade_allowed": True}
        if allowed is False:
            return {
                "state": TRADING_PERMISSION_DISABLED,
                "source": "gateway",
                "trade_allowed": False,
            }
        return {"state": CONNECTED, "source": "gateway", "trade_allowed": None}
    bound = [
        w
        for w in (workers or [])
        if str(w.get("broker_account_id")) == str(account.get("id"))
    ]
    if not bound:
        if str(account.get("verification") or "") == "connected":
            return {
                "state": BROKER_VERIFIED,
                "source": "verification",
                "trade_allowed": None,
            }
        if not evidence_available:
            return {"state": UNAVAILABLE, "source": "none", "trade_allowed": None}
        return {"state": NOT_CONNECTED, "source": "none", "trade_allowed": None}
    w = bound[0]
    err = str(w.get("last_error") or "").lower()
    if any(tok in err for tok in _USER_ACTION_ERRORS):
        return {
            "state": REQUIRES_USER_ACTION,
            "source": "worker",
            "trade_allowed": None,
            "detail": "Check the MT5 login, master password and exact server.",
        }
    if not w.get("connected") and not w.get("ready"):
        return {"state": DEGRADED, "source": "worker", "trade_allowed": None}
    if w.get("trade_allowed") is not True:
        return {
            "state": TRADING_PERMISSION_DISABLED,
            "source": "worker",
            "trade_allowed": False,
        }
    if not w.get("dispatch_ready"):
        return {"state": DEGRADED, "source": "worker", "trade_allowed": True}
    return {"state": ROBOT_READY, "source": "worker", "trade_allowed": True}
