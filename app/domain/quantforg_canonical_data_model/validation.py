"""QCDM validation — schema, compatibility, and reference checks (read-only)."""

from __future__ import annotations

from typing import Any

from app.domain.quantforg_canonical_data_model.catalog import build_catalog, build_model_schema
from app.domain.quantforg_canonical_data_model.models import (
    CANONICAL_MODELS,
    COMMON_FIELDS,
    COMPATIBILITY_RULES,
    MODEL_FIELDS,
    RELATIONSHIPS,
    SCHEMA_VERSION,
    VALIDATION_RULES,
)


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def schema_consistency_check() -> dict[str, Any]:
    issues: list[str] = []
    common_names = {f["name"] for f in COMMON_FIELDS}
    required_common = {"id", "version", "created_at", "updated_at", "metadata"}
    if not required_common.issubset(common_names):
        issues.append("common_fields_missing_required")

    for model in CANONICAL_MODELS:
        if model not in MODEL_FIELDS:
            issues.append(f"missing_fields:{model}")
            continue
        schema = build_model_schema(model)
        names = [f["name"] for f in schema["fields"]]
        if len(names) != len(set(names)):
            issues.append(f"duplicate_fields:{model}")
        for req in required_common:
            if req not in names:
                issues.append(f"missing_common:{model}.{req}")
        if model not in VALIDATION_RULES:
            issues.append(f"missing_validation_rules:{model}")
        if not schema.get("relationships") and model not in {
            "Portfolio",
            "Alert",
            "Incident",
            "Evidence",
            "Recommendation",
            "Certification",
            "Release",
            "ValidationEvent",
            "RiskEvent",
            "Replay",
            "Simulation",
            "Experiment",
            "Strategy",
            "Signal",
            "Execution",
            "Order",
            "Trade",
        }:
            pass  # all models may have zero or more relationships

    # Every relationship endpoint must reference a known model
    for rel in RELATIONSHIPS:
        if rel.get("from") not in CANONICAL_MODELS:
            issues.append(f"unknown_from:{rel.get('from')}")
        if rel.get("to") not in CANONICAL_MODELS:
            issues.append(f"unknown_to:{rel.get('to')}")

    catalog = build_catalog()
    if catalog["model_count"] != len(CANONICAL_MODELS):
        issues.append("catalog_count_mismatch")
    if catalog.get("schema_version") != SCHEMA_VERSION:
        issues.append("schema_version_mismatch")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "checked_models": list(CANONICAL_MODELS),
        "read_only": True,
    }


