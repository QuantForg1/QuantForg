"""Admin portal: manage customers, their feature access and broker accounts.

Every write:
* is refused for the acting admin's own account and for owner/admin accounts
  (they are managed by the designated-owner policy, never from this portal);
* is recorded in ``public.audit_logs`` with the admin as actor and a reason;
* never closes positions. Stopping a robot or removing a broker stops new
  entries; open positions keep their broker-side stop loss / take profit.

Role changes are limited to ``trader`` / ``viewer``: owner/admin can never be
granted here (``require_roles`` also ignores those roles unless the email is
the designated owner).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)

FEATURES = ("robot_trading", "signals", "ai_assistant", "broker_connect")
FEATURE_LABELS = {
    "robot_trading": "Robot trading",
    "signals": "Signals",
    "ai_assistant": "AI Assistant",
    "broker_connect": "Connect brokers",
}
ASSIGNABLE_ROLES = ("trader", "viewer")
PRIVILEGED_ROLES = frozenset({"owner", "admin"})
STATUS_ACTIONS = {
    "suspend": ("suspended", "suspend"),
    "reactivate": ("active", "activate"),
    "deactivate": ("deactivated", "deactivate"),
}
BROKER_ACTIONS = ("disable", "enable", "remove")


class AdminActionError(Exception):
    def __init__(self, code: str, message: str, status: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


@dataclass(frozen=True, slots=True)
class Actor:
    user_id: UUID
    email: str
    ip: str = ""
    user_agent: str = ""


def _db() -> tuple[Any, Any, Any]:
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
        execute,
        execute_transaction,
        fetch,
    )

    if not direct_postgres_available():
        raise AdminActionError("store_unavailable", "Database is unavailable", 503)
    return fetch, execute, execute_transaction


def _reason(reason: str) -> str:
    text = (reason or "").strip()
    if len(text) < 3:
        raise AdminActionError(
            "reason_required", "Give a short reason (3+ characters)."
        )
    return text[:500]


def _audit_sql(
    actor: Actor,
    *,
    action: str,
    resource_type: str,
    resource_id: str,
    message: str,
    metadata: dict[str, Any],
) -> tuple[str, tuple[Any, ...]]:
    return (
        """
        INSERT INTO public.audit_logs
            (action, outcome, resource_type, resource_id, actor_user_id,
             ip_address, user_agent, message, metadata)
        VALUES ($1, 'success', $2, $3::uuid, $4::uuid, $5, $6, $7, $8::jsonb)
        """,
        (
            action,
            resource_type,
            resource_id,
            str(actor.user_id),
            actor.ip[:64],
            actor.user_agent[:512],
            message[:1000],
            json.dumps({"admin_portal": True, "actor_email": actor.email, **metadata}),
        ),
    )


def _target(fetch: Any, user_id: UUID, actor: Actor) -> dict[str, Any]:
    rows = fetch(
        "SELECT id, email, display_name, role::text AS role, status::text AS status "
        "FROM public.users WHERE id = $1::uuid",
        str(user_id),
    )
    if not rows:
        raise AdminActionError("user_not_found", "User not found", 404)
    row: dict[str, Any] = dict(rows[0])
    if str(row["id"]) == str(actor.user_id):
        raise AdminActionError(
            "self_action", "You cannot change your own account here.", 403
        )
    if str(row.get("role") or "").lower() in PRIVILEGED_ROLES:
        raise AdminActionError(
            "privileged_target",
            "Owner and admin accounts cannot be changed from the admin portal.",
            403,
        )
    return row


# ------------------------------------------------------------------ reading


def list_users(
    *, query: str = "", status: str = "", limit: int = 200, fetch: Any | None = None
) -> dict[str, Any]:
    if fetch is None:
        fetch = _db()[0]
    q = (query or "").strip().lower()
    st = (status or "").strip().lower()
    rows = fetch(
        """
        SELECT u.id, u.email, u.display_name, u.role::text AS role,
               u.status::text AS status, u.created_at, u.last_login_at,
               (SELECT count(*) FROM public.broker_accounts a
                 WHERE a.user_id = u.id AND lower(a.status) <> 'revoked') AS brokers,
               (SELECT l.status FROM public.licenses l WHERE l.user_id = u.id
                 ORDER BY l.created_at DESC LIMIT 1) AS license_status,
               (SELECT l.expires_at FROM public.licenses l WHERE l.user_id = u.id
                 ORDER BY l.created_at DESC LIMIT 1) AS license_expires_at,
               (SELECT count(*) FROM public.user_access_overrides o
                 WHERE o.user_id = u.id AND o.allowed = false) AS restrictions
          FROM public.users u
         WHERE ($1 = '' OR lower(u.email) LIKE '%' || $1 || '%'
                OR lower(coalesce(u.display_name, '')) LIKE '%' || $1 || '%')
           AND ($2 = '' OR lower(u.status::text) = $2)
         ORDER BY u.created_at DESC
         LIMIT $3
        """,
        q,
        st,
        max(1, min(int(limit), 500)),
    )
    users = [_user_row(r) for r in rows]
    counts: dict[str, int] = {}
    for u in users:
        counts[u["status"]] = counts.get(u["status"], 0) + 1
    return {"users": users, "count": len(users), "by_status": counts}


def _iso(v: Any) -> str | None:
    return v.isoformat() if hasattr(v, "isoformat") else (str(v) if v else None)


def _user_row(r: dict[str, Any]) -> dict[str, Any]:
    license_status = str(r.get("license_status") or "").lower()
    return {
        "id": str(r["id"]),
        "email": r.get("email"),
        "display_name": r.get("display_name") or "",
        "role": str(r.get("role") or "").lower(),
        "status": str(r.get("status") or "").lower(),
        "created_at": _iso(r.get("created_at")),
        "last_login_at": _iso(r.get("last_login_at")),
        "brokers": int(r.get("brokers") or 0),
        "subscription": license_status or "none",
        "subscription_expires_at": _iso(r.get("license_expires_at")),
        "restrictions": int(r.get("restrictions") or 0),
        "manageable": str(r.get("role") or "").lower() not in PRIVILEGED_ROLES,
    }


def user_detail(user_id: UUID, *, fetch: Any | None = None) -> dict[str, Any]:
    if fetch is None:
        fetch = _db()[0]
    rows = fetch(
        """
        SELECT u.id, u.email, u.display_name, u.role::text AS role,
               u.status::text AS status, u.created_at, u.last_login_at,
               0 AS brokers, NULL AS license_status, NULL AS license_expires_at,
               0 AS restrictions
          FROM public.users u WHERE u.id = $1::uuid
        """,
        str(user_id),
    )
    if not rows:
        raise AdminActionError("user_not_found", "User not found", 404)
    user = _user_row(rows[0])
    access_rows = fetch(
        "SELECT feature, allowed, reason, updated_at FROM public.user_access_overrides "
        "WHERE user_id = $1::uuid",
        str(user_id),
    )
    overrides = {str(r["feature"]): r for r in access_rows}
    user["access"] = [
        {
            "feature": f,
            "label": FEATURE_LABELS[f],
            "allowed": bool(overrides[f]["allowed"]) if f in overrides else True,
            "overridden": f in overrides,
            "reason": str(overrides[f].get("reason") or "") if f in overrides else "",
        }
        for f in FEATURES
    ]
    user["brokers_list"] = list_brokers(user_id=user_id, fetch=fetch)["brokers"]
    lic = fetch(
        "SELECT id, status, tier, expires_at, created_at FROM public.licenses "
        "WHERE user_id = $1::uuid ORDER BY created_at DESC LIMIT 5",
        str(user_id),
    )
    user["licenses"] = [
        {
            "id": str(r["id"]),
            "status": str(r.get("status") or "").lower(),
            "plan": r.get("tier"),
            "expires_at": _iso(r.get("expires_at")),
            "created_at": _iso(r.get("created_at")),
        }
        for r in lic
    ]
    if user["licenses"]:
        user["subscription"] = user["licenses"][0]["status"]
        user["subscription_expires_at"] = user["licenses"][0]["expires_at"]
    user["brokers"] = len([b for b in user["brokers_list"] if b["status"] != "revoked"])
    user["restrictions"] = len([a for a in user["access"] if not a["allowed"]])
    user["audit"] = recent_audit(user_id=user_id, fetch=fetch)
    return user


def list_brokers(
    *,
    user_id: UUID | None = None,
    include_removed: bool = False,
    fetch: Any | None = None,
) -> dict[str, Any]:
    if fetch is None:
        fetch = _db()[0]
    rows = fetch(
        """
        SELECT a.id, a.user_id, u.email, a.label, a.external_account_id,
               a.server, a.environment, a.status, a.created_at, a.updated_at,
               a.metadata->>'verification' AS verification,
               a.metadata->>'assignment' AS assignment,
               a.metadata->>'admin_note' AS admin_note,
               c.state AS robot_state
          FROM public.broker_accounts a
          JOIN public.users u ON u.id = a.user_id
          LEFT JOIN public.robot_account_controls c ON c.broker_account_id = a.id
         WHERE ($1::uuid IS NULL OR a.user_id = $1::uuid)
           AND ($2 OR lower(a.status) <> 'revoked')
         ORDER BY a.updated_at DESC NULLS LAST
         LIMIT 500
        """,
        str(user_id) if user_id else None,
        bool(include_removed),
    )
    return {
        "brokers": [
            {
                "id": str(r["id"]),
                "user_id": str(r["user_id"]),
                "email": r.get("email"),
                "broker": r.get("label") or "",
                "account": _mask(r.get("external_account_id")),
                "server": r.get("server") or "",
                "environment": str(r.get("environment") or "").lower(),
                "status": str(r.get("status") or "").lower(),
                "verification": r.get("verification") or "",
                "assignment": r.get("assignment") or "",
                "robot_state": r.get("robot_state") or "STOPPED",
                "admin_note": r.get("admin_note") or "",
                "updated_at": _iso(r.get("updated_at")),
            }
            for r in rows
        ]
    }


def _mask(account: Any) -> str:
    s = str(account or "")
    return s if len(s) <= 4 else "•" * (len(s) - 4) + s[-4:]


def recent_audit(
    *, user_id: UUID | None = None, limit: int = 30, fetch: Any | None = None
) -> list[dict[str, Any]]:
    if fetch is None:
        fetch = _db()[0]
    rows = fetch(
        """
        SELECT l.action, l.resource_type, l.resource_id, l.message, l.occurred_at,
               l.metadata->>'actor_email' AS actor_email,
               l.metadata->>'target_user_id' AS target_user_id
          FROM public.audit_logs l
         WHERE (l.metadata->>'admin_portal') = 'true'
           AND ($1::text IS NULL OR l.metadata->>'target_user_id' = $1::text)
         ORDER BY l.occurred_at DESC
         LIMIT $2
        """,
        str(user_id) if user_id else None,
        max(1, min(int(limit), 200)),
    )
    return [
        {
            "action": r.get("action"),
            "resource_type": r.get("resource_type"),
            "message": r.get("message"),
            "actor": r.get("actor_email"),
            "at": _iso(r.get("occurred_at")),
        }
        for r in rows
    ]


# ------------------------------------------------------------------ writes


def _stop_robots_sql(
    user_id: str, actor: Actor, note: str
) -> list[tuple[str, tuple[Any, ...]]]:
    """Set every robot of the user to STOPPED (no new entries)."""
    return [
        (
            """
            INSERT INTO public.robot_account_controls
                (broker_account_id, user_id, state, reason, updated_by, updated_at)
            SELECT a.id, a.user_id, 'STOPPED', $2, $3::uuid, now()
              FROM public.broker_accounts a
             WHERE a.user_id = $1::uuid
            ON CONFLICT (broker_account_id) DO UPDATE
               SET state = 'STOPPED', reason = EXCLUDED.reason,
                   updated_by = EXCLUDED.updated_by, updated_at = now()
            """,
            (user_id, note[:300], str(actor.user_id)),
        )
    ]


def set_user_status(
    user_id: UUID, action: str, *, reason: str, actor: Actor, db: Any | None = None
) -> dict[str, Any]:
    if action not in STATUS_ACTIONS:
        raise AdminActionError("unknown_action", f"Unknown action {action}")
    fetch, _execute, tx = db or _db()
    note = _reason(reason)
    target = _target(fetch, user_id, actor)
    new_status, audit_action = STATUS_ACTIONS[action]
    before = str(target.get("status") or "").lower()
    if before == new_status:
        return {"user_id": str(user_id), "status": new_status, "changed": False}
    stmts: list[tuple[str, tuple[Any, ...]]] = [
        (
            """
            UPDATE public.users
               SET status = $2,
                   deactivated_at = CASE WHEN $2 = 'deactivated' THEN now()
                                         WHEN $2 = 'active' THEN NULL
                                         ELSE deactivated_at END,
                   updated_at = now()
             WHERE id = $1::uuid
            """,
            (str(user_id), new_status),
        )
    ]
    if new_status != "active":
        robots = fetch(
            "SELECT 1 FROM public.broker_accounts WHERE user_id = $1::uuid LIMIT 1",
            str(user_id),
        )
        if robots:
            stmts += _stop_robots_sql(str(user_id), actor, f"Admin {action}: {note}")
    stmts.append(
        _audit_sql(
            actor,
            action=audit_action,
            resource_type="user",
            resource_id=str(user_id),
            message=f"{action} user {target.get('email')}: {note}",
            metadata={
                "target_user_id": str(user_id),
                "before": before,
                "after": new_status,
            },
        )
    )
    tx(stmts)
    logger.info(
        "admin_user_status", user_id=str(user_id), before=before, after=new_status
    )
    return {"user_id": str(user_id), "status": new_status, "changed": True}


def update_user(
    user_id: UUID,
    *,
    display_name: str | None,
    role: str | None,
    reason: str,
    actor: Actor,
    db: Any | None = None,
) -> dict[str, Any]:
    fetch, _execute, tx = db or _db()
    note = _reason(reason)
    target = _target(fetch, user_id, actor)
    changes: dict[str, Any] = {}
    if display_name is not None:
        name = display_name.strip()
        if not 1 <= len(name) <= 120:
            raise AdminActionError("invalid_name", "Name must be 1-120 characters.")
        if name != (target.get("display_name") or ""):
            changes["display_name"] = name
    if role is not None:
        r = role.strip().lower()
        if r not in ASSIGNABLE_ROLES:
            raise AdminActionError(
                "invalid_role", "Role can only be set to trader or viewer here.", 403
            )
        if r != str(target.get("role") or "").lower():
            changes["role"] = r
    if not changes:
        return {"user_id": str(user_id), "changed": False}
    tx(
        [
            (
                """
                UPDATE public.users
                   SET display_name = coalesce($2, display_name),
                       role = coalesce($3, role::text),
                       updated_at = now()
                 WHERE id = $1::uuid
                """,
                (str(user_id), changes.get("display_name"), changes.get("role")),
            ),
            _audit_sql(
                actor,
                action="update",
                resource_type="user",
                resource_id=str(user_id),
                message=f"update user {target.get('email')}: {note}",
                metadata={"target_user_id": str(user_id), "changes": changes},
            ),
        ]
    )
    return {"user_id": str(user_id), "changed": True, "changes": changes}


def set_access(
    user_id: UUID,
    feature: str,
    *,
    allowed: bool,
    reason: str,
    actor: Actor,
    db: Any | None = None,
) -> dict[str, Any]:
    if feature not in FEATURES:
        raise AdminActionError("unknown_feature", f"Unknown feature {feature}")
    fetch, _execute, tx = db or _db()
    note = _reason(reason)
    target = _target(fetch, user_id, actor)
    stmts: list[tuple[str, tuple[Any, ...]]] = []
    if allowed:
        # Restoring default access: remove the override row (if any).
        existing = fetch(
            "SELECT 1 FROM public.user_access_overrides "
            "WHERE user_id = $1::uuid AND feature = $2",
            str(user_id),
            feature,
        )
        if existing:
            stmts.append(
                (
                    "DELETE FROM public.user_access_overrides "
                    "WHERE user_id = $1::uuid AND feature = $2",
                    (str(user_id), feature),
                )
            )
    else:
        stmts.append(
            (
                """
                INSERT INTO public.user_access_overrides
                    (user_id, feature, allowed, reason, set_by, updated_at)
                VALUES ($1::uuid, $2, false, $3, $4::uuid, now())
                ON CONFLICT (user_id, feature) DO UPDATE
                   SET allowed = false, reason = EXCLUDED.reason,
                       set_by = EXCLUDED.set_by, updated_at = now()
                """,
                (str(user_id), feature, note, str(actor.user_id)),
            )
        )
        if feature == "robot_trading":
            robots = fetch(
                "SELECT 1 FROM public.broker_accounts WHERE user_id = $1::uuid LIMIT 1",
                str(user_id),
            )
            if robots:
                stmts += _stop_robots_sql(
                    str(user_id), actor, f"Access removed: {note}"
                )
    if not stmts:
        return {
            "user_id": str(user_id),
            "feature": feature,
            "allowed": True,
            "changed": False,
        }
    stmts.append(
        _audit_sql(
            actor,
            action="update" if allowed else "revoke",
            resource_type="user_access",
            resource_id=str(user_id),
            message=(
                f"{'restore' if allowed else 'remove'} {FEATURE_LABELS[feature]} "
                f"for {target.get('email')}: {note}"
            ),
            metadata={
                "target_user_id": str(user_id),
                "feature": feature,
                "allowed": allowed,
            },
        )
    )
    tx(stmts)
    clear_access_cache()
    return {
        "user_id": str(user_id),
        "feature": feature,
        "allowed": allowed,
        "changed": True,
    }


def broker_action(
    broker_account_id: UUID,
    action: str,
    *,
    reason: str,
    actor: Actor,
    db: Any | None = None,
) -> dict[str, Any]:
    """disable: stop using it (reversible); enable: allow again;
    remove: revoke the account and its stored credentials (permanent)."""
    if action not in BROKER_ACTIONS:
        raise AdminActionError("unknown_action", f"Unknown action {action}")
    fetch, _execute, tx = db or _db()
    note = _reason(reason)
    rows = fetch(
        "SELECT a.id, a.user_id, a.status, a.label, a.external_account_id, "
        "u.role::text AS role, u.email FROM public.broker_accounts a "
        "JOIN public.users u ON u.id = a.user_id WHERE a.id = $1::uuid",
        str(broker_account_id),
    )
    if not rows:
        raise AdminActionError("broker_not_found", "Broker account not found", 404)
    acc = rows[0]
    if str(acc.get("role") or "").lower() in PRIVILEGED_ROLES:
        raise AdminActionError(
            "privileged_target",
            "The owner's live broker cannot be changed from the admin portal.",
            403,
        )
    before = str(acc.get("status") or "").lower()
    if before == "revoked":
        raise AdminActionError(
            "already_removed", "This broker account was already removed.", 409
        )
    target_status = {"disable": "disabled", "enable": "active", "remove": "revoked"}[
        action
    ]
    if before == target_status:
        return {
            "broker_account_id": str(broker_account_id),
            "status": before,
            "changed": False,
        }
    if action == "enable" and before != "disabled":
        raise AdminActionError(
            "not_disabled", "Only a disabled broker can be enabled.", 409
        )
    meta = {"admin_note": note[:200], "selected": "false"} if action != "enable" else {}
    stmts: list[tuple[str, tuple[Any, ...]]] = [
        (
            """
            UPDATE public.broker_accounts
               SET status = $2,
                   metadata = coalesce(metadata, '{}'::jsonb) || $3::jsonb,
                   updated_at = now()
             WHERE id = $1::uuid
            """,
            (str(broker_account_id), target_status, json.dumps(meta)),
        )
    ]
    if action == "remove":
        stmts.append(
            (
                """
                UPDATE public.broker_credentials
                   SET status = 'revoked', updated_at = now()
                 WHERE broker_account_id = $1::uuid AND status <> 'revoked'
                """,
                (str(broker_account_id),),
            )
        )
    if action in {"disable", "remove"}:
        stmts.append(
            (
                """
                INSERT INTO public.robot_account_controls
                    (broker_account_id, user_id, state, reason, updated_by, updated_at)
                VALUES ($1::uuid, $2::uuid, 'STOPPED', $3, $4::uuid, now())
                ON CONFLICT (broker_account_id) DO UPDATE
                   SET state = 'STOPPED', reason = EXCLUDED.reason,
                       updated_by = EXCLUDED.updated_by, updated_at = now()
                """,
                (
                    str(broker_account_id),
                    str(acc["user_id"]),
                    f"Admin {action}: {note}"[:300],
                    str(actor.user_id),
                ),
            )
        )
    stmts.append(
        _audit_sql(
            actor,
            action={"disable": "deactivate", "enable": "activate", "remove": "revoke"}[
                action
            ],
            resource_type="broker_account",
            resource_id=str(broker_account_id),
            message=(
                f"{action} broker {acc.get('label')} for {acc.get('email')}: {note}"
            ),
            metadata={
                "target_user_id": str(acc["user_id"]),
                "before": before,
                "after": target_status,
            },
        )
    )
    _run_tx_tolerant(tx, stmts)
    logger.info(
        "admin_broker_action",
        broker_account_id=str(broker_account_id),
        action=action,
        before=before,
        after=target_status,
    )
    return {
        "broker_account_id": str(broker_account_id),
        "status": target_status,
        "changed": True,
    }


def _run_tx_tolerant(tx: Any, stmts: list[tuple[str, tuple[Any, ...]]]) -> None:
    """Credentials may already be revoked (0 rows): run without that update."""
    from app.infrastructure.persistence.direct_postgres import TransactionNoRow

    try:
        tx(stmts)
    except TransactionNoRow:
        tx([s for s in stmts if "broker_credentials" not in s[0]])


# --------------------------------------------------------- enforcement


_ACCESS_CACHE: dict[tuple[str, str], tuple[float, bool]] = {}
_ACCESS_TTL_S = 15.0


def clear_access_cache() -> None:
    _ACCESS_CACHE.clear()


def feature_allowed(
    user_id: UUID | str, feature: str, *, fetch: Any | None = None
) -> bool:
    """False only when an admin removed this feature for the user.

    Unknown (storage unreadable) → allowed, so an outage never locks out
    paying customers; billing/subscription checks still apply separately.
    """
    import time

    key = (str(user_id), feature)
    now = time.monotonic()
    hit = _ACCESS_CACHE.get(key)
    if hit and hit[0] > now:
        return hit[1]
    try:
        if fetch is None:
            from app.infrastructure.persistence.direct_postgres import (
                direct_postgres_available,
                fetch as _fetch,
            )

            if not direct_postgres_available():
                return True
            fetch = _fetch
        rows = fetch(
            "SELECT allowed FROM public.user_access_overrides "
            "WHERE user_id = $1::uuid AND feature = $2",
            str(user_id),
            feature,
        )
        allowed = not rows or bool(rows[0].get("allowed"))
    except Exception:
        logger.exception("feature_access_read_failed", feature=feature)
        return True
    _ACCESS_CACHE[key] = (now + _ACCESS_TTL_S, allowed)
    return allowed
