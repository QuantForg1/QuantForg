"""Gateway Manager FastAPI dependencies."""

from __future__ import annotations

import contextlib
from typing import Annotated

from fastapi import Depends

from app.application.services.gateway_manager import GatewayManagerService
from app.domain.cloud.registry import GatewayRegistry
from core.di.container import get_container


def get_gateway_manager() -> GatewayManagerService:
    container = get_container()
    existing = getattr(container, "gateway_manager", None)
    if existing is not None:
        return existing  # type: ignore[no-any-return]

    registry = getattr(container, "gateway_registry", None)
    if registry is None:
        registry = GatewayRegistry()
        with contextlib.suppress(Exception):
            container.gateway_registry = registry  # type: ignore[attr-defined]

    svc = GatewayManagerService(registry=registry)
    with contextlib.suppress(Exception):
        container.gateway_manager = svc  # type: ignore[attr-defined]
    return svc


GatewayManagerDep = Annotated[GatewayManagerService, Depends(get_gateway_manager)]