def validate_instance(model: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Validate a payload against the canonical schema (advisory)."""
    issues: list[str] = []
    if model not in CANONICAL_MODELS:
        return {"ok": False, "issues": [f"unknown_model:{model}"], "read_only": True}
    schema = build_model_schema(model)
    data = _as_dict(payload)
    for field in schema["fields"]:
        name = field["name"]
        if field.get("required") and name not in data:
            issues.append(f"missing_required:{name}")
            continue
        if name not in data:
            continue
        value = data[name]
        ftype = str(field.get("type") or "")
        if ftype == "string" and not isinstance(value, str):
            issues.append(f"type:{name}:expected_string")
        elif ftype == "number" and not isinstance(value, (int, float)):
            issues.append(f"type:{name}:expected_number")
        elif ftype == "boolean" and not isinstance(value, bool):
            issues.append(f"type:{name}:expected_boolean")
        elif ftype == "object" and not isinstance(value, dict):
            issues.append(f"type:{name}:expected_object")
        elif ftype == "array" and not isinstance(value, list):
            issues.append(f"type:{name}:expected_array")
        elif ftype.startswith("enum:"):
            allowed = ftype.split(":", 1)[1].split("|")
            if str(value) not in allowed:
                issues.append(f"enum:{name}:got_{value}")
        elif ftype == "datetime" and not isinstance(value, str):
            issues.append(f"type:{name}:expected_datetime_string")

    for rule in VALIDATION_RULES.get(model, ()):
        field = rule.get("field")
        assertion = str(rule.get("assert") or "")
        optional = bool(rule.get("optional"))
        if field not in data:
            if optional or not any(
                f["name"] == field and f.get("required") for f in schema["fields"]
            ):
                continue
        value = data.get(field)
        if assertion == "non_empty" and (value is None or value == ""):
            issues.append(f"rule:{rule.get('rule')}")
        elif assertion.startswith("gt:") and isinstance(value, (int, float)):
            if not (value > float(assertion.split(":", 1)[1])):
                issues.append(f"rule:{rule.get('rule')}")
        elif assertion.startswith("gte:") and isinstance(value, (int, float)):
            if not (value >= float(assertion.split(":", 1)[1])):
                issues.append(f"rule:{rule.get('rule')}")
        elif assertion.startswith("in:"):
            allowed = assertion.split(":", 1)[1].split(",")
            if str(value) not in allowed:
                issues.append(f"rule:{rule.get('rule')}")
        elif assertion == "eq:true" and value is not True:
            issues.append(f"rule:{rule.get('rule')}")
        elif assertion == "eq:false" and value is not False:
            issues.append(f"rule:{rule.get('rule')}")
        elif assertion == "is_array" and not isinstance(value, list):
            issues.append(f"rule:{rule.get('rule')}")
        elif assertion.startswith("range:") and isinstance(value, (int, float)):
            lo, hi = assertion.split(":", 1)[1].split(",")
            if not (float(lo) <= float(value) <= float(hi)):
                issues.append(f"rule:{rule.get('rule')}")
        elif assertion.startswith("gte_field:"):
            other = assertion.split(":", 1)[1]
            if str(value or "") < str(data.get(other) or ""):
                issues.append(f"rule:{rule.get('rule')}")

    return {"ok": len(issues) == 0, "issues": issues, "model": model, "read_only": True}


def compatibility_validation(
    previous: dict[str, Any] | None = None,
    current: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compare two schema snapshots for breaking changes."""
    issues: list[str] = []
    prev = previous or {
        "schema_version": SCHEMA_VERSION,
        "models": {m: build_model_schema(m) for m in CANONICAL_MODELS},
    }
    curr = current or {
        "schema_version": SCHEMA_VERSION,
        "models": {m: build_model_schema(m) for m in CANONICAL_MODELS},
    }
    prev_models = _as_dict(prev.get("models"))
    curr_models = _as_dict(curr.get("models"))

    for name, pschema in prev_models.items():
        if name not in curr_models:
            issues.append(f"model_removed:{name}")
            continue
        pfields = {
            f["name"]: f
            for f in (pschema.get("fields") or [])
            if isinstance(f, dict)
        }
        cfields = {
            f["name"]: f
            for f in (curr_models[name].get("fields") or [])
            if isinstance(f, dict)
        }
        for fname, pf in pfields.items():
            if fname not in cfields:
                issues.append(f"field_removed:{name}.{fname}")
            elif pf.get("type") != cfields[fname].get("type"):
                issues.append(f"type_changed:{name}.{fname}")
            elif pf.get("required") and not cfields[fname].get("required"):
                pass  # relaxing required is compatible
            elif (not pf.get("required")) and cfields[fname].get("required"):
                issues.append(f"required_added:{name}.{fname}")

    for name, cschema in curr_models.items():
        if name not in prev_models:
            continue
        pfields = {
            f["name"]: f
            for f in (prev_models[name].get("fields") or [])
            if isinstance(f, dict)
        }
        for f in cschema.get("fields") or []:
            if not isinstance(f, dict):
                continue
            fname = f.get("name")
            if fname not in pfields and f.get("required"):
                issues.append(f"required_field_added:{name}.{fname}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "rules_applied": [r["rule_id"] for r in COMPATIBILITY_RULES],
        "compatible": len(issues) == 0,
        "read_only": True,
    }


def reference_validation() -> dict[str, Any]:
    """Ensure relationship 'via' fields exist on the source model (or metadata path)."""
    issues: list[str] = []
    for rel in RELATIONSHIPS:
        src = rel.get("from")
        via = str(rel.get("via") or "")
        schema = build_model_schema(str(src))
        field_names = {f["name"] for f in schema["fields"]}
        if via.startswith("metadata."):
            if "metadata" not in field_names:
                issues.append(f"missing_metadata:{src}")
            continue
        if via not in field_names:
            issues.append(f"missing_via_field:{src}.{via}")
        tgt = rel.get("to")
        if tgt not in CANONICAL_MODELS:
            issues.append(f"dangling_target:{tgt}")

    return {
        "ok": len(issues) == 0,
        "issues": issues,
        "relationship_count": len(RELATIONSHIPS),
        "read_only": True,
    }
