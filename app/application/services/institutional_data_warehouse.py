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

    # Optional read-only copies from research / ops analytics desks
    try:
        from app.domain.institutional_research_lab import get_irl

        lab = get_irl()
        experiments = lab.list_experiments(limit=100)
        ingested["research"] = wh.ingest(
            "research",
            experiments,
            environment="research",
            replace=True,
            source="irl",
        )
    except Exception:
        ingested.setdefault("research", 0)

    try:
        from app.application.services.market_regime_intelligence import (
            build_market_regime_intelligence,
        )

        regime = build_market_regime_intelligence(limit=50)
        hist = regime.get("history") if isinstance(regime.get("history"), list) else []
        current = regime.get("current")
        rows = list(hist)
        if isinstance(current, dict):
            rows = [current, *rows]
        ingested["regimes"] = wh.ingest(
            "regimes", rows, environment="analytics", replace=True, source="mri"
        )
    except Exception:
        ingested.setdefault("regimes", 0)

    try:
        from app.application.services.adaptive_opportunity_timeline import (
            timeline_snapshot_from_diagnostics,
        )
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        snap = get_strategy_diagnostics_store().snapshot(limit=50)
        tl = timeline_snapshot_from_diagnostics(snap, limit=50)
        points = tl.get("points") if isinstance(tl.get("points"), list) else []
        ingested["opportunity"] = wh.ingest(
            "opportunity",
            points,
            environment="analytics",
            replace=True,
            source="opportunity_timeline",
        )
    except Exception:
        ingested.setdefault("opportunity", 0)

    try:
        from app.application.services.strategy_diagnostics import (
            get_strategy_diagnostics_store,
        )

        snap = get_strategy_diagnostics_store().snapshot(limit=50)
        cycles = list(snap.get("cycles") or [])
        ingested["diagnostics"] = wh.ingest(
            "diagnostics",
            cycles,
            environment="analytics",
            replace=True,
            source="diagnostics",
        )
    except Exception:
        ingested.setdefault("diagnostics", 0)

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
    wh.ingest(
        "oms",
        [{"timestamp": "2026-07-20T08:00:01Z", "correlation_id": corr, "oms_status": "filled"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "gateway",
        [{"timestamp": "2026-07-20T08:00:02Z", "correlation_id": corr, "action": "health_ok"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "broker",
        [{"timestamp": "2026-07-20T08:00:03Z", "correlation_id": corr, "action": "deal"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "research",
        [{"timestamp": "2026-07-21T10:00:00Z", "correlation_id": corr, "verdict": "Research Passed"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "portfolio",
        [{"timestamp": "2026-07-21T11:00:00Z", "correlation_id": corr, "net_profit": 16}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "regimes",
        [{"timestamp": "2026-07-21T11:05:00Z", "correlation_id": corr, "regime": "trend"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "opportunity",
        [{"timestamp": "2026-07-21T11:06:00Z", "correlation_id": corr, "meter": 42}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "diagnostics",
        [{"timestamp": "2026-07-21T11:07:00Z", "correlation_id": corr, "cycle_id": "c-1"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "audit",
        [{"timestamp": "2026-07-22T09:05:00Z", "correlation_id": corr, "action": "ops_promotion"}],
        environment="demo",
        replace=True,
        source="idw:demo",
    )
    wh.ingest(
        "strategy_decisions",
        [{"timestamp": "2026-07-20T07:59:00Z", "correlation_id": corr, "decision": "BUY"}],
        environment="demo",
        replace=True,
        source="idw:demo",
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
            source="idw:demo",
        )
    return build_warehouse_pack(wh)


def query_analytics() -> dict[str, Any]:
    return run_analytics(get_warehouse())


def query_dimensional() -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.dimensional import (
        build_dimensional_model,
    )

    return build_dimensional_model(get_warehouse())


def query_data_quality() -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.quality_monitor import (
        run_data_quality_monitor,
    )

    return run_data_quality_monitor(get_warehouse())


def query_retention(*, apply: bool = False) -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.retention import (
        apply_retention_classification,
        retention_status,
    )

    wh = get_warehouse()
    if apply:
        return apply_retention_classification(wh)
    return retention_status(wh)


def query_aggregation(
    *,
    domain: str = "trades",
    grain: str = "day",
) -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.dimensional import (
        historical_aggregation,
    )

    return historical_aggregation(get_warehouse(), domain=domain, grain=grain)


def query_rolling(
    *,
    domain: str = "trades",
    window: int = 20,
) -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.dimensional import rolling_statistics

    return rolling_statistics(get_warehouse(), domain=domain, window=window)


# silence unused import for type alias consumers
_ = DataDomain
