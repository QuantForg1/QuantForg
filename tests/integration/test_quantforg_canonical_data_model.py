"""Integration — QCDM is read-only enterprise schema contract."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.application.services import quantforg_canonical_data_model as svc
from app.domain.quantforg_canonical_data_model.models import (
    CANONICAL_MODELS,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_canonical_data_model.platform import (
    QuantForgCanonicalDataModel,
)
from app.domain.quantforg_canonical_data_model.store import QcdmStore
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "quantforg_canonical_data_model" in {n for n, _ in _ROUTER_SPECS}


def test_isolation_flags() -> None:
    assert ISOLATION_FLAGS["executes_trades"] is False
    assert ISOLATION_FLAGS["modifies_production"] is False
    assert ISOLATION_FLAGS["modifies_strategies"] is False
    assert ISOLATION_FLAGS["schema_contract_read_only"] is True


def test_service_dashboard_flags(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    qcdm = QuantForgCanonicalDataModel(store=QcdmStore(path=tmp_path / "qcdm.json"))
    monkeypatch.setattr("app.domain.quantforg_canonical_data_model._QCDM", qcdm)
    monkeypatch.setattr(svc, "get_qcdm", lambda: qcdm)
    payload = svc.build_qcdm_dashboard()
    assert payload["never_executes_trades"] is True
    assert payload["never_modifies_production"] is True
    assert payload["never_modifies_strategies"] is True
    assert payload["schema_contract_read_only"] is True
    assert payload["mutates_engines"] is False
    assert payload["schema_consistency"]["ok"] is True
    assert payload["compatibility"]["ok"] is True
    assert payload["reference_validation"]["ok"] is True
    assert payload["model_count"] == len(CANONICAL_MODELS)

    models = svc.qcdm_models()
    assert models["count"] == 17
    strategy = svc.qcdm_model("Strategy")
    assert strategy["model"] == "Strategy"
    assert "id" in strategy["required_fields"]
    assert svc.qcdm_relationships()["edge_count"] > 0
    assert svc.qcdm_governance()["never_auto_migrates_production"] is True
    assert svc.qcdm_validate()["schema_consistency"]["ok"] is True
