"""Integration — Institutional Data Warehouse isolation."""

from __future__ import annotations

import pytest

from app.domain.institutional_data_warehouse.models import DATA_DOMAINS, HARD_LOCKS
from app.domain.institutional_data_warehouse.reports import build_warehouse_pack
from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse
from app.main import _ROUTER_SPECS

pytestmark = pytest.mark.integration


def test_router_registered() -> None:
    assert "institutional_data_warehouse" in {n for n, _ in _ROUTER_SPECS}


def test_expanded_domains_present() -> None:
    required = {
        "market",
        "signals",
        "strategy_decisions",
        "risk",
        "safety",
        "oms",
        "execution",
        "gateway",
        "broker",
        "replay",
        "research",
        "portfolio",
        "regimes",
        "opportunity",
        "diagnostics",
        "audit",
    }
    assert required.issubset(set(DATA_DOMAINS))


def test_hard_locks_immutable() -> None:
    assert HARD_LOCKS["read_only_warehouse"] is True
    assert HARD_LOCKS["never_modifies_strategy"] is True
    assert HARD_LOCKS["never_modifies_oms_gateway_auto_trading"] is True
    assert HARD_LOCKS["immutable_event_storage"] is True


def test_pack_never_mutates_production_flags() -> None:
    wh = InstitutionalDataWarehouse()
    wh.ingest(
        "trades",
        [
            {
                "timestamp": "2026-07-20T08:00:00Z",
                "correlation_id": "x",
                "session": "london",
                "net_pnl": 1,
            }
        ],
        environment="demo",
        source="integration",
    )
    pack = build_warehouse_pack(wh)
    assert pack["read_only"] is True
    assert pack["analytics_infrastructure_only"] is True
    assert pack["hard_locks"]["never_modifies_production_records"] is True
