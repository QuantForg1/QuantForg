"""Integration tests — Live Learning Program."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.live_learning_program import (
    LiveLearningProgramService,
)

pytestmark = [pytest.mark.integration]


def _collect_paths(routes: list[Any]) -> list[str]:
    out: list[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            out.append(str(path))
        original = getattr(route, "original_router", None)
        ctx = getattr(route, "include_context", None)
        if original is not None:
            prefix = str(getattr(ctx, "prefix", "") or "")
            for child in getattr(original, "routes", []) or []:
                child_path = getattr(child, "path", None)
                if child_path:
                    out.append(f"{prefix}{child_path}")
            continue
        nested = getattr(route, "routes", None)
        if nested:
            out.extend(_collect_paths(list(nested)))
    return out


def test_llp_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    assert (
        "live_learning_program",
        "app.presentation.routers.live_learning_program",
    ) in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("live-learning-program" in p for p in paths)
    assert any(
        p.endswith("/evaluate") and "live-learning-program" in p for p in paths
    )


def test_llp_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "live_learning_program"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_llp_service_evidence_only() -> None:
    out = LiveLearningProgramService().evaluate(
        {
            "completed_trades": [
                {
                    "result": 1,
                    "session": "london",
                    "predicted_confidence": 70,
                    "win": True,
                }
            ]
            * 20,
            "operator_feedback": [{"tag": "research_idea", "note": "x"}],
        }
    )
    assert out["evidence_only"] is True
    assert out["never_order_send"] is True
    assert out["auto_tune_parameters"] is False
    assert out["auto_promote_strategies"] is False
