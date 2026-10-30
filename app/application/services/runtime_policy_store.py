"""Persist and load the versioned runtime trading policy.

A failed read does not fall back to a previous document. Tests without a
database receive the approved baseline. Production without a database
fails closed.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from app.domain.identity.designated_owner import DESIGNATED_OWNER_EMAIL
from app.domain.institutional_trading.runtime_policy import (
    PolicyDecision,
    approved_baseline,
    use_runtime_policy,
    validate_policy_changes,
)
from core.logging import get_logger

logger_name = "runtime_policy_store"
logger = get_logger(logger_name)
_LOCK = threading.Lock()
_MEMORY: dict[str, Any] | None = None
_MEMORY_VERSION = 0
_SCHEMA_READY = False
_LAST_APPLIED: dict[str, Any] = {}
_LOGGED_VERSION: dict[str, int | None] = {"version": None}
_AUDIT: list[dict[str, Any]] = []

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS public.trading_runtime_config (
    id SMALLINT PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    version INTEGER NOT NULL CHECK (version >= 1),
    document JSONB NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID
)
"""

_ROLE_FUNCTION = """
CREATE OR REPLACE FUNCTION public.forbid_self_service_role_change()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
DECLARE
  jwt_role text;
BEGIN
  jwt_role := current_setting('request.jwt.claim.role', true);
  IF jwt_role IS NULL OR jwt_role = '' OR jwt_role = 'service_role' THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'UPDATE' AND NEW.role IS NOT DISTINCT FROM OLD.role THEN
    RETURN NEW;
  END IF;
  IF TG_OP = 'INSERT' AND NEW.role IN ('trader', 'viewer', 'support') THEN
    RETURN NEW;
  END IF;
  RAISE EXCEPTION 'role_change_forbidden' USING ERRCODE = '42501';
END;
$fn$
"""

_ROLE_TRIGGER = """
DROP TRIGGER IF EXISTS users_forbid_self_service_role_change ON public.users;
CREATE TRIGGER users_forbid_self_service_role_change
  BEFORE INSERT OR UPDATE ON public.users
  FOR EACH ROW EXECUTE FUNCTION public.forbid_self_service_role_change()
"""

_POLICY_LOCKDOWN = """
DO $lock$
BEGIN
  EXECUTE 'ALTER TABLE public.trading_runtime_config ENABLE ROW LEVEL SECURITY';
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.trading_runtime_config FROM anon';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    EXECUTE 'REVOKE ALL ON TABLE public.trading_runtime_config FROM authenticated';
  END IF;
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    EXECUTE 'GRANT ALL ON TABLE public.trading_runtime_config TO service_role';
  END IF;
END
$lock$;
"""


@dataclass(frozen=True, slots=True)
class StoredPolicy:
    ok: bool
    version: int
    document: dict[str, Any] | None
    source: str
    error: str = ""
    applied_version: int | None = None
    status: str = ""
    worker_loaded_at: str | None = None


def reset_runtime_policy_store_for_tests() -> None:
    global _MEMORY, _MEMORY_VERSION, _SCHEMA_READY
    with _LOCK:
        _MEMORY = None
        _MEMORY_VERSION = 0
        _SCHEMA_READY = False
        _LAST_APPLIED.clear()
        _LOGGED_VERSION["version"] = None
        _AUDIT.clear()
    use_runtime_policy(None)


def last_applied_version() -> int | None:
    raw = _LAST_APPLIED.get("version")
    return int(raw) if isinstance(raw, int) else None


def last_applied_at() -> str | None:
    raw = _LAST_APPLIED.get("at")
    return str(raw) if raw else None


def _iso(raw: object) -> str | None:
    if raw is None:
        return None
    isoformat = getattr(raw, "isoformat", None)
    if callable(isoformat):
        return str(isoformat())
    text = str(raw).strip()
    return text or None


def memory_audit_events() -> list[dict[str, Any]]:
    return list(_AUDIT)


def _testing() -> bool:
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    try:
        from core.config.settings import get_settings

        return bool(getattr(get_settings(), "is_testing", False))
    except Exception:
        return False


def _postgres() -> tuple[Any, Any, Any]:
    from app.infrastructure.persistence.direct_postgres import (
        direct_postgres_available,
        execute,
        fetch,
    )

    return direct_postgres_available, execute, fetch


