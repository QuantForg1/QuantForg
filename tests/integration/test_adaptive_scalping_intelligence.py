"""Integration tests — Adaptive Scalping Intelligence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.adaptive_scalping_intelligence import (
    AdaptiveScalpingIntelligenceService,
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


def test_asi_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    spec = (
        "adaptive_scalping_intelligence",
        "app.presentation.routers.adaptive_scalping_intelligence",
    )
    assert spec in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("adaptive-scalping-intelligence" in p for p in paths)
    assert any(
        p.endswith("/evaluate") and "adaptive-scalping-intelligence" in p
        for p in paths
    )


def test_asi_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "adaptive_scalping_intelligence"
    )
    offenders: list[str] = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "order_send(" in text or ".order_send" in text:
            offenders.append(path.name)
    assert offenders == []


def test_asi_service_evaluate_auditable() -> None:
    svc = AdaptiveScalpingIntelligenceService()
    out = svc.evaluate(
        {
            "session": "london",
            "historical_observations": [
                {
                    "session": "london",
                    "hour_utc": 10,
                    "quality": 70,
                    "personality": "trending",
                    "pattern_id": "a",
                    "confidence": 70,
                    "win": True,
                }
            ]
            * 20,
        }
    )
    assert out["auditable"] is True
    assert out["never_order_send"] is True
    assert out["audit_id"]
