"""Phase 9 — ITE → multi-account dry-run adapter (non-executing).

Product-owner Phase 9 explicitly authorizes a thin hook from
``institutional_ite_runtime`` into this module for **planning only**.

Hard rules:
- Never imports OMS / gateway_client / order_send.
- Never enables MULTI_ACCOUNT_LIVE_SUBMIT.
- When LIVE submit is armed, refuse the multi-account path fail-closed.
- With MULTI_ACCOUNT_DISPATCH_ENABLED=false, jobs (if persisted) are not claimable.
- No credentials in signal or job payloads.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.application.services.multi_account_dispatch_dry_run import (
    DispatchPlan,
    DispatchTarget,
    InMemoryDispatchLedger,
    plan_signal_dispatch,
)
from app.application.services.multi_account_dispatch_queue import (
    DurableDispatchQueue,
    get_durable_dispatch_queue,
)
from app.domain.multi_account.feature_gates import (
    multi_account_dispatch_allowed,
    multi_account_live_submit_allowed,
)
from app.domain.multi_account.signal_dispatch import (
    AccountExecutionState,
    CentralSignalIntent,
)

logger = logging.getLogger(__name__)

TargetProvider = Callable[[], Sequence[DispatchTarget]]

_ledger = InMemoryDispatchLedger()
_target_provider: TargetProvider | None = None


def set_ite_dry_run_target_provider(provider: TargetProvider | None) -> None:
    """Test/ops hook — production may leave unset (no invented targets)."""
    global _target_provider
    _target_provider = provider


def reset_ite_dry_run_state_for_tests() -> None:
    """Reset process-local ledger + provider (unit tests only)."""
    global _ledger, _target_provider
    _ledger = InMemoryDispatchLedger()
    _target_provider = None


def _dec(value: object) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _decision_side(decision: Any) -> str:
    raw = getattr(decision, "action", None)
    side = str(getattr(raw, "value", raw) or "").strip().upper()
    return side if side in {"BUY", "SELL"} else ""


def _decision_quality(decision: Any) -> int:
    for attr in ("quality", "confidence", "score"):
        val = getattr(decision, attr, None)
        if val is None and isinstance(decision, dict):
            val = decision.get(attr)
        try:
            if val is not None:
                return max(1, min(100, int(val)))
        except (TypeError, ValueError):
            continue
    ai = getattr(decision, "ai_score", None)
    if isinstance(ai, dict):
        try:
            return max(1, min(100, int(ai.get("score") or 50)))
        except (TypeError, ValueError):
            pass
    return 50


def build_central_signal_from_ite_decision(
    *,
    decision: Any,
    trace_id: str,
) -> CentralSignalIntent | None:
    """Map a qualified ITE decision into CentralSignalIntent or None if invalid."""
    side = _decision_side(decision)
    if side not in {"BUY", "SELL"}:
        return None
    symbol = str(getattr(decision, "symbol", "") or "").strip().upper()
    if not symbol:
        return None
    decision_id = str(getattr(decision, "id", "") or "").strip()
    key = f"ite:{decision_id or trace_id}:{symbol}:{side}"
    entry = _dec(getattr(decision, "entry", None) or getattr(decision, "price", None))
    stop = _dec(getattr(decision, "stop_loss", None) or getattr(decision, "sl", None))
    take = _dec(getattr(decision, "take_profit", None) or getattr(decision, "tp", None))
    return CentralSignalIntent.create(
        symbol=symbol,
        side=side,
        quality=_decision_quality(decision),
        entry=entry,
        stop_loss=stop,
        take_profit=take,
        strategy_id="institutional_ite",
        trace_id=str(trace_id or ""),
        idempotency_key=key,
        metadata={
            "source": "institutional_ite_runtime",
            "phase": "phase9_dry_run",
            "decision_id": decision_id,
            "live_submit_allowed": False,
            "credentials_exposed": False,
        },
    )


def resolve_dry_run_targets(
    *,
    explicit: Sequence[DispatchTarget] | None = None,
    diagnostics: dict[str, Any] | None = None,
) -> list[DispatchTarget]:
    """Resolve targets without inventing SaaS accounts.

    Order: explicit arg → diagnostics['multi_account_targets'] → provider → [].
    """
    if explicit is not None:
        return list(explicit)
    if diagnostics and isinstance(diagnostics.get("multi_account_targets"), list):
        out: list[DispatchTarget] = []
        for raw in diagnostics["multi_account_targets"]:
            if isinstance(raw, DispatchTarget):
                out.append(raw)
        if out:
            return out
    if _target_provider is not None:
        try:
            return list(_target_provider() or [])
        except Exception:
            logger.exception("ite_dry_run_target_provider_failed")
            return []
    return []


def run_ite_multi_account_dry_run(
    *,
    decision: Any,
    trace_id: str,
    targets: Sequence[DispatchTarget] | None = None,
    settings: Any | None = None,
    diagnostics: dict[str, Any] | None = None,
    persist_jobs: bool = True,
    queue: DurableDispatchQueue | None = None,
) -> dict[str, Any]:
    """Plan per-account eligibility + optional durable audit jobs.

    Never submits orders. Never claims worker delivery when dispatch flag is off.
    """
    audit: dict[str, Any] = {
        "ok": False,
        "phase": "phase9_ite_dry_run",
        "generated_at": datetime.now(UTC).isoformat(),
        "trace_id": str(trace_id or ""),
        "live_submit_allowed": False,
        "credentials_exposed": False,
        "oms_touched": False,
        "order_send": False,
        "dry_run": True,
    }

    if multi_account_live_submit_allowed(settings):
        audit.update(
            {
                "error": "live_submit_armed_refused",
                "detail": (
                    "Multi-account LIVE submit is armed — Phase 9 refuses "
                    "fan-out planning fail-closed."
                ),
            }
        )
        return audit

    signal = build_central_signal_from_ite_decision(
        decision=decision, trace_id=trace_id
    )
    if signal is None:
        audit.update(
            {
                "error": "invalid_ite_signal",
                "detail": "Decision missing BUY/SELL side or symbol",
            }
        )
        return audit

    audit["signal_idempotency_key"] = signal.idempotency_key
    audit["signal_id"] = str(signal.signal_id)
    audit["symbol"] = signal.symbol
    audit["side"] = signal.side

    resolved = resolve_dry_run_targets(explicit=targets, diagnostics=diagnostics)
    audit["target_count"] = len(resolved)
    if not resolved:
        audit.update(
            {
                "ok": True,
                "error": None,
                "eligible": 0,
                "blocked": 0,
                "job_count": 0,
                "detail": "no_eligible_targets",
                "note": (
                    "No multi-account targets registered for this cycle. "
                    "Singleton Weltrade LIVE path is unchanged."
                ),
            }
        )
        return audit

    dispatch_on = multi_account_dispatch_allowed(settings)
    audit["dispatch_allowed"] = bool(dispatch_on)

    plan: DispatchPlan
    jobs: list[Any] = []
    if persist_jobs:
        q = queue or get_durable_dispatch_queue()
        try:
            plan, jobs = q.plan_and_enqueue(
                signal=signal,
                targets=list(resolved),
                settings=settings,
                require_readiness=True,
            )
        except RuntimeError as exc:
            msg = str(exc) or "plan_and_enqueue_refused"
            if "live_submit_armed_refused" in msg:
                audit.update(
                    {
                        "ok": False,
                        "error": "live_submit_armed_refused",
                        "detail": "durable_queue_refused",
                    }
                )
                return audit
            logger.exception("ite_dry_run_enqueue_failed")
            audit.update(
                {
                    "ok": False,
                    "error": f"queue_outage:{type(exc).__name__}",
                    "detail": "durable_queue_unavailable",
                }
            )
            return audit
        except Exception as exc:
            logger.exception("ite_dry_run_enqueue_failed")
            audit.update(
                {
                    "ok": False,
                    "error": f"queue_outage:{type(exc).__name__}",
                    "detail": "durable_queue_unavailable",
                }
            )
            return audit
    else:
        plan = plan_signal_dispatch(
            signal=signal,
            targets=list(resolved),
            settings=settings,
            require_readiness=True,
            ledger=_ledger,
        )

    # Idempotent ledger remember for in-process audits even when queue used.
    _ledger.remember(plan)

    eligible = sum(
        1
        for i in plan.items
        if i.evaluation.state is AccountExecutionState.ELIGIBLE
        or i.intent.state is AccountExecutionState.QUEUED
    )
    blocked = sum(
        1 for i in plan.items if i.evaluation.state is AccountExecutionState.BLOCKED
    )
    items_public = []
    for item in plan.items:
        items_public.append(
            {
                "user_id": str(item.intent.user_id),
                "broker_account_id": str(item.intent.broker_account_id),
                "state": item.intent.state.value,
                "block_reason": item.evaluation.block_reason,
                "idempotency_key": item.idempotency_key,
                "delivery_suppressed": item.delivery_suppressed,
                "dry_run": item.evaluation.dry_run,
                "dispatch_allowed": item.evaluation.dispatch_allowed,
                "live_submit_allowed": False,
            }
        )

    audit.update(
        {
            "ok": True,
            "error": None,
            "eligible": eligible,
            "blocked": blocked,
            "job_count": len(jobs),
            "delivery_suppressed_all": all(i.delivery_suppressed for i in plan.items),
            "plan": plan.to_dict(),
            "items": items_public,
            "detail": "dry_run_plan_complete",
        }
    )
    logger.info(
        "ite_multi_account_dry_run signal=%s eligible=%s blocked=%s jobs=%s "
        "dispatch=%s live=false",
        signal.idempotency_key,
        eligible,
        blocked,
        len(jobs),
        dispatch_on,
    )
    return audit


def attach_ite_multi_account_dry_run(
    *,
    decision: Any,
    trace_id: str,
    diagnostics: dict[str, Any] | None,
    targets: Sequence[DispatchTarget] | None = None,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Merge dry-run audit into cycle diagnostics. Never raises to ITE."""
    diag = dict(diagnostics or {})
    try:
        result = run_ite_multi_account_dry_run(
            decision=decision,
            trace_id=trace_id,
            targets=targets,
            settings=settings,
            diagnostics=diag,
            persist_jobs=True,
        )
    except Exception as exc:
        logger.exception("ite_multi_account_dry_run_attach_failed")
        result = {
            "ok": False,
            "error": f"adapter_exception:{type(exc).__name__}",
            "live_submit_allowed": False,
            "credentials_exposed": False,
            "oms_touched": False,
            "order_send": False,
        }
    diag["multi_account_dry_run"] = result
    return diag
