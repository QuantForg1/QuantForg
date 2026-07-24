"""Unit tests — QuantForg Canonical Data Model."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.domain.quantforg_canonical_data_model.catalog import (
    build_catalog,
    build_governance,
    build_relationships_graph,
)
from app.domain.quantforg_canonical_data_model.models import (
    CANONICAL_MODELS,
    ISOLATION_FLAGS,
    SCHEMA_VERSION,
)
from app.domain.quantforg_canonical_data_model.platform import (
    QuantForgCanonicalDataModel,
)
from app.domain.quantforg_canonical_data_model.store import QcdmStore
from app.domain.quantforg_canonical_data_model.validation import (
    compatibility_validation,
    reference_validation,
    schema_consistency_check,
    validate_instance,
)

pytestmark = pytest.mark.unit


class TestIsolation:
    def test_flags(self) -> None:
        assert ISOLATION_FLAGS["executes_trades"] is False
        assert ISOLATION_FLAGS["modifies_production"] is False
        assert ISOLATION_FLAGS["modifies_strategies"] is False
        assert ISOLATION_FLAGS["schema_contract_read_only"] is True


class TestSchemaConsistency:
    def test_all_models_defined(self) -> None:
        assert len(CANONICAL_MODELS) == 17
        catalog = build_catalog()
        assert catalog["model_count"] == 17
        assert catalog["schema_version"] == SCHEMA_VERSION
        for name in CANONICAL_MODELS:
            assert name in catalog["model_names"]
        assert schema_consistency_check()["ok"] is True
        assert reference_validation()["ok"] is True
        assert compatibility_validation()["ok"] is True


class TestCompatibility:
    def test_breaking_change_detected(self) -> None:
        from app.domain.quantforg_canonical_data_model.catalog import (
            build_model_schema,
        )

        prev = {
            "schema_version": "1.0.0",
            "models": {m: build_model_schema(m) for m in CANONICAL_MODELS},
        }
        curr_models = {m: build_model_schema(m) for m in CANONICAL_MODELS}
        # Simulate removing a field
        trade = dict(curr_models["Trade"])
        trade["fields"] = [f for f in trade["fields"] if f["name"] != "symbol"]
        curr_models["Trade"] = trade
        result = compatibility_validation(
            previous=prev, current={"schema_version": "1.1.0", "models": curr_models}
        )
        assert result["ok"] is False
        assert any("field_removed" in i for i in result["issues"])


class TestInstanceValidation:
    def test_valid_and_invalid_trade(self) -> None:
        good = {
            "id": "t1",
            "version": "1",
            "created_at": "2026-01-01T00:00:00+00:00",
            "updated_at": "2026-01-01T00:00:00+00:00",
            "metadata": {},
            "symbol": "EURUSD",
            "side": "buy",
            "quantity": 1.0,
            "price": 1.1,
        }
        assert validate_instance("Trade", good)["ok"] is True
        bad = {**good, "quantity": -1, "side": "hold"}
        assert validate_instance("Trade", bad)["ok"] is False


class TestGovernanceAndGraph:
    def test_governance_and_relationships(self) -> None:
        gov = build_governance()
        assert gov["current_version"] == SCHEMA_VERSION
        assert gov["compatibility_rules"]
        assert gov["deprecation_rules"]
        assert gov["migration_rules"]
        assert gov["never_auto_migrates_production"] is True
        graph = build_relationships_graph()
        assert graph["node_count"] == 17
        assert graph["edge_count"] > 0


class TestPlatform:
    def test_dashboard(self, tmp_path: Path) -> None:
        qcdm = QuantForgCanonicalDataModel(
            store=QcdmStore(path=tmp_path / "qcdm.json")
        )
        t0 = time.perf_counter()
        pack = qcdm.dashboard()
        elapsed = (time.perf_counter() - t0) * 1000.0
        assert pack["never_executes_trades"] is True
        assert pack["never_modifies_production"] is True
        assert pack["never_modifies_strategies"] is True
        assert pack["schema_consistency"]["ok"] is True
        assert pack["compatibility"]["ok"] is True
        assert pack["reference_validation"]["ok"] is True
        assert pack["sections"]["schema_explorer"]
        assert pack["sections"]["model_browser"]
        assert pack["sections"]["relationship_explorer"]
        assert pack["sections"]["version_timeline"]
        assert pack["elapsed_ms"] < 500
        assert elapsed < 2000
