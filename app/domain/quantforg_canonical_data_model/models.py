"""QCDM models — QuantForg Canonical Data Model (read-only enterprise contract)."""

from __future__ import annotations

from typing import Any

ISOLATION_FLAGS: dict[str, Any] = {
    "mutates_production": False,
    "executes_trades": False,
    "modifies_production": False,
    "modifies_strategies": False,
    "writes_production_tables": False,
    "schema_contract_read_only": True,
    "canonical_data_model": True,
}

# Enterprise-wide canonical model names
CANONICAL_MODELS: tuple[str, ...] = (
    "Trade",
    "Order",
    "Execution",
    "Signal",
    "Strategy",
    "Experiment",
    "Replay",
    "Simulation",
    "Portfolio",
    "RiskEvent",
    "ValidationEvent",
    "Certification",
    "Release",
    "Incident",
    "Alert",
    "Evidence",
    "Recommendation",
)

SCHEMA_VERSION = "1.0.0"

# Common fields required on every canonical model
COMMON_FIELDS: tuple[dict[str, Any], ...] = (
    {
        "name": "id",
        "type": "string",
        "required": True,
        "description": "Unique identifier",
    },
    {
        "name": "version",
        "type": "string",
        "required": True,
        "description": "Entity version / revision",
    },
    {
        "name": "created_at",
        "type": "datetime",
        "required": True,
        "description": "Creation timestamp (UTC)",
    },
    {
        "name": "updated_at",
        "type": "datetime",
        "required": True,
        "description": "Last update timestamp (UTC)",
    },
    {
        "name": "metadata",
        "type": "object",
        "required": True,
        "description": "Extensible metadata bag",
    },
)

# Model-specific fields (beyond common)
MODEL_FIELDS: dict[str, tuple[dict[str, Any], ...]] = {
    "Trade": (
        {"name": "symbol", "type": "string", "required": True},
        {"name": "side", "type": "enum:buy|sell", "required": True},
        {"name": "quantity", "type": "number", "required": True},
        {"name": "price", "type": "number", "required": True},
        {"name": "order_id", "type": "string", "required": False},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "execution_id", "type": "string", "required": False},
    ),
    "Order": (
        {"name": "symbol", "type": "string", "required": True},
        {"name": "side", "type": "enum:buy|sell", "required": True},
        {"name": "order_type", "type": "string", "required": True},
        {"name": "quantity", "type": "number", "required": True},
        {"name": "status", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "signal_id", "type": "string", "required": False},
    ),
    "Execution": (
        {"name": "order_id", "type": "string", "required": True},
        {"name": "fill_price", "type": "number", "required": True},
        {"name": "fill_quantity", "type": "number", "required": True},
        {"name": "venue", "type": "string", "required": False},
        {"name": "slippage_bps", "type": "number", "required": False},
    ),
    "Signal": (
        {"name": "strategy_id", "type": "string", "required": True},
        {"name": "symbol", "type": "string", "required": True},
        {"name": "direction", "type": "enum:long|short|flat", "required": True},
        {"name": "strength", "type": "number", "required": False},
        {"name": "confidence", "type": "number", "required": False},
    ),
    "Strategy": (
        {"name": "name", "type": "string", "required": True},
        {"name": "lifecycle_state", "type": "string", "required": True},
        {"name": "owner", "type": "string", "required": False},
        {"name": "family", "type": "string", "required": False},
    ),
    "Experiment": (
        {"name": "title", "type": "string", "required": True},
        {"name": "status", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "hypothesis", "type": "string", "required": False},
    ),
    "Replay": (
        {"name": "source_dataset", "type": "string", "required": True},
        {"name": "window_start", "type": "datetime", "required": True},
        {"name": "window_end", "type": "datetime", "required": True},
        {"name": "status", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
    ),
    "Simulation": (
        {"name": "mode", "type": "string", "required": True},
        {"name": "scenario", "type": "string", "required": False},
        {"name": "status", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "experiment_id", "type": "string", "required": False},
    ),
    "Portfolio": (
        {"name": "name", "type": "string", "required": True},
        {"name": "allocations", "type": "array", "required": True},
        {"name": "nav", "type": "number", "required": False},
        {"name": "currency", "type": "string", "required": False},
    ),
    "RiskEvent": (
        {"name": "severity", "type": "enum:info|warning|critical", "required": True},
        {"name": "kind", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "portfolio_id", "type": "string", "required": False},
        {"name": "metric", "type": "string", "required": False},
    ),
    "ValidationEvent": (
        {"name": "result", "type": "enum:pass|fail|warn", "required": True},
        {"name": "suite", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "confidence", "type": "number", "required": False},
    ),
    "Certification": (
        {"name": "level", "type": "string", "required": True},
        {"name": "score", "type": "number", "required": False},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "blockers", "type": "array", "required": False},
    ),
    "Release": (
        {"name": "release_version", "type": "string", "required": True},
        {"name": "status", "type": "string", "required": True},
        {"name": "strategy_id", "type": "string", "required": False},
        {"name": "certification_id", "type": "string", "required": False},
    ),
    "Incident": (
        {"name": "severity", "type": "enum:info|warning|critical", "required": True},
        {"name": "status", "type": "string", "required": True},
        {"name": "summary", "type": "string", "required": True},
        {"name": "related_alert_ids", "type": "array", "required": False},
    ),
    "Alert": (
        {"name": "severity", "type": "enum:info|warning|critical", "required": True},
        {"name": "category", "type": "string", "required": True},
        {"name": "source", "type": "string", "required": True},
        {"name": "message", "type": "string", "required": True},
    ),
    "Evidence": (
        {"name": "kind", "type": "string", "required": True},
        {"name": "uri", "type": "string", "required": False},
        {"name": "checksum", "type": "string", "required": False},
        {"name": "linked_entity_type", "type": "string", "required": False},
        {"name": "linked_entity_id", "type": "string", "required": False},
    ),
    "Recommendation": (
        {"name": "kind", "type": "string", "required": True},
        {"name": "priority", "type": "string", "required": True},
        {"name": "title", "type": "string", "required": True},
        {"name": "requires_human_approval", "type": "boolean", "required": True},
        {"name": "auto_applied", "type": "boolean", "required": True},
    ),
}

