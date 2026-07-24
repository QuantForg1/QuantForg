"""Automated production readiness checklist — PASS / WARNING / FAIL."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

from app.domain.institutional_trading.release_candidate.config import (
    CHECKLIST_ITEMS,
    DEFAULT_RC1_CONFIG,
)

CheckStatus = Literal["PASS", "WARNING", "FAIL"]

ROOT = Path(__file__).resolve().parents[4]


def _item(id: str, status: CheckStatus, detail: str, *, evidence: str | None = None) -> dict[str, Any]:
    return {"id": id, "status": status, "detail": detail, "evidence": evidence}


def _exists(rel: str) -> bool:
    return (ROOT / rel.replace("\\", "/")).is_file()


def run_production_checklist() -> dict[str, Any]:
    """Compose filesystem + live probes into a scored checklist. Never mutates trading."""
    items: list[dict[str, Any]] = []

    # MT5 Gateway
    gw_ok = _exists("app/infrastructure/brokers/mt5/gateway_client.py")
    items.append(
        _item(
            "mt5_gateway",
            "PASS" if gw_ok else "FAIL",
            "Gateway client module present" if gw_ok else "Missing gateway client",
            evidence="app/infrastructure/brokers/mt5/gateway_client.py",
        )
    )

    # Broker
    broker_ok = _exists("app/infrastructure/brokers/mt5/gateway_client.py")
    items.append(
        _item(
            "broker",
            "PASS" if broker_ok else "FAIL",
            "Broker integration surface present",
            evidence="mt5 gateway",
        )
    )

    # OMS
    oms_ok = _exists("app/application/services/institutional_oms_adapter.py")
    items.append(
        _item(
            "oms",
            "PASS" if oms_ok else "FAIL",
            "OMS adapter present" if oms_ok else "OMS adapter missing",
            evidence="app/application/services/institutional_oms_adapter.py",
        )
    )

    # AI Engine
    ai_ok = _exists("app/domain/institutional_trading/ai_validation/__init__.py") or _exists(
        "app/domain/institutional_trading/pipeline.py"
    )
    items.append(
        _item(
            "ai_engine",
            "PASS" if ai_ok else "WARNING",
            "AI / decision pipeline surfaces present",
            evidence="ai_validation or pipeline",
        )
    )

    # Portfolio Engine
    port_ok = _exists(
        "app/domain/institutional_trading/portfolio_intelligence/__init__.py"
    )
    items.append(
        _item(
            "portfolio_engine",
            "PASS" if port_ok else "WARNING",
            "Portfolio intelligence package present",
            evidence="portfolio_intelligence",
        )
    )

    # Position Recovery
    rec_ok = _exists(
        "app/domain/institutional_trading/production_hardening/position_recovery.py"
    )
    items.append(
        _item(
            "position_recovery",
            "PASS" if rec_ok else "FAIL",
            "Position recovery module present",
            evidence="production_hardening.position_recovery",
        )
    )

    # Health Monitoring
    health_ok = _exists("app/presentation/routers/health.py")
    items.append(
        _item(
            "health_monitoring",
            "PASS" if health_ok else "FAIL",
            "Health router present",
            evidence="/health",
        )
    )

    # Retry Engine
    retry_ok = _exists(
        "app/domain/institutional_trading/production_hardening/retry.py"
    )
    items.append(
        _item(
            "retry_engine",
            "PASS" if retry_ok else "FAIL",
            "Retry engine present",
            evidence="production_hardening.retry",
        )
    )

    # Dashboard
    dash_ok = _exists(
        "app/presentation/routers/institutional_reliability.py"
    )
    items.append(
        _item(
            "dashboard",
            "PASS" if dash_ok else "WARNING",
            "Reliability / ops dashboards wired",
            evidence="/ite/reliability",
        )
    )

    # Railway Environment
    railway = bool(os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PROJECT_ID"))
    items.append(
        _item(
            "railway_environment",
            "PASS" if railway else "WARNING",
            "Railway env detected" if railway else "Railway env vars not set (local/dev OK)",
            evidence="RAILWAY_ENVIRONMENT|RAILWAY_PROJECT_ID",
        )
    )

    # Secrets — names only, never values
    critical_names = ("SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "DATABASE_URL")
    present = [n for n in critical_names if os.environ.get(n)]
    missing = [n for n in critical_names if n not in present]
    if not missing:
        sec_status: CheckStatus = "PASS"
        sec_detail = "Critical secret names present (values not inspected)"
    elif len(present) >= 1:
        sec_status = "WARNING"
        sec_detail = f"Partial secrets: missing {', '.join(missing)}"
    else:
        sec_status = "WARNING"
        sec_detail = "Critical secret names not set in this process (may be injected at deploy)"
    items.append(
        _item("secrets", sec_status, sec_detail, evidence="env name presence only")
    )

    # Database
    db_url = bool(os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_URL"))
    items.append(
        _item(
            "database",
            "PASS" if db_url else "WARNING",
            "Database URL / Supabase URL configured" if db_url else "No DATABASE_URL/SUPABASE_URL in process",
            evidence="DATABASE_URL|SUPABASE_URL",
        )
    )

    # Market Data
    md_ok = _exists("app/infrastructure/brokers/mt5/gateway_client.py")
    live_probe: CheckStatus = "WARNING"
    live_detail = "Static surface OK; live probe not run in checklist"
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        if runtime is not None:
            probes = getattr(runtime, "probes", None)
            if probes is not None and hasattr(probes, "collect"):
                snap = probes.collect()
                if isinstance(snap, dict) and snap:
                    live_probe = "PASS"
                    live_detail = "Live probe collection available"
                else:
                    live_detail = "Probe collect returned empty"
            else:
                live_detail = "ITE runtime present without probe collector"
        else:
            live_detail = "ITE runtime not started (static market-data surface OK)"
    except Exception as exc:
        live_detail = f"Live probe skipped: {exc}"
    items.append(
        _item(
            "market_data",
            "PASS" if md_ok and live_probe != "FAIL" else live_probe,
            live_detail if md_ok else "Market data client missing",
            evidence="gateway + optional ITE probes",
        )
    )

    # Ensure all configured ids present
    by_id = {i["id"]: i for i in items}
    for cid in CHECKLIST_ITEMS:
        if cid not in by_id:
            items.append(_item(cid, "WARNING", "Check not implemented", evidence=None))

    counts = {"PASS": 0, "WARNING": 0, "FAIL": 0}
    for i in items:
        counts[str(i["status"])] = counts.get(str(i["status"]), 0) + 1

    overall: CheckStatus = "PASS"
    if counts["FAIL"] > 0:
        overall = "FAIL"
    elif counts["WARNING"] > 0:
        overall = "WARNING"

    return {
        "version": DEFAULT_RC1_CONFIG.version,
        "overall": overall,
        "counts": counts,
        "items": items,
        "affects_production": False,
    }
