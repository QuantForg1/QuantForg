"""Application facade — QuantForg Certification Suite (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_certification_suite import get_qcs
from app.domain.quantforg_certification_suite.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "never_modifies_risk": True,
        "never_modifies_safety": True,
        "never_approves_releases_automatically": True,
        "human_approval_required_for_certification": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qcs_dashboard() -> dict[str, Any]:
    payload = get_qcs().dashboard()
    payload.update(_flags())
    return payload


def qcs_readiness() -> dict[str, Any]:
    pack = get_qcs().dashboard()
    return {
        "readiness_center": (pack.get("sections") or {}).get("readiness_center"),
        **_flags(),
    }


def qcs_checks() -> dict[str, Any]:
    pack = get_qcs().dashboard()
    return {"checks": pack.get("checks") or [], **_flags()}


def qcs_blockers() -> dict[str, Any]:
    pack = get_qcs().dashboard()
    return {"blockers": pack.get("blockers") or [], **_flags()}


def qcs_evidence() -> dict[str, Any]:
    pack = get_qcs().dashboard()
    return {"evidence": pack.get("evidence"), **_flags()}


def qcs_timeline() -> dict[str, Any]:
    pack = get_qcs().dashboard()
    return {
        "certification_timeline": (pack.get("sections") or {}).get(
            "certification_timeline"
        ),
        **_flags(),
    }


def qcs_scores() -> dict[str, Any]:
    pack = get_qcs().dashboard()
    return {
        "scores": pack.get("scores"),
        "level": pack.get("level"),
        **_flags(),
    }


def qcs_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_qcs().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), **_flags()}
