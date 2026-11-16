"""Phase 12B — multi-account OMS execution authorization + reconciliation.

Separates:
- delivery ACK (queue handoff) from broker fill
- OMS authorization from MT5 order_send
- DEMO order_send (allowed when fully validated) from LIVE order_send
  (path implemented, fail-closed until Owner unlocks live send)

Never treats queue ACK as proof of execution.
Never returns passwords or sealed credentials.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.application.services.multi_account_oms_authorization import (
    preview_oms_authorization,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.worker_runtime import WorkerRuntime


def multi_account_oms_live_order_send_allowed(settings: Any | None = None) -> bool:
    """Explicit LIVE multi-account order_send unlock (default OFF).

    Distinct from MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED, which only arms policy.
    """
    if settings is None:
        try:
            from core.config.settings import get_settings

            settings = get_settings()
        except Exception:
            return False
    raw = getattr(settings, "multi_account_oms_live_order_send_enabled", False)
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True, slots=True)
class ExecutionAuthorization:
    ok: bool
    order_send_allowed: bool
    environment: str
    reasons: tuple[str, ...]
    intent_id: str
    user_id: str
    broker_account_id: str
    worker_id: str
    symbol: str
    side: str
    volume: str
    stop_loss: str | None
    take_profit: str | None
    entry: str | None
    idempotency_key: str
    live_submit_flag: bool
    live_path_authorized: bool
    audit: dict[str, Any] = field(default_factory=dict)

    def to_public_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "order_send_allowed": self.order_send_allowed,
            "environment": self.environment,
            "reasons": list(self.reasons),
            "intent_id": self.intent_id,
            "user_id": self.user_id,
            "broker_account_id": self.broker_account_id,
            "worker_id": self.worker_id,
            "symbol": self.symbol,
            "side": self.side,
            "volume": self.volume,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "entry": self.entry,
            "idempotency_key": self.idempotency_key,
            "live_submit_flag": self.live_submit_flag,
            "live_path_authorized": self.live_path_authorized,
            "order_send": False,  # authorization never submits
            "credentials_exposed": False,
            "audit": self.audit,
        }


@dataclass(frozen=True, slots=True)
class BrokerExecutionReport:
    intent_id: UUID
    worker_id: UUID
    ok: bool
    retcode: int | None
    order_ticket: int | None
    deal_ticket: int | None
    broker_comment: str
    symbol: str
    side: str
    volume: str
    price: str | None
    environment: str
    idempotency_key: str
    raw_safe: dict[str, Any] = field(default_factory=dict)


def authorize_worker_execution(
    *,
    worker: WorkerRuntime,
    intent_id: UUID,
    job_payload: dict[str, Any],
    job_user_id: UUID,
    job_broker_account_id: UUID,
    job_idempotency_key: str,
    revoked: bool = False,
    account_environment: str | None = None,
    customer_trading_enabled: bool = True,
    settings: Any | None = None,
    account_snapshot: dict[str, Any] | None = None,
    now: datetime | None = None,
    user_caps: Any | None = None,
) -> ExecutionAuthorization:
    """Revalidate ownership + risk + OMS gates at execution time.

    The environment comes from MT5 ``trade_mode`` in the worker's account
    snapshot, never from the job payload. Every new entry passes the same
    final owner guard as the Weltrade robot path.
    """
    from app.application.services.multi_account_owner_guard import (
        environment_from_snapshot,
        evaluate_worker_entry,
    )

    reasons: list[str] = []
    status = worker.public_status()
    claimed = (
        str(
            account_environment
            or job_payload.get("account_environment")
            or job_payload.get("environment")
            or ""
        )
        .strip()
        .lower()
        or None
    )
    if claimed is not None and claimed not in {"demo", "live"}:
        reasons.append("account_environment_invalid")
        claimed = None
    verified_env = environment_from_snapshot(account_snapshot)
    # Unknown environment is treated as LIVE for the send lock: never as demo.
    env = verified_env or "live"

    if revoked or status.get("lifecycle") == "revoked":
        reasons.append("account_revoked")
    if worker.user_id != job_user_id:
        reasons.append("user_ownership_mismatch")
    if worker.broker_account_id != job_broker_account_id:
        reasons.append("account_ownership_mismatch")
    if not status.get("dispatch_ready"):
        reasons.append("worker_not_dispatch_ready")
        for r in status.get("not_ready_reasons") or []:
            reasons.append(str(r))
    if not customer_trading_enabled:
        reasons.append("customer_trading_disabled")
    if not multi_account_dispatch_allowed(settings):
        reasons.append("dispatch_disabled")

    symbol = str(job_payload.get("symbol") or job_payload.get("broker_symbol") or "")
    side = str(job_payload.get("side") or job_payload.get("action") or "")
    volume = (
        job_payload.get("volume") or job_payload.get("lot") or job_payload.get("lots")
    )
    stop_loss = job_payload.get("stop_loss") or job_payload.get("sl")
    take_profit = job_payload.get("take_profit") or job_payload.get("tp")
    entry = job_payload.get("entry")

    preview = preview_oms_authorization(
        user_id=worker.user_id,
        broker_account_id=worker.broker_account_id,
        symbol=symbol,
        side=side,
        volume=volume,
        stop_loss=stop_loss,
        worker_dispatch_ready=bool(status.get("dispatch_ready")),
        ownership_verified=worker.user_id == job_user_id
        and worker.broker_account_id == job_broker_account_id,
        account_environment=env,
        settings=settings,
    )
    reasons.extend(list(preview.reasons))

    guard = evaluate_worker_entry(
        snapshot=account_snapshot,
        claimed_environment=claimed,
        user_id=worker.user_id,
        symbol=symbol,
        side=side,
        volume=volume,
        entry=entry,
        stop_loss=stop_loss,
        take_profit=take_profit,
        now=now,
        user_caps=user_caps,
        broker_account_id=worker.broker_account_id,
    )
    reasons.extend(guard.reasons)

    from app.application.services.robot_control_service import (
        entry_block as _robot_entry_block,
    )

    robot_block = _robot_entry_block(
        user_id=worker.user_id, broker_account_id=worker.broker_account_id
    )
    if robot_block:
        reasons.append(robot_block.split(":")[0])

    from app.application.services.entitlements import check_trading_entitlement

    entitlement = check_trading_entitlement(user_id=worker.user_id)
    if not entitlement.allowed:
        reasons.append(entitlement.reason)

    # De-dupe reasons
    seen: set[str] = set()
    ordered: list[str] = []
    for r in reasons:
        if r and r not in seen:
            seen.add(r)
            ordered.append(r)

    live_flag = multi_account_live_submit_allowed(settings)
    live_path_authorized = (
        env == "live" and live_flag and customer_trading_enabled and not ordered
    )
    # DEMO may send when fully validated. LIVE send requires explicit unlock.
    order_send_allowed = False
    if not ordered:
        if env == "demo":
            order_send_allowed = True
        elif env == "live":
            if live_path_authorized and multi_account_oms_live_order_send_allowed(
                settings
            ):
                order_send_allowed = True
            else:
                ordered.append("live_order_send_fail_closed")

    # LIVE fail-closed may leave live_order_send_fail_closed in reasons while
    # auth_ok stays true for path checks excluding the send lock.
    auth_ok = len([r for r in ordered if r not in {"live_order_send_fail_closed"}]) == 0

    vol_s = str(volume) if volume is not None else ""
    return ExecutionAuthorization(
        ok=auth_ok,
        order_send_allowed=order_send_allowed and auth_ok,
        environment=env,
        reasons=tuple(ordered),
        intent_id=str(intent_id),
        user_id=str(worker.user_id),
        broker_account_id=str(worker.broker_account_id),
        worker_id=str(worker.worker_id),
        symbol=str(symbol).upper(),
        side=str(side).upper(),
        volume=vol_s,
        stop_loss=str(stop_loss) if stop_loss is not None else None,
        take_profit=str(take_profit) if take_profit is not None else None,
        entry=str(entry) if entry is not None else None,
        idempotency_key=str(job_idempotency_key or ""),
        live_submit_flag=live_flag,
        live_path_authorized=bool(live_path_authorized),
        audit={
            "authorized_at": datetime.now(UTC).isoformat(),
            "oms_preview_authorized": preview.authorized,
            "environment_source": "mt5_trade_mode" if verified_env else "unverified",
            "owner_guard_inputs": guard.planned_inputs,
            "dispatch_ready": bool(status.get("dispatch_ready")),
        },
    )


def sanitize_broker_result_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip secret-like keys from broker result payloads."""
    banned = {
        "password",
        "token",
        "secret",
        "sealed",
        "credential",
        "api_key",
        "authorization",
    }
    out: dict[str, Any] = {}
    for k, v in payload.items():
        if str(k).lower() in banned:
            continue
        if isinstance(v, dict):
            out[k] = sanitize_broker_result_payload(v)
        else:
            out[k] = v
    return out


