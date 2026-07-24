"""QCDM catalog — build canonical schemas, relationships, governance views."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.domain.quantforg_canonical_data_model.models import (
    CANONICAL_MODELS,
    COMMON_FIELDS,
    COMPATIBILITY_RULES,
    DEPRECATION_RULES,
    MIGRATION_RULES,
    MODEL_FIELDS,
    RELATIONSHIPS,
    SCHEMA_VERSION,
    VALIDATION_RULES,
    VERSION_HISTORY,
)


def _fields_for(model: str) -> list[dict[str, Any]]:
    common = [deepcopy(f) for f in COMMON_FIELDS]
    specific = [deepcopy(f) for f in MODEL_FIELDS.get(model, ())]
    return common + specific


def build_model_schema(model: str) -> dict[str, Any]:
    fields = _fields_for(model)
    rels = [
        deepcopy(r)
        for r in RELATIONSHIPS
        if r.get("from") == model or r.get("to") == model
    ]
    rules = [deepcopy(r) for r in VALIDATION_RULES.get(model, ())]
    return {
        "model": model,
        "schema_version": SCHEMA_VERSION,
        "id": f"qcdm.{model}",
        "version": SCHEMA_VERSION,
        "created_at": VERSION_HISTORY[0]["released_at"],
        "updated_at": VERSION_HISTORY[0]["released_at"],
        "metadata": {
            "namespace": "quantforg.canonical",
            "contract": "enterprise",
            "read_only": True,
        },
        "fields": fields,
        "relationships": rels,
        "validation_rules": rules,
        "field_count": len(fields),
        "required_fields": [f["name"] for f in fields if f.get("required")],
        "immutable_contract": True,
        "read_only": True,
    }


def build_catalog() -> dict[str, Any]:
    models = [build_model_schema(m) for m in CANONICAL_MODELS]
    return {
        "schema_version": SCHEMA_VERSION,
        "model_count": len(models),
        "models": models,
        "model_names": list(CANONICAL_MODELS),
        "read_only": True,
        "never_modifies_production": True,
    }


def build_relationships_graph() -> dict[str, Any]:
    nodes = [{"id": m, "label": m, "type": "canonical_model"} for m in CANONICAL_MODELS]
    edges = [
        {
            "id": f"{r['from']}->{r['to']}:{r['via']}",
            "from": r["from"],
            "to": r["to"],
            "via": r["via"],
            "cardinality": r.get("cardinality"),
        }
        for r in RELATIONSHIPS
    ]
    return {
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
        "read_only": True,
    }


def build_governance() -> dict[str, Any]:
    return {
        "current_version": SCHEMA_VERSION,
        "version_history": [deepcopy(v) for v in VERSION_HISTORY],
        "compatibility_rules": [deepcopy(r) for r in COMPATIBILITY_RULES],
        "deprecation_rules": [deepcopy(r) for r in DEPRECATION_RULES],
        "migration_rules": [deepcopy(r) for r in MIGRATION_RULES],
        "read_only": True,
        "never_auto_migrates_production": True,
    }


def build_version_timeline() -> list[dict[str, Any]]:
    return [
        {
            "version": v["version"],
            "timestamp": v["released_at"],
            "status": v.get("status"),
            "notes": v.get("notes"),
            "breaking": bool(v.get("breaking")),
            "models_added": list(v.get("models_added") or []),
        }
        for v in VERSION_HISTORY
    ]
