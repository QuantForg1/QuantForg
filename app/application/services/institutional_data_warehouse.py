"""Application service — Institutional Data Warehouse (read-only analytics)."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_data_warehouse.analytics import run_analytics
from app.domain.institutional_data_warehouse.models import DATA_DOMAINS, DataDomain
from app.domain.institutional_data_warehouse.reports import build_warehouse_pack
from app.domain.institutional_data_warehouse.store import (
    InstitutionalDataWarehouse,
    get_warehouse,
)


def run_warehouse(
    *, warehouse: InstitutionalDataWarehouse | None = None
) -> dict[str, Any]:
    return build_warehouse_pack(warehouse or get_warehouse())


def ingest_domain(
    domain: str,
    rows: list[dict[str, Any]] | None,
    *,
    environment: str | None = None,
    replace: bool = False,
    warehouse: InstitutionalDataWarehouse | None = None,
) -> dict[str, Any]:
    if domain not in DATA_DOMAINS:
        return {
            "status": "unavailable",
            "reason": f"Unknown domain '{domain}'",
            "allowed": list(DATA_DOMAINS),
        }
    wh = warehouse or get_warehouse()
    n = wh.ingest(
        domain,  # type: ignore[arg-type]
        rows,
        environment=environment,
        replace=replace,
    )
    return {
        "status": "ingested",
        "domain": domain,
        "records": n,
        "read_only": True,
        "source_mutated": False,
    }


def snapshot_read_only_sources(
    *,
    warehouse: InstitutionalDataWarehouse | None = None,
    journal_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Best-effort deep-copy ingest from live advisory stores — never mutates them."""
    wh = warehouse or get_warehouse()
    ingested: dict[str, int] = {}

    if journal_rows:
        ingested["trades"] = wh.ingest("trades", journal_rows, environment="live")
        ingested["execution"] = wh.ingest(
            "execution", journal_rows, environment="live"
        )

    try:
        from app.domain.replay_evidence_lab.evidence_store import get_evidence_database

        db = get_evidence_database()
        ingested["replay"] = wh.ingest(
            "replay", db.list("replay"), environment="replay", replace=True
        )
        ingested["evidence"] = wh.ingest(
            "evidence",
            db.list("live") + db.list("demo") + db.list("research"),
            environment="mixed",
            replace=True,
        )
    except Exception:
        ingested.setdefault("replay", 0)
        ingested.setdefault("evidence", 0)

    try:
        from app.domain.audit_governance.change_history import (
            get_config_change_history,
        )
        from app.domain.audit_governance.store import get_audit_store
        from app.domain.audit_governance.versions import get_trade_version_registry

        events = get_audit_store().list(limit=2000)
        ingested["governance"] = wh.ingest(
            "governance", events, environment="governance", replace=True
        )
        # Map governance categories into risk/safety when applicable
        risk_ev = [e for e in events if e.get("category") == "risk"]
        safety_ev = [e for e in events if e.get("category") == "safety"]
        ingested["risk"] = wh.ingest("risk", risk_ev, environment="governance")
        ingested["safety"] = wh.ingest("safety", safety_ev, environment="governance")
        ingested["configuration"] = wh.ingest(
            "configuration",
            get_config_change_history().list(limit=2000),
            environment="governance",
            replace=True,
        )
        version_tags = get_trade_version_registry().list(limit=2000)
        # Enrich trades domain with version-tagged rows (analytics copies)
        ingested["signals"] = wh.ingest(
            "signals",
            [
                e
                for e in events
                if e.get("category") in {"strategy", "performance"}
                or e.get("action") == "trade_version_tagged"
            ],
            environment="governance",
        )
        if version_tags:
            wh.ingest("trades", version_tags, environment="governance")
    except Exception:
        ingested.setdefault("governance", 0)
        ingested.setdefault("risk", 0)
        ingested.setdefault("safety", 0)
        ingested.setdefault("configuration", 0)

    return {
        "status": "available",
        "ingested": ingested,
        "inventory": wh.inventory(),
        "read_only": True,
        "never_modifies_production_records": True,
    }


