"""Application facade — Institutional Simulation Engine (isolated digital twin)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_simulation_engine import get_ise
from app.domain.institutional_simulation_engine.models import ISOLATION_FLAGS


def build_ise_dashboard() -> dict[str, Any]:
    payload = get_ise().dashboard()
    payload.update(
        {
            "advisory_only": True,
            "mutates_engines": False,
            "influences_trading": False,
            "never_modifies_production": True,
            "never_executes_trades": True,
            "digital_twin": True,
            "isolation": {**ISOLATION_FLAGS, **(payload.get("isolation") or {})},
        }
    )
    return payload


def ise_simulate(
    *,
    mode: str,
    scenario: str | None = None,
    paths: int = 100,
) -> dict[str, Any]:
    return get_ise().simulate(mode=mode, scenario=scenario, paths=paths)


def ise_list_simulations(*, limit: int = 50) -> dict[str, Any]:
    rows = get_ise().store.list_simulations(limit=limit)
    return {
        "simulations": rows,
        "count": len(rows),
        "isolation": ISOLATION_FLAGS,
    }


def ise_list_reports(*, limit: int = 20) -> dict[str, Any]:
    rows = get_ise().store.list_reports(limit=limit)
    return {"reports": rows, "count": len(rows), "isolation": ISOLATION_FLAGS}


def ise_aqs_analysis(simulation_id: str) -> dict[str, Any] | None:
    return get_ise().analyze_for_aqs(simulation_id)


def ise_knowledge_nodes(*, limit: int = 40) -> list[dict[str, Any]]:
    return get_ise().store.knowledge_nodes(limit=limit)
