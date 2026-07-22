"""Application service — Institutional Observability Platform."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_observability.reports import build_observability_pack


def _try_ops_facts() -> dict[str, Any]:
    """Best-effort read-only ops facts — never mutates control plane."""
    try:
        from app.application.services.auto_trading_status import (
            build_auto_trading_status,
        )
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from core.config.settings import get_settings

        plane = get_control_plane()
        snap = build_auto_trading_status(plane, settings=get_settings())
        facts = snap.facts
        live = snap.live or {}
        return {
            "gateway_connected": bool(facts.gateway_connected),
            "broker_connected": bool(facts.broker_connected),
            "mt5_logged_in": bool(
                facts.broker_connected or live.get("broker_connected")
            ),
            "execution_enabled": bool(facts.execution_enabled),
            "ops_mode": str(facts.ops_mode or plane.mode.value),
        }
    except Exception:
        return {}


def _try_governance_events(limit: int = 200) -> list[dict[str, Any]]:
    try:
        from app.domain.audit_governance.store import get_audit_store

        return get_audit_store().list(limit=limit)
    except Exception:
        return []


def _try_journal_ok(journal: Any | None, user_id: str | None) -> dict[str, Any]:
    if journal is None or not user_id:
        return {}
    try:
        rows = journal.list_for_user(str(user_id), limit=1)
        return {
            "journal_ok": True,
            "journal_detail": f"list_ok n={len(rows) if isinstance(rows, list) else 0}",
        }
    except Exception as exc:
        return {"journal_ok": False, "journal_detail": str(exc)[:120]}


def run_observability(
    *,
    ops_facts: dict[str, Any] | None = None,
    latency_samples: dict[str, float | None] | None = None,
    error_events: list[dict[str, Any]] | None = None,
    journal: Any | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    facts = dict(ops_facts or _try_ops_facts())
    facts.update(_try_journal_ok(journal, user_id))
    events = error_events if error_events is not None else _try_governance_events()
    return build_observability_pack(
        ops_facts=facts,
        latency_samples=latency_samples,
        error_events=events,
    )


def seed_demo_observability() -> dict[str, Any]:
    """Demo pack for local reports — labeled synthetic latency/error samples."""
    return build_observability_pack(
        ops_facts={
            "gateway_connected": True,
            "broker_connected": True,
            "mt5_logged_in": True,
            "execution_enabled": False,
            "journal_ok": True,
            "journal_detail": "demo journal ok",
            "queue_depth": 3,
        },
        latency_samples={
            "api": 12.5,
            "gateway": 40.0,
            "broker": 55.0,
            "decision": 8.0,
            "risk": 6.0,
            "safety": 5.0,
            "execution": 70.0,
            "journal": 9.0,
            "dashboard": 18.0,
        },
        error_events=[
            {
                "timestamp": "2026-07-22T09:00:00Z",
                "severity": "warning",
                "action": "reconnect",
                "component": "gateway",
                "result": "success",
                "reason": "transient disconnect recovery",
            },
            {
                "timestamp": "2026-07-22T09:12:00Z",
                "severity": "critical",
                "action": "kill_switch_armed",
                "component": "safety",
                "result": "success",
            },
            {
                "timestamp": "2026-07-22T10:00:00Z",
                "severity": "error",
                "action": "timeout",
                "component": "broker",
                "result": "failure",
            },
        ],
    )