def build_position_reconciliation_record(
    *,
    report: BrokerExecutionReport,
    user_id: UUID | str,
    broker_account_id: UUID | str,
) -> dict[str, Any]:
    """Audit-safe position observation for PME handoff (no PME mutate).

    Records the broker tickets so position management can observe the
    correct account-scoped fill. Does not call frozen PME lifecycle APIs.
    """
    return {
        "user_id": str(user_id),
        "broker_account_id": str(broker_account_id),
        "worker_id": str(report.worker_id),
        "intent_id": str(report.intent_id),
        "environment": report.environment,
        "symbol": report.symbol,
        "side": report.side,
        "volume": report.volume,
        "price": report.price,
        "order_ticket": report.order_ticket,
        "deal_ticket": report.deal_ticket,
        "retcode": report.retcode,
        "filled": bool(report.ok and report.order_ticket),
        "pme_mutated": False,
        "credentials_exposed": False,
        "idempotency_key": report.idempotency_key,
        "observed_at": datetime.now(UTC).isoformat(),
    }


# MT5 trade retcodes treated as definitive reject (not uncertain).
_DEFINITE_REJECT_RETCODES = frozenset(
    {
        10004,  # REQUOTE
        10006,  # REJECT
        10007,  # CANCEL
        10013,  # INVALID
        10014,  # INVALID_VOLUME
        10015,  # INVALID_PRICE
        10016,  # INVALID_STOPS
        10017,  # TRADE_DISABLED
        10018,  # MARKET_CLOSED
        10019,  # NO_MONEY
        10030,  # INVALID_FILL
    }
)
_UNCERTAIN_RETCODES = frozenset(
    {
        10012,  # TIMEOUT
        10024,  # PRICE_CHANGED
        10031,  # CONNECTION
    }
)


