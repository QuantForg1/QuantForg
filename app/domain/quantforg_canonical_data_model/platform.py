"""QCDM platform — read-only enterprise data contract surface."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_canonical_data_model.catalog import (
    build_catalog,
    build_governance,
    build_model_schema,
    build_relationships_graph,
    build_version_timeline,
)
from app.domain.quantforg_canonical_data_model.models import (
    CANONICAL_MODELS,
    ISOLATION_FLAGS,
    SCHEMA_VERSION,
)
from app.domain.quantforg_canonical_data_model.store import QcdmStore
from app.domain.quantforg_canonical_data_model.validation import (
    compatibility_validation,
    reference_validation,
    schema_consistency_check,
    validate_instance,
)


class QuantForgCanonicalDataModel:
    def __init__(self, store: QcdmStore | None = None) -> None:
        self.store = store or QcdmStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        catalog = build_catalog()
        relationships = build_relationships_graph()
        governance = build_governance()
        timeline = build_version_timeline()
        schema_consistency = schema_consistency_check()
        compatibility = compatibility_validation()
        references = reference_validation()
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": SCHEMA_VERSION,
            "mode": "quantforg_canonical_data_model",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "model_count": catalog["model_count"],
            "model_names": list(CANONICAL_MODELS),
            "catalog": catalog,
            "relationships": relationships,
            "governance": governance,
            "version_timeline": timeline,
            "schema_consistency": schema_consistency,
            "compatibility": compatibility,
            "reference_validation": references,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategies": True,
            "schema_contract_read_only": True,
        }
        if persist:
            self.store.save_snapshot(pack)
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "schema_explorer": {
                "schema_version": pack["schema_version"],
                "model_names": pack["model_names"],
                "model_count": pack["model_count"],
                "governance_preview": {
                    "compatibility_rules": len(
                        (pack.get("governance") or {}).get("compatibility_rules") or []
                    ),
                    "deprecation_rules": len(
                        (pack.get("governance") or {}).get("deprecation_rules") or []
                    ),
                    "migration_rules": len(
                        (pack.get("governance") or {}).get("migration_rules") or []
                    ),
                },
            },
            "model_browser": pack["catalog"],
            "relationship_explorer": pack["relationships"],
            "version_timeline": pack["version_timeline"],
        }
        return pack

    def list_models(self) -> dict[str, Any]:
        catalog = build_catalog()
        return {
            "models": [
                {
                    "model": m["model"],
                    "field_count": m["field_count"],
                    "required_fields": m["required_fields"],
                    "relationship_count": len(m.get("relationships") or []),
                    "validation_rule_count": len(m.get("validation_rules") or []),
                }
                for m in catalog["models"]
            ],
            "count": catalog["model_count"],
            "schema_version": SCHEMA_VERSION,
            "read_only": True,
        }

    def get_model(self, model: str) -> dict[str, Any]:
        if model not in CANONICAL_MODELS:
            return {"error": "unknown_model", "model": model, "read_only": True}
        return build_model_schema(model)

    def relationships(self) -> dict[str, Any]:
        return build_relationships_graph()

    def governance(self) -> dict[str, Any]:
        return build_governance()

    def timeline(self) -> dict[str, Any]:
        return {
            "timeline": build_version_timeline(),
            "current_version": SCHEMA_VERSION,
            "read_only": True,
        }

    def validate(
        self,
        *,
        model: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema_consistency": schema_consistency_check(),
            "compatibility": compatibility_validation(),
            "reference_validation": reference_validation(),
            "read_only": True,
        }
        if model and payload is not None:
            result["instance"] = validate_instance(model, payload)
        return result
