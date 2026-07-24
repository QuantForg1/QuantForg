"""Application facade — Institutional Experimentation Platform (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_experimentation_platform import get_iep
from app.domain.institutional_experimentation_platform.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_approves_experiments_automatically": True,
        "never_promotes_experiments_automatically": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_iep_dashboard() -> dict[str, Any]:
    payload = get_iep().dashboard()
    payload.update(_flags())
    return payload


def iep_registry(*, limit: int = 100) -> dict[str, Any]:
    pack = get_iep().dashboard()
    rows = list(pack.get("registry") or [])[:limit]
    return {"registry": rows, "count": len(rows), **_flags()}


def iep_experiment(experiment_id: str) -> dict[str, Any]:
    row = get_iep().get_experiment(experiment_id)
    if not row:
        return {"experiment": None, "found": False, **_flags()}
    return {"experiment": row, "found": True, **_flags()}


def iep_hypothesis() -> dict[str, Any]:
    pack = get_iep().dashboard()
    return {
        "hypothesis_builder": (pack.get("sections") or {}).get("hypothesis_builder"),
        **_flags(),
    }


def iep_comparison() -> dict[str, Any]:
    pack = get_iep().dashboard()
    return {
        "comparison_workspace": (pack.get("sections") or {}).get(
            "comparison_workspace"
        ),
        **_flags(),
    }


def iep_evidence(experiment_id: str | None = None) -> dict[str, Any]:
    iep = get_iep()
    if experiment_id:
        row = iep.get_experiment(experiment_id)
        return {
            "experiment_id": experiment_id,
            "evidence": (row or {}).get("evidence"),
            "found": row is not None,
            **_flags(),
        }
    pack = iep.dashboard()
    return {
        "evidence_explorer": (pack.get("sections") or {}).get("evidence_explorer"),
        **_flags(),
    }


def iep_decisions() -> dict[str, Any]:
    pack = get_iep().dashboard()
    return {
        "decision_dashboard": (pack.get("sections") or {}).get("decision_dashboard"),
        **_flags(),
    }


def iep_statistics(experiment_id: str | None = None) -> dict[str, Any]:
    iep = get_iep()
    if experiment_id:
        row = iep.get_experiment(experiment_id)
        return {
            "experiment_id": experiment_id,
            "statistics": (row or {}).get("statistics"),
            "found": row is not None,
            **_flags(),
        }
    pack = iep.dashboard()
    return {
        "registry_statistics": [
            {
                "experiment_id": e.get("experiment_id"),
                "statistics": e.get("statistics"),
            }
            for e in pack.get("registry") or []
        ],
        "statistical_consistency": pack.get("statistical_consistency"),
        **_flags(),
    }


def iep_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_iep().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}
