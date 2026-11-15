"""Application facade — Phase 7 Autonomous Trading Control."""

from __future__ import annotations

from typing import Any

from app.domain.autonomous_trading_control import MODEL_VERSION, isolation_payload
from app.domain.autonomous_trading_control.engines import (
    authorize_execution,
    evaluate_decision,
    propose_sizing,
    select_strategies,
    validate_signal,
)
from app.domain.autonomous_trading_control.overview import (
    build_feedback_overview,
    build_hub_summary,
    build_ops_overview,
    build_orders_lifecycle,
    build_trade_intelligence,
)
from app.domain.autonomous_trading_control.store import get_autonomy_store


def health() -> dict[str, Any]:
    mode = get_autonomy_store().get_mode()
    return {
        "ok": True,
        "model_version": MODEL_VERSION,
        "mode": mode.get("mode"),
        "order_send": False,
        "phase7_live_dispatch": False,
        **isolation_payload(),
    }


def summary() -> dict[str, Any]:
    return build_hub_summary()


def list_decisions(*, limit: int = 50) -> dict[str, Any]:
    rows = get_autonomy_store().list_decisions(limit=limit)
    return {
        "decisions": rows,
        "count": len(rows),
        **isolation_payload(),
    }


def get_decision(decision_id: str) -> dict[str, Any] | None:
    return get_autonomy_store().get_decision(decision_id)


def create_decision(**kwargs: Any) -> dict[str, Any]:
    return evaluate_decision(**kwargs)


def strategy_selection(**kwargs: Any) -> dict[str, Any]:
    return select_strategies(**kwargs)


def signal_validate(payload: dict[str, Any]) -> dict[str, Any]:
    return validate_signal(payload)


def sizing_propose(payload: dict[str, Any]) -> dict[str, Any]:
    return propose_sizing(payload)


def execution_authorize(payload: dict[str, Any]) -> dict[str, Any]:
    return authorize_execution(payload)


def get_modes() -> dict[str, Any]:
    return get_autonomy_store().get_mode()


def set_mode(*, mode: str, actor: str, note: str = "") -> dict[str, Any]:
    return get_autonomy_store().set_mode(mode, actor=actor, note=note)


def list_approvals(*, limit: int = 50) -> dict[str, Any]:
    rows = get_autonomy_store().list_approvals(limit=limit)
    return {
        "approvals": rows,
        "count": len(rows),
        "approved_is_not_live": True,
        **isolation_payload(),
    }


def create_approval(**kwargs: Any) -> dict[str, Any]:
    return get_autonomy_store().create_approval(**kwargs)


def approval_action(
    approval_id: str,
    *,
    action: str,
    actor: str,
    note: str = "",
    current_params: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return get_autonomy_store().act_on_approval(
        approval_id,
        action=action,
        actor=actor,
        note=note,
        current_params=current_params,
    )


def orders_lifecycle(**kwargs: Any) -> dict[str, Any]:
    return build_orders_lifecycle(**kwargs)


def trade_intelligence(**kwargs: Any) -> dict[str, Any]:
    return build_trade_intelligence(**kwargs)


def feedback_overview(**kwargs: Any) -> dict[str, Any]:
    return build_feedback_overview(**kwargs)


def ops_overview(**kwargs: Any) -> dict[str, Any]:
    return build_ops_overview(**kwargs)


def audit_log(*, limit: int = 100) -> dict[str, Any]:
    rows = get_autonomy_store().list_audit(limit=limit)
    # Redact obvious secrets
    redacted: list[dict[str, Any]] = []
    for row in rows:
        clean = dict(row)
        for k in list(clean.keys()):
            lk = k.lower()
            if any(s in lk for s in ("password", "token", "secret", "api_key")):
                clean[k] = "[redacted]"
        redacted.append(clean)
    return {
        "events": redacted,
        "count": len(redacted),
        **isolation_payload(),
    }
