"""Integration tests — Scalping AI V2 router registration (no live broker)."""

from __future__ import annotations

from typing import Any

import pytest

pytestmark = [pytest.mark.integration]


def _collect_paths(routes: list[Any]) -> list[str]:
    """Collect paths from FastAPI routes, including ``_IncludedRouter`` mounts."""
    out: list[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if path:
            out.append(str(path))

        # FastAPI ≥0.128 stores included routers as ``_IncludedRouter``.
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


def test_scalping_ai_v2_router_registered(app) -> None:
    from app.main import _ROUTER_SPECS

    spec = ("scalping_ai_v2", "app.presentation.routers.scalping_ai_v2")
    assert spec in _ROUTER_SPECS

    paths = _collect_paths(list(app.routes))
    assert any("scalping-ai-v2" in p for p in paths)
    assert any(p.endswith("/status") and "scalping-ai-v2" in p for p in paths)
    assert any(p.endswith("/cycle") and "scalping-ai-v2" in p for p in paths)
    assert any(
        p.endswith("/diagnostics") and "scalping-ai-v2" in p for p in paths
    )
    assert any(
        p.endswith("/emergency-stop") and "scalping-ai-v2" in p for p in paths
    )
    assert any(p.endswith("/soak") and "scalping-ai-v2" in p for p in paths)


def test_scalping_domain_isolated_from_order_send() -> None:
    """Static contract: domain package must not reference order_send calls."""
    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "app" / "domain" / "scalping_ai_v2"
    offenders: list[str] = []
    for path in root.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        if "order_send(" in text or ".order_send" in text:
            offenders.append(path.name)
    assert offenders == []
