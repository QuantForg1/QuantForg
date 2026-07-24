"""IRDP gather — READ-ONLY snapshots for release checklist evidence."""

from __future__ import annotations

from typing import Any


def _safe(fn, default: Any = None) -> Any:
    try:
        return fn()
    except Exception:  # noqa: BLE001
        return default


def gather_release_evidence() -> dict[str, Any]:
    sources: dict[str, Any] = {}
    availability: dict[str, bool] = {}

    # Cached snapshots only — never force heavy rebuilds that mutate production
    sources["cvf"] = _safe(
        lambda: __import__(
            "app.domain.continuous_validation_framework", fromlist=["get_cvf"]
        ).get_cvf().store.__dict__.get("_snapshot")
        or {},
        {},
    )
    availability["cvf"] = bool(sources["cvf"])

    sources["eqs"] = _safe(
        lambda: __import__(
            "app.domain.execution_quality_suite", fromlist=["get_eqs"]
        ).get_eqs().store.__dict__.get("_snapshot")
        or {},
        {},
    )
    availability["eqs"] = bool(sources["eqs"])

    sources["res"] = _safe(
        lambda: __import__(
            "app.domain.reliability_engineering_suite", fromlist=["get_res"]
        ).get_res().store.__dict__.get("_snapshot")
        or {},
        {},
    )
    availability["res"] = bool(sources["res"])

    sources["ise"] = _safe(
        lambda: {
            "simulations": __import__(
                "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
            )
            .get_ise()
            .store.list_simulations(limit=10),
            "reports": __import__(
                "app.domain.institutional_simulation_engine", fromlist=["get_ise"]
            )
            .get_ise()
            .store.list_reports(limit=5),
        },
        {"simulations": [], "reports": []},
    )
    availability["ise"] = isinstance(sources["ise"], dict)

    sources["qkg"] = _safe(
        lambda: __import__(
            "app.domain.quant_knowledge_graph", fromlist=["get_qkg"]
        )
        .get_qkg()
        .store.get_snapshot(),
        {},
    )
    availability["qkg"] = bool(sources["qkg"])

    sources["audit"] = _safe(
        lambda: __import__(
            "app.domain.audit_governance.store",
            fromlist=["get_audit_store"],
        ).get_audit_store().list(limit=40),
        [],
    )
    availability["audit"] = isinstance(sources["audit"], list)

    sources["icc"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_control_center",
            fromlist=["build_institutional_control_center"],
        ).build_institutional_control_center(),
        {},
    )
    availability["icc"] = bool(sources["icc"])

    sources["prr"] = _safe(
        lambda: __import__(
            "app.application.services.institutional_production_readiness_review",
            fromlist=["build_institutional_production_readiness_review"],
        ).build_institutional_production_readiness_review(write_report=False),
        {},
    )
    availability["prr"] = bool(sources["prr"])

    return {
        "sources": sources,
        "availability": availability,
        "source_count": sum(1 for v in availability.values() if v),
        "read_only": True,
        "never_mutates_sources": True,
    }
