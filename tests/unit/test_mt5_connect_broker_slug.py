"""MT5 connect validates broker_slug against server brand — no cross-borrow."""

from __future__ import annotations

import pytest

from app.application.services.weltrade_integration import WeltradeIntegrationService


@pytest.mark.asyncio
async def test_connect_rejects_cross_broker_server() -> None:
    svc = WeltradeIntegrationService.__new__(WeltradeIntegrationService)

    with pytest.raises(ValueError, match="does not belong"):
        await svc.connect(
            user_id=__import__("uuid").uuid4(),
            login=12345,
            password="x",
            server="Exness-MT5Real8",
            account_type="live",
            broker_slug="xm",
        )


@pytest.mark.asyncio
async def test_connect_requires_server_for_non_weltrade() -> None:
    svc = WeltradeIntegrationService.__new__(WeltradeIntegrationService)

    with pytest.raises(ValueError, match="Exact MT5 server is required"):
        await svc.connect(
            user_id=__import__("uuid").uuid4(),
            login=12345,
            password="x",
            server="auto",
            account_type="live",
            broker_slug="exness",
        )