_PRE_SEND_REJECT_MARKERS = frozenset(
    {
        "symbol_select_failed",
        "symbol_quote_unavailable",
        "invalid_symbol_or_side",
        "mandatory_stop_loss_missing",
        "invalid_numeric_fields",
        "volume_non_positive",
        "mt5_package_unavailable",
        "mt5_attach_failed",
        "dry_run",
    }
)


def classify_broker_execution_outcome(
    *,
    ok: bool,
    retcode: int | None,
    order_ticket: int | None,
    detail: str = "",
    uncertain_flag: bool = False,
    order_send_attempted: bool | None = None,
) -> str:
    """Classify broker outcome for durable state.

    Returns ``filled``, ``rejected``, or ``unknown``.
    Unknown must never trigger a blind order_send retry.
    """
    detail_l = (detail or "").lower()
    if any(m in detail_l for m in _PRE_SEND_REJECT_MARKERS):
        return "rejected"
    if uncertain_flag or "order_send_null" in detail_l or "uncertain" in detail_l:
        return "unknown"
    if retcode == 10009 and order_ticket:
        return "filled"
    if retcode == 10009 and not order_ticket:
        return "unknown"
    if retcode in _UNCERTAIN_RETCODES and not order_ticket:
        return "unknown"
    if retcode is None and not order_ticket and not ok:
        # No retcode: only UNKNOWN if a broker send may have left the process.
        if order_send_attempted is False:
            return "rejected"
        if order_send_attempted is True:
            return "unknown"
        # Ambiguous legacy payloads without order_send flag → fail closed unknown.
        return "unknown"
    if ok and order_ticket:
        return "filled"
    if retcode in _DEFINITE_REJECT_RETCODES:
        return "rejected"
    if not ok:
        return "rejected"
    return "unknown"


def parse_broker_execution_report(
    *,
    intent_id: UUID,
    worker_id: UUID,
    body: dict[str, Any],
) -> BrokerExecutionReport:
    safe = sanitize_broker_result_payload(body)
    retcode = safe.get("retcode")
    try:
        retcode_i = int(retcode) if retcode is not None else None
    except Exception:
        retcode_i = None
    order_ticket = safe.get("order_ticket") or safe.get("order")
    deal_ticket = safe.get("deal_ticket") or safe.get("deal")
    try:
        order_i = int(order_ticket) if order_ticket not in (None, "") else None
    except Exception:
        order_i = None
    try:
        deal_i = int(deal_ticket) if deal_ticket not in (None, "") else None
    except Exception:
        deal_i = None
    ok = bool(safe.get("ok"))
    if retcode_i == 10009:  # TRADE_RETCODE_DONE
        ok = True
    order_send_raw = safe.get("order_send")
    order_send_attempted: bool | None = (
        None if order_send_raw is None else bool(order_send_raw)
    )
    outcome = classify_broker_execution_outcome(
        ok=ok,
        retcode=retcode_i,
        order_ticket=order_i,
        detail=str(safe.get("detail") or safe.get("comment") or ""),
        uncertain_flag=bool(safe.get("uncertain")),
        order_send_attempted=order_send_attempted,
    )
    if outcome == "filled":
        ok = True
    elif outcome == "rejected":
        ok = False
    safe["execution_outcome"] = outcome
    safe["retry_order_send_allowed"] = outcome == "rejected"
    return BrokerExecutionReport(
        intent_id=intent_id,
        worker_id=worker_id,
        ok=ok,
        retcode=retcode_i,
        order_ticket=order_i,
        deal_ticket=deal_i,
        broker_comment=str(safe.get("comment") or safe.get("broker_comment") or "")[
            :200
        ],
        symbol=str(safe.get("symbol") or "").upper(),
        side=str(safe.get("side") or "").upper(),
        volume=str(safe.get("volume") or ""),
        price=str(safe.get("price")) if safe.get("price") is not None else None,
        environment=str(safe.get("environment") or "demo").lower(),
        idempotency_key=str(safe.get("idempotency_key") or ""),
        raw_safe=safe,
    )
