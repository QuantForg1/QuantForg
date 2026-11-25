"""Live verification state of a customer's MT5 broker connection.

A connect request is not "saved" and left there: the account's own worker
terminal logs in with the submitted credentials and the result is recorded
on the account:

- ``verifying``  - waiting for (or running) the real MT5 login;
- ``connected``  - MT5 accepted the login and trading is allowed;
- ``rejected``   - MT5 refused it (wrong login/password/server, investor
  password, trading disabled). The account and its stored password are
  revoked at once, so a wrong broker account is never kept.

Infrastructure failures (terminal/IPC) are not the user's fault and leave the
account ``verifying`` so the worker retries.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)

VERIFYING = "verifying"
CONNECTED = "connected"
REJECTED = "rejected"

# (needle in the worker error, reason code, trader-facing message)
_REJECTIONS: tuple[tuple[str, str, str], ...] = (
    (
        "authorization failed",
        "INVALID_CREDENTIALS",
        "MT5 rejected the login: check the account number, password and server.",
    ),
    (
        "invalid account",
        "INVALID_CREDENTIALS",
        "MT5 rejected the login: check the account number, password and server.",
    ),
    (
        "(-6,",
        "INVALID_CREDENTIALS",
        "MT5 rejected the login: check the account number, password and server.",
    ),
    (
        "login_failed",
        "INVALID_CREDENTIALS",
        "MT5 rejected the login: check the account number, password and server.",
    ),
    (
        "login_account_mismatch",
        "INVALID_CREDENTIALS",
        "The terminal logged into a different account than the one entered.",
    ),
    (
        "authenticated_trading_not_enabled",
        "TRADING_NOT_ALLOWED",
        "Logged in, but this account cannot trade. Use the master (trading) "
        "password, not the investor password, and check the account is enabled.",
    ),
    (
        "server",
        "SERVER_NOT_FOUND",
        "MT5 could not reach that server. Copy the exact server name from your "
        "broker portal.",
    ),
)


def classify_failure(error: str) -> tuple[str, str, str] | None:
    """(state, code, message) for a user-caused failure; None = retry later."""
    text = (error or "").lower()
    if not text:
        return None
    # Terminal / IPC / network trouble on our side is retried, never blamed on
    # the user's credentials.
    if any(
        k in text
        for k in ("ipc", "initialize_failed:(-10", "terminal", "timeout", "attach")
    ) and not any(k in text for k in ("authorization", "(-6,")):
        return None
    for needle, code, message in _REJECTIONS:
        if needle in text:
            return REJECTED, code, message
    return None


# A first "-6 Authorization failed" from a freshly started terminal is often
# only the broker's server list not being downloaded yet. A customer is told
# "rejected" only after the same account fails twice in a row.
AUTH_FAILURES_BEFORE_REJECT = 2


def is_auth_failure(error: str) -> bool:
    text = (error or "").lower()
    return "authorization failed" in text or "(-6," in text


def count_auth_failure(
    broker_account_id: UUID | str,
    *,
    fetch: Any | None = None,
    execute: Any | None = None,
) -> int:
    """Increment and return the account's consecutive auth-failure counter."""
    if fetch is None or execute is None:
        from app.infrastructure.persistence.direct_postgres import (
            execute as _execute,
            fetch as _fetch,
        )

        fetch = fetch or _fetch
        execute = execute or _execute
    try:
        rows = fetch(
            "SELECT coalesce(metadata->>'auth_fail_count','0') AS n "
            "FROM public.broker_accounts WHERE id = $1::uuid",
            str(broker_account_id),
        )
        current = int(str((rows[0] if rows else {}).get("n") or "0") or 0)
    except Exception:
        logger.exception("broker_verification_auth_count_read_failed")
        return AUTH_FAILURES_BEFORE_REJECT  # cannot count: keep old behaviour
    nxt = current + 1
    try:
        execute(
            """
            UPDATE public.broker_accounts
               SET metadata = coalesce(metadata, '{}'::jsonb) || $2::jsonb,
                   updated_at = now()
             WHERE id = $1::uuid AND status <> 'revoked'
            """,
            str(broker_account_id),
            json.dumps({"auth_fail_count": str(nxt)}),
        )
    except Exception:
        logger.exception("broker_verification_auth_count_write_failed")
    return nxt


def _now() -> str:
    return datetime.now(UTC).isoformat()


