"""Application facade — QuantForg Canonical Data Model (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_canonical_data_model import get_qcdm
from app.domain.quantforg_canonical_data_model.models import ISOLATION_FLAGS


def _flags() -> dict[str, Any]:
    return {
        "advisory_only": True,
        "mutates_engines": False,
        "influences_trading": False,
        "never_executes_trades": True,
        "never_modifies_production": True,
        "never_modifies_strategies": True,
        "schema_contract_read_only": True,
        "isolation": dict(ISOLATION_FLAGS),
    }


def build_qcdm_dashboard() -> dict[str, Any]:
    payload = get_qcdm().dashboard()
    payload.update(_flags())
    return payload


def qcdm_models() -> dict[str, Any]:
    payload = get_qcdm().list_models()
    payload.update(_flags())
    return payload


def qcdm_model(model: str) -> dict[str, Any]:
    payload = get_qcdm().get_model(model)
    payload.update(_flags())
    return payload


def qcdm_relationships() -> dict[str, Any]:
    payload = get_qcdm().relationships()
    payload.update(_flags())
    return payload


def qcdm_governance() -> dict[str, Any]:
    payload = get_qcdm().governance()
    payload.update(_flags())
    return payload


def qcdm_timeline() -> dict[str, Any]:
    payload = get_qcdm().timeline()
    payload.update(_flags())
    return payload


def qcdm_validate(
    *, model: str | None = None, payload: dict[str, Any] | None = None
) -> dict[str, Any]:
    result = get_qcdm().validate(model=model, payload=payload)
    result.update(_flags())
    return result
