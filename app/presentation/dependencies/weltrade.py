"""Weltrade integration dependencies."""

from __future__ import annotations

import contextlib
from typing import Annotated

from fastapi import Depends

from app.application.services.weltrade_integration import WeltradeIntegrationService
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.di.container import get_container


def get_weltrade_service() -> WeltradeIntegrationService:
    """Resolve Weltrade orchestration from the process DI container.

    Matches Gateway Manager / MT5 deps — never ``request.app.state.container``.
    """
    container = get_container()
    existing = getattr(container, "weltrade_integration", None)
    if existing is not None:
        return existing  # type: ignore[no-any-return]

    adapter = getattr(container, "mt5_adapter", None)
    if not isinstance(adapter, MT5Adapter):
        raise RuntimeError("MT5 adapter is not available for Weltrade integration")

    svc = WeltradeIntegrationService(adapter=adapter)
    with contextlib.suppress(Exception):
        container.weltrade_integration = svc  # type: ignore[attr-defined]
    return svc


WeltradeSvc = Annotated[WeltradeIntegrationService, Depends(get_weltrade_service)]