def mark(
    broker_account_id: UUID | str,
    *,
    state: str,
    code: str = "",
    message: str = "",
    fetch: Any | None = None,
    execute: Any | None = None,
) -> bool:
    """Record a verification state. ``rejected`` also revokes the account."""
    if fetch is None or execute is None:
        from app.infrastructure.persistence.direct_postgres import (
            execute as _execute,
            fetch as _fetch,
        )

        fetch = fetch or _fetch
        execute = execute or _execute
    patch = {
        "verification": state,
        "verification_code": code,
        "verification_message": message,
        "verification_at": _now(),
    }
    if state == CONNECTED:
        patch["last_verified"] = patch["verification_at"]
        patch["assignment"] = "connected"
    try:
        if state == REJECTED:
            execute(
                """
                UPDATE public.broker_accounts
                   SET metadata = coalesce(metadata, '{}'::jsonb) || $2::jsonb
                                  || '{"selected": "false"}'::jsonb,
                       status = 'revoked',
                       updated_at = now()
                 WHERE id = $1::uuid
                """,
                str(broker_account_id),
                json.dumps(patch),
            )
            execute(
                """
                UPDATE public.broker_credentials
                   SET status = 'revoked', updated_at = now()
                 WHERE broker_account_id = $1::uuid
                """,
                str(broker_account_id),
            )
        else:
            execute(
                """
                UPDATE public.broker_accounts
                   SET metadata = coalesce(metadata, '{}'::jsonb) || $2::jsonb,
                       updated_at = now()
                 WHERE id = $1::uuid AND status <> 'revoked'
                """,
                str(broker_account_id),
                json.dumps(patch),
            )
    except Exception:
        logger.exception("broker_verification_mark_failed")
        return False
    logger.info(
        "broker_verification_state",
        broker_account_id=str(broker_account_id),
        state=state,
        code=code,
    )
    return True


def mark_idle(broker_account_id: UUID | str, *, execute: Any | None = None) -> bool:
    """Verified, no subscription: keep 'connected', release the terminal."""
    if execute is None:
        from app.infrastructure.persistence.direct_postgres import (
            execute as _execute,
        )

        execute = _execute
    try:
        execute(
            """
            UPDATE public.broker_accounts
               SET metadata = coalesce(metadata, '{}'::jsonb)
                              || '{"assignment": "verified_idle"}'::jsonb,
                   updated_at = now()
             WHERE id = $1::uuid AND status <> 'revoked'
            """,
            str(broker_account_id),
        )
    except Exception:
        logger.exception("broker_verification_idle_failed")
        return False
    return True


def status_for_user(user_id: UUID | str, *, fetch: Any | None = None) -> dict[str, Any]:
    """Latest connect attempt for the user (including a just-rejected one)."""
    if fetch is None:
        from app.infrastructure.persistence.direct_postgres import fetch as _fetch

        fetch = _fetch
    try:
        rows = fetch(
            """
            SELECT a.id, a.status, a.environment, a.external_account_id,
                   a.server, a.metadata, a.updated_at, b.slug, b.name
              FROM public.broker_accounts a
              JOIN public.brokers b ON b.id = a.broker_id
             WHERE a.user_id = $1::uuid
               AND (a.status <> 'revoked'
                    OR a.metadata->>'verification' = 'rejected')
             ORDER BY a.updated_at DESC
             LIMIT 1
            """,
            str(user_id),
        )
    except Exception:
        logger.exception("broker_verification_status_failed")
        return {"state": "unknown", "message": "Status is unavailable right now."}
    if not rows:
        return {"state": "none"}
    row = rows[0]
    meta = row.get("metadata") or {}
    if isinstance(meta, str):
        meta = json.loads(meta)
    state = str(meta.get("verification") or "")
    if not state:
        state = CONNECTED if meta.get("last_verified") else VERIFYING
    login = str(row.get("external_account_id") or "")
    from app.application.services.entitlements import check_trading_entitlement

    try:
        subscribed = bool(check_trading_entitlement(user_id=UUID(str(user_id))).allowed)
    except Exception:
        subscribed = False
    verifier_online: bool | None = None
    if state == VERIFYING:
        verifier_online = _verifier_online(fetch)
    return {
        "verifier_online": verifier_online,
        "subscription_active": subscribed,
        "robot_ready": state == CONNECTED and subscribed,
        "state": state,
        "code": str(meta.get("verification_code") or ""),
        "message": str(meta.get("verification_message") or ""),
        "broker": str(row.get("name") or row.get("slug") or ""),
        "server": str(row.get("server") or ""),
        "account": f"***{login[-4:]}" if login else "",
        "environment": str(row.get("environment") or ""),
        "submitted_at": str(meta.get("submitted_at") or ""),
        "verified_at": str(meta.get("verification_at") or ""),
    }


# Tolerate worker restarts and slow login cycles: only call the verifier offline
# after 15 minutes without any heartbeat (workers beat every ~30 s).
VERIFIER_HEARTBEAT_SECONDS = 900


def _verifier_online(fetch: Any) -> bool | None:
    """True if any MT5 verification worker sent a heartbeat recently.

    ``None`` when it cannot be determined (never reported as healthy).
    """
    try:
        rows = fetch(
            """
            SELECT count(*) AS n
              FROM public.mt5_worker_control_plane
             WHERE revoked = false
               AND last_heartbeat_at > now() - make_interval(secs => $1)
            """,
            VERIFIER_HEARTBEAT_SECONDS,
        )
    except Exception:
        logger.warning("broker_verifier_heartbeat_check_failed")
        return None
    if not rows:
        return None
    return int(rows[0].get("n") or 0) > 0
