"""Integration tests — Institutional Validation Program."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.institutional_validation_program import (
    InstitutionalValidationProgramService,
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


def test_ivp_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    assert (
        "institutional_validation_program",
        "app.presentation.routers.institutional_validation_program",
    ) in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("institutional-validation-program" in p for p in paths)
    assert any(
        p.endswith("/evaluate") and "institutional-validation-program" in p
        for p in paths
    )


def test_ivp_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "institutional_validation_program"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_ivp_service_read_only() -> None:
    out = InstitutionalValidationProgramService().evaluate(
        {
            "completed_trades": [
                {"pnl": 10 if i % 2 else -5} for i in range(40)
            ],
        }
    )
    assert out["read_only"] is True
    assert out["never_order_send"] is True
    assert out["auto_promote_research"] is False
    assert out["modifies_execution"] is False
