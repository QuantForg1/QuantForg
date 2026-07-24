"""QuantForg Canonical Data Model API — read-only schema metadata.

Prefix: /qcdm
Never executes trades or modifies production/strategies.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query

from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(prefix="/qcdm", tags=["quantforg-canonical-data-model"])


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "schema_contract_read_only": True,
        "read_only_endpoints": True,
    }


@router.get("/dashboard")
def qcdm_dashboard(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import (
        build_qcdm_dashboard,
    )

    payload = build_qcdm_dashboard()
    payload.update(_flags())
    return payload


@router.get("/models")
def qcdm_models(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import qcdm_models as svc

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/models/{model}")
def qcdm_model(model: str, _user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import qcdm_model as svc

    payload = svc(model)
    payload.update(_flags())
    return payload


@router.get("/relationships")
def qcdm_relationships(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import (
        qcdm_relationships as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/governance")
def qcdm_governance(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import (
        qcdm_governance as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/timeline")
def qcdm_timeline(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import (
        qcdm_timeline as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/validate")
def qcdm_validate(_user: CurrentUser) -> dict[str, Any]:
    from app.application.services.quantforg_canonical_data_model import (
        qcdm_validate as svc,
    )

    payload = svc()
    payload.update(_flags())
    return payload


@router.get("/schema")
def qcdm_schema_metadata(
    _user: CurrentUser,
    model: str | None = Query(default=None),
) -> dict[str, Any]:
    """Expose schema metadata for the contract or a single model."""
    from app.application.services.quantforg_canonical_data_model import (
        qcdm_governance,
        qcdm_model,
        qcdm_models,
    )

    if model:
        payload = qcdm_model(model)
    else:
        payload = {
            "models": qcdm_models(),
            "governance": qcdm_governance(),
        }
    payload.update(_flags())
    return payload
