"""Institutional Simulation Engine API — isolated digital twin.

Prefix: /ise
Never executes trades or modifies production, strategies, thresholds,
risk, safety, OMS, gateway, or scheduler.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/ise", tags=["institutional-simulation-engine"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_modifies_production": True,
        "never_executes_trades": True,
        "digital_twin": True,
        "simulation_laboratory_only": True,
    }


@router.get("/dashboard")
def ise_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import (
        build_ise_dashboard,
    )

    payload = build_ise_dashboard()
    payload.update(_flags())
    return payload


@router.get("/catalog")
def ise_catalog(_user: CurrentUser) -> dict[str, Any]:
    from app.domain.institutional_simulation_engine.engine import catalog

    payload = catalog()
    payload.update(_flags())
    return payload


@router.get("/simulate")
def ise_simulate(
    _user: CurrentUser,
    mode: str = Query(default="Historical Scenario Builder"),
    scenario: str | None = None,
    paths: int = Query(default=100, ge=1, le=5000),
) -> dict[str, Any]:
    """Run an isolated simulation (digital twin only)."""
    from app.application.services.institutional_simulation_engine import ise_simulate as _sim

    payload = _sim(mode=mode, scenario=scenario, paths=paths)
    payload.update(_flags())
    return payload


@router.get("/simulations")
def ise_simulations(
    _user: CurrentUser,
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import (
        ise_list_simulations,
    )

    payload = ise_list_simulations(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/simulations/{simulation_id}")
def ise_simulation(simulation_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.domain.institutional_simulation_engine import get_ise

    row = get_ise().store.get_simulation(simulation_id)
    if not row:
        raise HTTPException(status_code=404, detail="simulation_not_found")
    return {"simulation": row, **_flags()}


@router.get("/simulations/{simulation_id}/aqs")
def ise_aqs(simulation_id: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import ise_aqs_analysis

    pack = ise_aqs_analysis(simulation_id)
    if not pack:
        raise HTTPException(status_code=404, detail="simulation_not_found")
    return {"analysis": pack, **_flags()}


@router.get("/monte-carlo")
def ise_monte_carlo(
    _user: CurrentUser,
    paths: int = Query(default=100, ge=1, le=5000),
    scenario: str | None = None,
) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import ise_simulate as _sim

    payload = _sim(mode="Historical Monte Carlo", scenario=scenario, paths=paths)
    payload.update(_flags())
    return payload


@router.get("/walk-forward")
def ise_walk_forward(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import ise_simulate as _sim

    payload = _sim(mode="Historical Walk Forward")
    payload.update(_flags())
    return payload


@router.get("/stress")
def ise_stress(
    _user: CurrentUser,
    stress: str = Query(default="volatility_spike"),
) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import ise_simulate as _sim

    payload = _sim(mode="Historical Stress Test", scenario=stress)
    payload.update(_flags())
    return payload


@router.get("/reports")
def ise_reports(
    _user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import ise_list_reports

    payload = ise_list_reports(limit=limit)
    payload.update(_flags())
    return payload


@router.get("/knowledge-nodes")
def ise_knowledge_nodes(
    _user: CurrentUser,
    limit: int = Query(default=40, ge=1, le=100),
) -> dict[str, Any]:
    from app.application.services.institutional_simulation_engine import (
        ise_knowledge_nodes as _nodes,
    )

    return {"nodes": _nodes(limit=limit), **_flags()}
