"""Integration tests — Integration Sprint V1."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.integration_sprint_v1 import (
    IntegrationSprintV1Service,
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


def test_integration_sprint_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    assert (
        "integration_sprint_v1",
        "app.presentation.routers.integration_sprint_v1",
    ) in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("integration-sprint-v1" in p for p in paths)
    assert any(p.endswith("/bus") and "integration-sprint-v1" in p for p in paths)
    assert any("/hydrate" in p for p in paths)


def test_integration_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "integration_sprint_v1"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_service_read_only_bus() -> None:
    out = IntegrationSprintV1Service().bus()
    assert out["read_only"] is True
    assert out["never_places_trades"] is True
    assert "health_summary" in out
    assert "connected_feeds" in out
    assert "missing_feeds" in out
