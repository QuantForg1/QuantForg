"""Broker Connectivity Framework FastAPI dependencies."""

from __future__ import annotations

import contextlib
from typing import Annotated

from fastapi import Depends

from app.application.services.broker_connectivity import BrokerConnectivityService
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.di.container import get_container


def get_broker_connectivity() -> BrokerConnectivityService:
    container = get_container()
    existing = getattr(container, "broker_connectivity", None)
    if existing is not None:
        return existing  # type: ignore[no-any-return]

    mt5 = getattr(container, "mt5_adapter", None)
    if mt5 is not None and not isinstance(mt5, MT5Adapter):
        mt5 = None

    paper_available = getattr(container, "paper_trading_engine", None) is not None
    svc = BrokerConnectivityService.create(
        mt5=mt5,
        health_monitor=getattr(container, "broker_health_monitor", None),
        reconnect_manager=getattr(container, "broker_reconnect_manager", None),
        paper_available=paper_available,
    )
    with contextlib.suppress(Exception):
        container.broker_connectivity = svc  # type: ignore[attr-defined]
    return svc


BrokerConnectivityDep = Annotated[
    BrokerConnectivityService, Depends(get_broker_connectivity)
]
