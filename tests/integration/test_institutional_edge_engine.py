"""Integration tests — Institutional Edge Engine."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.application.services.institutional_edge_engine import (
    InstitutionalEdgeEngineService,
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


def test_iee_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    spec = (
        "institutional_edge_engine",
        "app.presentation.routers.institutional_edge_engine",
    )
    assert spec in _ROUTER_SPECS
    paths = _collect_paths(list(app.routes))
    assert any("institutional-edge-engine" in p for p in paths)
    assert any(
        p.endswith("/evaluate") and "institutional-edge-engine" in p
        for p in paths
    )


def test_iee_domain_no_order_send() -> None:
    root = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "domain"
        / "institutional_edge_engine"
    )
    offenders = [
        p.name
        for p in root.glob("*.py")
        if "order_send(" in p.read_text(encoding="utf-8")
        or ".order_send" in p.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_iee_service_returns_scorecard() -> None:
    svc = InstitutionalEdgeEngineService()
    trades = [
        {
            "win": i % 2 == 0,
            "pnl": 10 if i % 2 == 0 else -6,
            "rr": 1.1,
            "regime": "trend",
            "session": "london",
            "volatility": "low",
            "entry_timing": "ok",
            "exit_timing": "ok",
            "mae": 0.3,
            "mfe": 1.0,
            "holding_time_sec": 100,
            "exit_efficiency": 70,
            "risk_pct": 0.5,
        }
        for i in range(30)
    ]
    out = svc.evaluate(
        {
            "completed_trades": trades,
            "discipline_facts": {"rule_compliance_pct": 90},
        }
    )
    assert out["auditable"] is True
    assert out["institutional_score"]["status"] in {
        "available",
        "insufficient_data",
    }
