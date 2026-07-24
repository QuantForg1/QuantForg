"""Application facade — QuantForg Event Mesh (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_event_mesh import get_qem
from app.domain.quantforg_event_mesh.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_modifies_risk": True,
        "never_approves_releases": True,
        "events_immutable": True,
        "event_distribution_read_only": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qem_dashboard() -> dict[str, Any]:
    payload = get_qem().dashboard()
    payload.update(_flags())
    return payload


def qem_events(*, limit: int = 100) -> dict[str, Any]:
    pack = get_qem().dashboard()
    return {
        "events": (pack.get("events") or [])[-limit:],
        "stats": pack.get("stats"),
        **_flags(),
    }


def qem_stream(*, limit: int = 100) -> dict[str, Any]:
    payload = get_qem().stream(limit=limit)
    payload.update(_flags())
    return payload


def qem_timeline(*, limit: int = 100) -> dict[str, Any]:
    payload = get_qem().timeline(limit=limit)
    payload.update(_flags())
    return payload


def qem_search(**kwargs: Any) -> dict[str, Any]:
    payload = get_qem().search(**kwargs)
    payload.update(_flags())
    return payload


def qem_replay(**kwargs: Any) -> dict[str, Any]:
    payload = get_qem().replay(**kwargs)
    payload.update(_flags())
    return payload


def qem_correlation(*, correlation_id: str | None = None) -> dict[str, Any]:
    payload = get_qem().correlation(correlation_id)
    payload.update(_flags())
    return payload


def qem_subscribers() -> dict[str, Any]:
    payload = get_qem().subscribers()
    payload.update(_flags())
    return payload
