"""Unit tests — Institutional Data Warehouse (read-only analytics)."""

from __future__ import annotations

import pytest

from app.domain.institutional_data_warehouse.analytics import (
    no_trade_analysis,
    performance_by_session,
    performance_by_strategy_version,
)
from app.domain.institutional_data_warehouse.reports import build_warehouse_pack
from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse


def _seed(wh: InstitutionalDataWarehouse) -> None:
    versions = {
        "strategy": "v1.0.1",
        "risk": "v1.0.1",
        "safety": "v1.0.1",
        "execution": "v1.0.1",
    }
    wh.ingest(
        "trades",
        [
            {
                "timestamp": "2026-07-20T08:00:00Z",
                "trade_id": "T1",
                "correlation_id": "c1",
                "session": "london",
                "regime": "trend",
                "net_pnl": 20,
                "versions": versions,
            },
            {
                "timestamp": "2026-07-20T15:00:00Z",
                "trade_id": "T2",
                "correlation_id": "c1",
                "session": "new_york",
                "regime": "range",
                "net_pnl": -8,
                "versions": versions,
            },
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "signals",
        [
            {
                "timestamp": "2026-07-20T14:55:00Z",
                "correlation_id": "c1",
                "decision": "NO_TRADE",
                "no_trade_reason": "spread too wide",
                "versions": versions,
            }
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "governance",
        [
            {
                "timestamp": "2026-07-22T09:05:00Z",
                "correlation_id": "c1",
                "action": "ops_promotion",
            }
        ],
        environment="demo",
        replace=True,
    )


@pytest.mark.unit
class TestInstitutionalDataWarehouse:
    def test_ingest_deep_copy_does_not_mutate_source(self) -> None:
        wh = InstitutionalDataWarehouse()
        source = [{"timestamp": "2026-07-20T08:00:00Z", "net_pnl": 1, "marker": "x"}]
        wh.ingest("trades", source, environment="demo")
        source[0]["marker"] = "mutated"
        rows = wh.list("trades")
        assert rows[0]["payload"]["marker"] == "x"
        assert rows[0]["read_only"] is True
        assert rows[0]["source_mutated"] is False

    def test_record_keys_when_available(self) -> None:
        wh = InstitutionalDataWarehouse()
        _seed(wh)
        row = wh.list("trades")[0]
        assert row["timestamp"]
        assert row["correlation_id"] == "c1"
        assert row["trade_id"] == "T1"
        assert row["session"] == "london"
        assert row["symbol"] == "XAUUSD"
        assert row["strategy_version"] == "v1.0.1"
        assert row["risk_version"] == "v1.0.1"
        assert row["safety_version"] == "v1.0.1"
        assert row["execution_version"] == "v1.0.1"

    def test_analytics_queries(self) -> None:
        wh = InstitutionalDataWarehouse()
        _seed(wh)
        by_ver = performance_by_strategy_version(wh)
        assert "v1.0.1" in by_ver["by_strategy_version"]
        by_sess = performance_by_session(wh)
        assert by_sess["by_session"]["london"]["trades"] == 1
        nt = no_trade_analysis(wh)
        assert nt["no_trade_count"] == 1
        assert nt["reason_histogram"]["spread too wide"] == 1

    def test_domains_isolated(self) -> None:
        wh = InstitutionalDataWarehouse()
        _seed(wh)
        assert wh.counts()["trades"] == 2
        assert wh.counts()["signals"] == 1
        assert wh.counts()["market"] == 0

    def test_filters(self) -> None:
        wh = InstitutionalDataWarehouse()
        _seed(wh)
        london = wh.list("trades", session="london")
        assert len(london) == 1
        found = wh.list("trades", q="T2")
        assert len(found) == 1

    def test_pack_reports_and_locks(self) -> None:
        wh = InstitutionalDataWarehouse()
        _seed(wh)
        pack = build_warehouse_pack(wh)
        assert pack["read_only"] is True
        assert pack["hard_locks"]["never_modifies_production_records"] is True
        assert "warehouse_health_report" in pack["reports"]
        assert "data_coverage_report" in pack["reports"]
        assert "data_quality_report" in pack["reports"]
        assert "correlation_report" in pack["reports"]
        assert pack["reports"]["correlation_report"]["cross_domain_correlations"] >= 1
        assert isinstance(pack["recommendations"], list)

    def test_missing_fields_not_fabricated(self) -> None:
        wh = InstitutionalDataWarehouse()
        wh.ingest("trades", [{"net_pnl": 5}], environment="demo")
        row = wh.list("trades")[0]
        assert row["timestamp"] is None
        assert row["strategy_version"] is None
        assert row["correlation_id"] is None
