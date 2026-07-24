"""Auto-generate research documentation snippets."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


def document_experiment(exp: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Experiment: {exp.get('name')}",
            f"- ID: {exp.get('id')}",
            f"- Author: {exp.get('author')}",
            f"- Status: {exp.get('status')}",
            f"- Start: {exp.get('start_date')} End: {exp.get('end_date')}",
            f"- Sample size: {exp.get('sample_size')}",
            f"- Success criteria: {exp.get('success_criteria')}",
            f"- Description: {exp.get('description')}",
            f"- Generated: {datetime.now(UTC).isoformat()}",
            "",
            "Isolation: does not affect live trading until explicit approval.",
        ]
    )


def document_model_change(model: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Model: {model.get('version')}",
            f"- Author: {model.get('author')}",
            f"- Date: {model.get('date')}",
            f"- Approval: {model.get('approval_status')}",
            f"- Notes: {model.get('notes')}",
            f"- Performance: {model.get('performance')}",
            "",
            "Only approved models may be promoted; promotion never auto-deploys.",
        ]
    )


def document_config_change(event: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Config change: {event.get('key')}",
            f"- User: {event.get('user')}",
            f"- At: {event.get('at')}",
            f"- Category: {event.get('category')}",
            f"- Previous: {event.get('previous_value')}",
            f"- New: {event.get('new_value')}",
            f"- Reason: {event.get('reason')}",
        ]
    )


def document_optimization(run: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"# Optimization: {run.get('target')}",
            f"- Author: {run.get('author')}",
            f"- At: {run.get('at')}",
            f"- Best score: {run.get('best_score')}",
            f"- Best params: {run.get('best_params')}",
            f"- Metrics: {run.get('metrics')}",
            f"- Applied: false",
            f"- Notes: {run.get('notes')}",
        ]
    )