def ensure_owner_schema() -> None:
    """Idempotent table and role trigger. Safe to call more than once."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    available, execute, _fetch = _postgres()
    if not available():
        return
    execute(_CREATE_TABLE)
    execute("""
        ALTER TABLE public.trading_runtime_config
            ADD COLUMN IF NOT EXISTS worker_applied_version INTEGER,
            ADD COLUMN IF NOT EXISTS worker_applied_at TIMESTAMPTZ
        """)
    execute(_POLICY_LOCKDOWN)
    execute(_ROLE_FUNCTION)
    execute(_ROLE_TRIGGER)
    try:
        from app.application.services.equity_peak_store import (
            ensure_equity_peak_schema,
        )

        ensure_equity_peak_schema()
    except Exception as exc:
        logger.warning("equity_peak_schema_failed", error_type=type(exc).__name__)
    _SCHEMA_READY = True


def enforce_designated_owner_rows() -> int:
    """Demote every owner/admin row that is not the designated email.

    Direct Postgres has no user JWT, so the self-service trigger allows this.
    Deactivated accounts are left unchanged. Returns the number demoted.
    """
    available, execute, fetch = _postgres()
    if not available():
        return 0
    demoted = fetch(
        """
        UPDATE users
        SET role = 'trader'
        WHERE role IN ('owner', 'admin')
          AND lower(email) <> lower($1)
          AND status IS DISTINCT FROM 'deactivated'
        RETURNING id::text AS id
        """,
        DESIGNATED_OWNER_EMAIL,
    )
    if not demoted:
        return 0
    actor_rows = fetch(
        """
        SELECT id::text AS id
        FROM users
        WHERE lower(email) = lower($1)
        LIMIT 1
        """,
        DESIGNATED_OWNER_EMAIL,
    )
    actor = str(actor_rows[0].get("id") or "") if actor_rows else ""
    for row in demoted:
        target = str(row.get("id") or "")
        if not target:
            continue
        try:
            execute(
                """
                INSERT INTO audit_logs (
                    id, action, outcome, resource_type, resource_id,
                    actor_user_id, occurred_at, ip_address, user_agent,
                    message, metadata, created_at, updated_at
                ) VALUES (
                    $1, 'update', 'success', 'user_role', $2::uuid,
                    $3::uuid, NOW(), '', '',
                    $4, $5::jsonb, NOW(), NOW()
                )
                """,
                uuid4(),
                target,
                actor or target,
                "privileged role demoted_not_designated",
                json.dumps(
                    {
                        "role_action": "demoted_not_designated",
                        "role": "trader",
                    }
                ),
            )
        except Exception:
            logger.warning("owner_role_audit_failed", error_type="insert_failed")
    return len(demoted)


def bootstrap_owner_control_plane() -> dict[str, int | bool]:
    """Create the owner schema and demote non-designated privileged rows.

    Does not enable trading and does not promote anyone. Promotion still
    requires a verified authentication identity.
    """
    schema_ok = True
    try:
        ensure_owner_schema()
    except Exception as exc:
        schema_ok = False
        logger.warning("owner_schema_ensure_failed", error_type=type(exc).__name__)
    demoted = 0
    try:
        demoted = enforce_designated_owner_rows()
    except Exception as exc:
        logger.warning("owner_role_reconcile_failed", error_type=type(exc).__name__)
    if demoted:
        logger.info("owner_privileged_roles_reconciled", demoted=demoted)
    return {"schema_ok": schema_ok, "demoted": demoted}


def _command_count(status: str) -> int:
    parts = str(status or "").split()
    if not parts:
        return 0
    try:
        return int(parts[-1])
    except ValueError:
        return 0


def _status(version: int) -> str:
    applied = last_applied_version()
    if applied is None:
        return "saved"
    if applied == version:
        return "applied"
    if applied < version:
        return "pending_apply"
    return "saved"


def _note_applied(version: int) -> None:
    _LAST_APPLIED["version"] = version
    _LAST_APPLIED["at"] = datetime.now(UTC).isoformat()


def load_runtime_policy() -> StoredPolicy:
    available, _execute, fetch = _postgres()
    if available():
        try:
            ensure_owner_schema()
            rows = fetch("""
                SELECT version, document, worker_applied_version, worker_applied_at
                FROM trading_runtime_config WHERE id = 1
                """)
        except Exception as exc:
            logger.warning("runtime_policy_load_failed", error_type=type(exc).__name__)
            return StoredPolicy(
                False, 0, None, "unavailable", error="config_read_failed"
            )
        if not rows:
            return StoredPolicy(True, 0, approved_baseline(), "approved_baseline")
        document = rows[0].get("document")
        if isinstance(document, str):
            document = json.loads(document)
        if not isinstance(document, dict):
            return StoredPolicy(
                False, 0, None, "unavailable", error="config_document_invalid"
            )
        version = int(rows[0].get("version") or 0)
        acked_raw = rows[0].get("worker_applied_version")
        acked = int(acked_raw) if acked_raw is not None else None
        return StoredPolicy(
            True,
            version,
            document,
            "persisted",
            status=_status(version),
            applied_version=acked,
            worker_loaded_at=_iso(rows[0].get("worker_applied_at")),
        )
    if _testing():
        with _LOCK:
            if _MEMORY is None:
                return StoredPolicy(True, 0, approved_baseline(), "approved_baseline")
            acked = last_applied_version()
            return StoredPolicy(
                True,
                _MEMORY_VERSION,
                dict(_MEMORY),
                "memory",
                status=_status(_MEMORY_VERSION),
                applied_version=acked,
                worker_loaded_at=last_applied_at() if acked is not None else None,
            )
    return StoredPolicy(False, 0, None, "unavailable", error="config_store_unavailable")


def install_cycle_policy() -> StoredPolicy:
    """Install the current policy for this cycle. Failure replaces any prior one."""
    loaded = load_runtime_policy()
    if not loaded.ok or loaded.document is None:
        use_runtime_policy({"unavailable": True})
        return loaded
    use_runtime_policy(dict(loaded.document))
    if loaded.version > 0:
        _note_applied(loaded.version)
        _persist_worker_ack(loaded.version)
    if _LOGGED_VERSION.get("version") != loaded.version:
        from app.domain.institutional_trading.owner_live_limits import (
            commission_audit,
        )

        logger.info(
            "runtime_policy_applied",
            version=loaded.version,
            source=loaded.source,
            status="applied" if loaded.version > 0 else "approved_baseline",
            **commission_audit("XAUUSD", loaded.document),
        )
        _LOGGED_VERSION["version"] = loaded.version
    return StoredPolicy(
        True,
        loaded.version,
        loaded.document,
        loaded.source,
        status="applied" if loaded.version > 0 else "approved_baseline",
        applied_version=last_applied_version(),
        worker_loaded_at=last_applied_at(),
    )


def _persist_worker_ack(version: int) -> None:
    """Record the exact version this worker installed.

    A failed write stays unconfirmed.
    """
    available, execute, _fetch = _postgres()
    if not available():
        return
    try:
        execute(
            """
            UPDATE trading_runtime_config
            SET worker_applied_version = $1, worker_applied_at = NOW()
            WHERE id = 1 AND version = $1
            """,
            version,
        )
    except Exception:
        logger.warning("runtime_policy_worker_ack_failed", error_type="update_failed")


def _audit(
    actor_id: UUID | None,
    outcome: str,
    message: str,
    version: int,
    *,
    persist: bool = True,
) -> None:
    event = {
        "actor_user_id": str(actor_id) if actor_id else None,
        "action": "update",
        "target": "trading_runtime_policy",
        "outcome": outcome,
        "version": version,
        "message": message,
        "at": datetime.now(UTC).isoformat(),
    }
    _AUDIT.append(event)
    available, execute, _fetch = _postgres()
    if not persist or not available() or actor_id is None:
        return
    try:
        execute(
            """
            INSERT INTO audit_logs (
                id, action, outcome, resource_type, resource_id,
                actor_user_id, occurred_at, ip_address, user_agent,
                message, metadata, created_at, updated_at
            ) VALUES (
                $1, 'update', $2, 'trading_policy', $3,
                $4, NOW(), '', '',
                $5, $6::jsonb, NOW(), NOW()
            )
            """,
            uuid4(),
            outcome,
            actor_id,
            actor_id,
            message[:1000],
            json.dumps({"version": version, "target": "trading_runtime_policy"}),
        )
    except Exception:
        logger.warning("runtime_policy_audit_failed", error_type="insert_failed")


def save_runtime_policy(
    *,
    actor_id: UUID,
    expected_version: int,
    changes: dict[str, Any],
) -> StoredPolicy:
    loaded = load_runtime_policy()
    if not loaded.ok or loaded.document is None:
        _audit(actor_id, "failure", "policy read failed before save", 0)
        return StoredPolicy(
            False, loaded.version, None, "rejected", error=loaded.error or "read_failed"
        )
    if loaded.version != expected_version:
        _audit(actor_id, "denied", "stale policy version", loaded.version)
        return StoredPolicy(
            False,
            loaded.version,
            loaded.document,
            "conflict",
            error="stale_version",
            status="rejected",
        )
    decision: PolicyDecision = validate_policy_changes(loaded.document, changes)
    if not decision.ok or decision.document is None:
        _audit(actor_id, "denied", "policy validation rejected", loaded.version)
        return StoredPolicy(
            False,
            loaded.version,
            None,
            "rejected",
            error="; ".join(decision.errors),
            status="rejected",
        )
    new_version = expected_version + 1
    available, _execute, _fetch = _postgres()
    if available():
        payload = json.dumps(decision.document)
        try:
            ensure_owner_schema()
            if expected_version == 0:
                write_sql = """
                    INSERT INTO trading_runtime_config
                        (id, version, document, updated_at, updated_by)
                    VALUES (1, $1, $2::jsonb, NOW(), $3)
                    ON CONFLICT (id) DO NOTHING
                    """
                write_args: tuple[Any, ...] = (new_version, payload, actor_id)
            else:
                write_sql = """
                    UPDATE trading_runtime_config
                    SET version = $1, document = $2::jsonb,
                        updated_at = NOW(), updated_by = $3
                    WHERE id = 1 AND version = $4
                    """
                write_args = (new_version, payload, actor_id, expected_version)
            from app.infrastructure.persistence.direct_postgres import (
                TransactionNoRow,
                execute_transaction,
            )

            audit_sql = """
                INSERT INTO audit_logs (
                    id, action, outcome, resource_type, resource_id,
                    actor_user_id, occurred_at, ip_address, user_agent,
                    message, metadata, created_at, updated_at
                ) VALUES (
                    $1, 'update', 'success', 'trading_policy', $2,
                    $3, NOW(), '', '',
                    $4, $5::jsonb, NOW(), NOW()
                )
                """
            audit_args = (
                uuid4(),
                actor_id,
                actor_id,
                "runtime policy saved",
                json.dumps(
                    {
                        "version": new_version,
                        "target": "trading_runtime_policy",
                    }
                ),
            )
            try:
                statuses = execute_transaction(
                    [
                        (write_sql, write_args),
                        (audit_sql, audit_args),
                    ]
                )
            except TransactionNoRow:
                _audit(actor_id, "denied", "stale policy version", expected_version)
                return StoredPolicy(
                    False,
                    loaded.version,
                    loaded.document,
                    "conflict",
                    error="stale_version",
                    status="rejected",
                )
            status = statuses[0] if statuses else ""
            if _command_count(status) <= 0:
                _audit(actor_id, "denied", "stale policy version", expected_version)
                return StoredPolicy(
                    False,
                    loaded.version,
                    loaded.document,
                    "conflict",
                    error="stale_version",
                    status="rejected",
                )
        except Exception:
            _audit(actor_id, "failure", "policy write failed", expected_version)
            return StoredPolicy(
                False, expected_version, None, "rejected", error="config_write_failed"
            )
    elif _testing():
        global _MEMORY, _MEMORY_VERSION
        with _LOCK:
            if expected_version != _MEMORY_VERSION:
                return StoredPolicy(
                    False,
                    _MEMORY_VERSION,
                    dict(_MEMORY) if _MEMORY else None,
                    "conflict",
                    error="stale_version",
                    status="rejected",
                )
            _MEMORY = dict(decision.document)
            _MEMORY_VERSION = new_version
    else:
        return StoredPolicy(
            False, 0, None, "rejected", error="config_store_unavailable"
        )
    _audit(
        actor_id,
        "success",
        "runtime policy saved",
        new_version,
        persist=not available(),
    )
    use_runtime_policy(None)
    return StoredPolicy(
        True,
        new_version,
        decision.document,
        "persisted" if available() else "memory",
        status="saved",
        applied_version=loaded.applied_version,
        worker_loaded_at=loaded.worker_loaded_at,
    )
