"""Map stored reason text through the existing catalog.

An unknown reason stays blank. The original record is preserved.
"""

from __future__ import annotations

from typing import Any

from app.domain.execution_engine.reasons import humanize_reason

SCHEMA_VERSION = "trade-explanation.v1"


def explain_reasons(reasons: list[str] | tuple[str, ...] | None) -> dict[str, Any]:
    """Explain catalogued reasons. Missing or unknown text is not rewritten."""
    items: list[dict[str, Any]] = []
    for raw in reasons or []:
        original = str(raw).strip()
        if not original:
            items.append(_item(original="", sentence=None, status="unavailable"))
            continue
        rendered = humanize_reason(original).strip()
        if not rendered or rendered == original or rendered.lower() == original.lower():
            items.append(_item(original=original, sentence=None, status="unavailable"))
            continue
        items.append(
            _item(original=original, sentence=rendered, status="verified")
        )
    return {
        "schema_version": SCHEMA_VERSION,
        "places_orders": False,
        "overrides_execution": False,
        "authoritative_for_execution": False,
        "source": "execution_reason_catalog",
        "explanations": items,
        "known_limitations": [
            "Sentences are catalog text for a stored reason, not a new decision.",
            "A reason that is not in the catalog stays blank.",
            "This report does not read another user's decision log.",
        ],
    }


def _item(*, original: str, sentence: str | None, status: str) -> dict[str, Any]:
    return {
        "original_reason": original,
        "sentence": sentence,
        "status": status,
        "source": "execution_reason_catalog",
        "authoritative": False,
        "overrides_execution": False,
    }