# Directed relationships: from_model -> to_model via field
RELATIONSHIPS: tuple[dict[str, Any], ...] = (
    {"from": "Trade", "to": "Order", "via": "order_id", "cardinality": "many_to_one"},
    {"from": "Trade", "to": "Execution", "via": "execution_id", "cardinality": "many_to_one"},
    {"from": "Trade", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Order", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Order", "to": "Signal", "via": "signal_id", "cardinality": "many_to_one"},
    {"from": "Execution", "to": "Order", "via": "order_id", "cardinality": "many_to_one"},
    {"from": "Signal", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Experiment", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Replay", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Simulation", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Simulation", "to": "Experiment", "via": "experiment_id", "cardinality": "many_to_one"},
    {"from": "RiskEvent", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "RiskEvent", "to": "Portfolio", "via": "portfolio_id", "cardinality": "many_to_one"},
    {"from": "ValidationEvent", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Certification", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Release", "to": "Strategy", "via": "strategy_id", "cardinality": "many_to_one"},
    {"from": "Release", "to": "Certification", "via": "certification_id", "cardinality": "many_to_one"},
    {"from": "Incident", "to": "Alert", "via": "related_alert_ids", "cardinality": "many_to_many"},
    {"from": "Evidence", "to": "Strategy", "via": "linked_entity_id", "cardinality": "many_to_one"},
    {"from": "Recommendation", "to": "Evidence", "via": "metadata.evidence_ids", "cardinality": "many_to_many"},
)

