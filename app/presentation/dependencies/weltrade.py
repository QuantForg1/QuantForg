"""Weltrade integration dependencies."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


def get_weltrade_service(request: Request) -> WeltradeIntegrationService:
    container = request.app.state.container
    existing = getattr(container, "weltrade_integration", None)
    if existing is not None:
        return existing  # type: ignore[no-any-return]
    adapter: MT5Adapter = container.mt5_adapter
    svc = WeltradeIntegrationService(adapter=adapter)
    container.weltrade_integration = svc  # type: ignore[attr-defined]
    return svc


WeltradeSvc = Annotated[WeltradeIntegrationService, Depends(get_weltrade_service)]
