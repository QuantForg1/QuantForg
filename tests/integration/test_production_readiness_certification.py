"""Integration tests — Production Readiness Certification."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.production_readiness_certification import (
    ProductionReadinessCertificationService,
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


def test_prc_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    assert (
        "production_readiness_certification",
        "app.presentation.routers.production_readiness_certification",
    ) in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("production-readiness-certification" in p for p in paths)
    assert any(
        p.endswith("/evaluate") and "production-readiness-certification" in p
        for p in paths
    )


def test_prc_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "production_readiness_certification"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_prc_service_certifies_only() -> None:
    out = ProductionReadinessCertificationService().evaluate(
        {
            "reliability": {
                "service_uptime_pct": 99.9,
                "recovery_success_rate_pct": 100,
                "restart_recovery_ok": True,
                "watchdog_health_ok": True,
                "mt5_synchronization_ok": True,
                "incident_rate_per_day": 0,
                "duplicate_protection_ok": True,
            }
        }
    )
    assert out["certifies_only"] is True
    assert out["never_order_send"] is True
    assert out["changes_configuration_automatically"] is False
    assert out["human_approval_required"] is True