# Per-model validation rules (declarative)
VALIDATION_RULES: dict[str, tuple[dict[str, Any], ...]] = {
    "Trade": (
        {"rule": "quantity_positive", "field": "quantity", "assert": "gt:0"},
        {"rule": "price_non_negative", "field": "price", "assert": "gte:0"},
        {"rule": "side_enum", "field": "side", "assert": "in:buy,sell"},
    ),
    "Order": (
        {"rule": "quantity_positive", "field": "quantity", "assert": "gt:0"},
        {"rule": "side_enum", "field": "side", "assert": "in:buy,sell"},
    ),
    "Execution": (
        {"rule": "fill_quantity_positive", "field": "fill_quantity", "assert": "gt:0"},
        {"rule": "fill_price_non_negative", "field": "fill_price", "assert": "gte:0"},
        {"rule": "order_ref_required", "field": "order_id", "assert": "non_empty"},
    ),
    "Signal": (
        {"rule": "direction_enum", "field": "direction", "assert": "in:long,short,flat"},
        {"rule": "confidence_range", "field": "confidence", "assert": "range:0,1", "optional": True},
    ),
    "Strategy": (
        {"rule": "name_required", "field": "name", "assert": "non_empty"},
        {"rule": "lifecycle_required", "field": "lifecycle_state", "assert": "non_empty"},
    ),
    "Experiment": (
        {"rule": "title_required", "field": "title", "assert": "non_empty"},
        {"rule": "status_required", "field": "status", "assert": "non_empty"},
    ),
    "Replay": (
        {"rule": "window_order", "field": "window_end", "assert": "gte_field:window_start"},
    ),
    "Simulation": (
        {"rule": "mode_required", "field": "mode", "assert": "non_empty"},
    ),
    "Portfolio": (
        {"rule": "allocations_array", "field": "allocations", "assert": "is_array"},
    ),
    "RiskEvent": (
        {"rule": "severity_enum", "field": "severity", "assert": "in:info,warning,critical"},
    ),
    "ValidationEvent": (
        {"rule": "result_enum", "field": "result", "assert": "in:pass,fail,warn"},
    ),
    "Certification": (
        {"rule": "level_required", "field": "level", "assert": "non_empty"},
    ),
    "Release": (
        {"rule": "version_required", "field": "release_version", "assert": "non_empty"},
        {"rule": "status_required", "field": "status", "assert": "non_empty"},
    ),
    "Incident": (
        {"rule": "severity_enum", "field": "severity", "assert": "in:info,warning,critical"},
        {"rule": "summary_required", "field": "summary", "assert": "non_empty"},
    ),
    "Alert": (
        {"rule": "severity_enum", "field": "severity", "assert": "in:info,warning,critical"},
        {"rule": "message_required", "field": "message", "assert": "non_empty"},
    ),
    "Evidence": (
        {"rule": "kind_required", "field": "kind", "assert": "non_empty"},
    ),
    "Recommendation": (
        {"rule": "human_approval_true", "field": "requires_human_approval", "assert": "eq:true"},
        {"rule": "never_auto_applied", "field": "auto_applied", "assert": "eq:false"},
    ),
}

# Schema governance
VERSION_HISTORY: tuple[dict[str, Any], ...] = (
    {
        "version": "1.0.0",
        "released_at": "2026-07-24T00:00:00+00:00",
        "status": "current",
        "notes": "Initial enterprise canonical contract",
        "models_added": list(CANONICAL_MODELS),
        "breaking": False,
    },
)

COMPATIBILITY_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "additive_fields_ok",
        "description": "Adding optional fields is backward compatible",
        "severity": "info",
    },
    {
        "rule_id": "required_field_add_breaking",
        "description": "Adding required fields is a breaking change",
        "severity": "critical",
    },
    {
        "rule_id": "field_remove_breaking",
        "description": "Removing fields is a breaking change",
        "severity": "critical",
    },
    {
        "rule_id": "type_narrow_breaking",
        "description": "Narrowing field types is a breaking change",
        "severity": "critical",
    },
    {
        "rule_id": "enum_value_remove_breaking",
        "description": "Removing enum values is a breaking change",
        "severity": "critical",
    },
    {
        "rule_id": "major_bump_on_breaking",
        "description": "Breaking changes require major version bump",
        "severity": "critical",
    },
)

DEPRECATION_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "deprecate_before_remove",
        "description": "Fields must be marked deprecated for at least one minor release before removal",
        "min_minor_releases": 1,
    },
    {
        "rule_id": "deprecation_notice",
        "description": "Deprecated fields remain readable; writers should stop emitting them",
    },
    {
        "rule_id": "no_silent_removal",
        "description": "Silent field removal is forbidden",
    },
)

MIGRATION_RULES: tuple[dict[str, Any], ...] = (
    {
        "rule_id": "forward_only_reads",
        "description": "Consumers must tolerate unknown optional fields",
    },
    {
        "rule_id": "rename_via_alias",
        "description": "Renames require alias period covering both old and new names",
    },
    {
        "rule_id": "no_auto_migrate_production",
        "description": "QCDM never auto-migrates production data stores",
    },
    {
        "rule_id": "advisory_migration_plan",
        "description": "Migration plans are advisory documentation only",
    },
)