def seed_demo_warehouse() -> dict[str, Any]:
    """Local demo datasets for report generation — labeled demo environment."""
    wh = InstitutionalDataWarehouse()
    corr = "corr-idw-demo-1"
    versions = {
        "strategy": "v1.0.1",
        "risk": "v1.0.1",
        "safety": "v1.0.1",
        "execution": "v1.0.1",
    }
    trades = [
        {
            "timestamp": "2026-07-20T08:00:00Z",
            "trade_id": "T-1001",
            "correlation_id": corr,
            "session": "london",
            "regime": "trend",
            "net_pnl": 25,
            "symbol": "XAUUSD",
            "versions": versions,
            "decision": "BUY",
        },
        {
            "timestamp": "2026-07-20T15:00:00Z",
            "trade_id": "T-1002",
            "correlation_id": corr,
            "session": "new_york",
            "regime": "range",
            "net_pnl": -9,
            "symbol": "XAUUSD",
            "versions": versions,
            "decision": "SELL",
        },
    ]
    signals = [
        {
            "timestamp": "2026-07-20T14:55:00Z",
            "correlation_id": corr,
            "decision": "NO_TRADE",
            "no_trade_reason": "spread too wide",
            "session": "new_york",
            "versions": versions,
        }
    ]
    market = [
        {
            "timestamp": "2026-07-20T08:00:00Z",
            "correlation_id": corr,
            "open": 2400,
            "high": 2405,
            "low": 2398,
            "close": 2402,
            "symbol": "XAUUSD",
        }
    ]
    governance = [
        {
            "timestamp": "2026-07-22T09:05:00Z",
            "correlation_id": corr,
            "category": "operations",
            "action": "ops_promotion",
            "actor": "owner.bob",
            "previous_state": "SHADOW",
            "new_state": "CANARY",
        }
    ]
    wh.ingest("trades", trades, environment="demo", replace=True)
    wh.ingest("signals", signals, environment="demo", replace=True)
    wh.ingest("market", market, environment="demo", replace=True)
    wh.ingest("governance", governance, environment="demo", replace=True)
    wh.ingest("replay", trades, environment="demo", replace=True)
    wh.ingest("evidence", trades + signals, environment="demo", replace=True)
    wh.ingest(
        "performance",
        [
            {
                "timestamp": "2026-07-22T10:00:00Z",
                "correlation_id": corr,
                "win_rate": 0.5,
            }
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "orders",
        [
            {
                "timestamp": "2026-07-20T08:00:00Z",
                "trade_id": "T-1001",
                "correlation_id": corr,
            }
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "risk",
        [
            {
                "timestamp": "2026-07-20T15:01:00Z",
                "correlation_id": corr,
                "action": "daily_loss_check",
                "severity": "info",
            }
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "safety",
        [
            {
                "timestamp": "2026-07-22T09:12:00Z",
                "correlation_id": corr,
                "action": "kill_switch_armed",
                "severity": "critical",
            }
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "execution",
        trades,
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "configuration",
        [
            {
                "timestamp": "2026-07-22T09:04:00Z",
                "correlation_id": corr,
                "key": "EXECUTION_ENABLED",
                "previous_value": "false",
                "new_value": "true",
            }
        ],
        environment="demo",
        replace=True,
    )
    wh.ingest(
        "reports",
        [
            {
                "timestamp": "2026-07-22T09:10:00Z",
                "correlation_id": corr,
                "action": "daily_report_generated",
            }
        ],
        environment="demo",
        replace=True,
    )
    # Mirror into process warehouse for API demos
    process = get_warehouse()
    process.clear()
    for domain in DATA_DOMAINS:
        process.ingest(
            domain,  # type: ignore[arg-type]
            [r["payload"] for r in wh.list(domain, limit=10_000)],  # type: ignore[arg-type]
            environment="demo",
            replace=True,
        )
    return build_warehouse_pack(wh)


def query_analytics() -> dict[str, Any]:
    return run_analytics(get_warehouse())


# silence unused import for type alias consumers
_ = DataDomain
