"""API reliability — catalogue / status messages stay distinct (no collapse)."""

from __future__ import annotations

from pathlib import Path


def test_catalogue_degraded_copy_not_gateway_disconnected() -> None:
    """Frontend market-status source must keep catalogue ≠ gateway wording."""
    path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "lib"
        / "trading"
        / "market-status.ts"
    )
    text = path.read_text(encoding="utf-8")
    assert "Catalogue degraded" in text
    assert "gatewayOnline === true" in text
    # Must not claim gateway down solely because catalogue timed out.
    assert "backend delayed" in text.lower() or "Tap Retry" in text


def test_pre_trade_blocks_when_gateway_unknown() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "components"
        / "execution"
        / "pre-trade-checklist.tsx"
    )
    text = path.read_text(encoding="utf-8")
    assert "gatewayOnline !== true" in text
    assert "gatewayOnline === true" in text


def test_auth_boot_timeout_bounded() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "providers"
        / "auth-provider.tsx"
    )
    text = path.read_text(encoding="utf-8")
    assert "SESSION_BOOT_TIMEOUT_MS = 25_000" in text
    assert "SESSION_ME_RETRY_MS" in text
    assert "session_timeout" in text


def test_api_client_dedupes_health_gets() -> None:
    path = (
        Path(__file__).resolve().parents[2]
        / "frontend"
        / "src"
        / "lib"
        / "api"
        / "client.ts"
    )
    text = path.read_text(encoding="utf-8")
    assert "inflightGets" in text
    assert "API_AUTH_TIMEOUT_MS = 22_000" in text
    assert "noteApiSlow" in text
