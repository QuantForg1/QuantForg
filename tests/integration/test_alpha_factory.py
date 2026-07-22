"""Integration tests — Alpha Factory."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.alpha_factory import AlphaFactoryService

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


def test_alpha_factory_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    assert (
        "alpha_factory",
        "app.presentation.routers.alpha_factory",
    ) in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("alpha-factory" in p for p in paths)
    assert any(p.endswith("/evaluate") and "alpha-factory" in p for p in paths)


def test_alpha_factory_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2] / "app" / "domain" / "alpha_factory"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_alpha_factory_service_isolated() -> None:
    out = AlphaFactoryService().evaluate(
        {
            "experiment": {
                "author": "svc",
                "version": "1",
                "status": "draft",
                "description": "x",
            },
            "promotion": {"stage": "Development"},
        }
    )
    assert out["outside_production"] is True
    assert out["never_order_send"] is True
    assert out["automatic_promotion"] is False
