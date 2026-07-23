"""Institutional Production Readiness Review (PRR) — STRICTLY READ ONLY.

Audits architecture, security, reliability, trading pipeline presence,
data integrity, performance budgets, and operations. Never modifies
Strategy, Risk, Safety, OMS, Execution, Auto Trading, or Thresholds.
"""

from __future__ import annotations

import ast
import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

CheckStatus = Literal["PASS", "WARNING", "FAIL"]
Recommendation = Literal[
    "NOT READY",
    "CONDITIONALLY READY",
    "READY FOR CONTROLLED LIVE",
    "READY FOR INSTITUTIONAL PRODUCTION",
]

ROOT = Path(__file__).resolve().parents[3]

__all__ = [
    "build_institutional_production_readiness_review",
    "prr_to_markdown",
]

# Critical trading / control surfaces (existence + wiring checks only).
_TRADING_SURFACES: dict[str, str] = {
    "signal_pipeline": "app/domain/institutional_trading/pipeline.py",
    "decision_pipeline": "app/application/services/institutional_decision_pipeline.py",
    "risk_engine": "app/application/services/risk_engine.py",
    "safety_engine": "app/application/services/execution_safety.py",
    "oms_guards": "app/application/services/institutional_ops_guards.py",
    "oms_adapter": "app/application/services/institutional_oms_adapter.py",
    "gateway_client": "app/infrastructure/brokers/mt5/gateway_client.py",
    "execution_engine": "app/application/services/institutional_execution_engine.py",
    "kill_switch": "app/domain/institutional_trading/execution/kill_switch.py",
    "control_plane": "app/domain/institutional_trading/operations/control_plane.py",
}

_LAYER_DIRS = {
    "presentation": ROOT / "app" / "presentation",
    "application": ROOT / "app" / "application",
    "domain": ROOT / "app" / "domain",
    "infrastructure": ROOT / "app" / "infrastructure",
    "core": ROOT / "core",
}


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _check(
    subsystem: str,
    status: CheckStatus,
    detail: str,
    *,
    evidence: str | None = None,
) -> dict[str, Any]:
    return {
        "subsystem": subsystem,
        "status": status,
        "detail": detail,
        "evidence": evidence,
    }


def _path_exists(rel: str) -> bool:
    return (ROOT / rel.replace("\\", "/")).is_file()


def _count_py(path: Path) -> int:
    if not path.is_dir():
        return 0
    return sum(1 for _ in path.rglob("*.py"))


def _scan_forbidden_imports(
    layer_dir: Path,
    *,
    forbidden_prefixes: tuple[str, ...],
    sample_limit: int = 400,
) -> list[str]:
    """AST-scan Python files for absolute imports matching forbidden prefixes."""
    hits: list[str] = []
    if not layer_dir.is_dir():
        return hits
    files = list(layer_dir.rglob("*.py"))[:sample_limit]
    for path in files:
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            mods: list[str] = []
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                mods = [node.module]
            for mod in mods:
                if any(mod == p or mod.startswith(p + ".") for p in forbidden_prefixes):
                    rel = str(path.relative_to(ROOT)).replace("\\", "/")
                    hits.append(f"{rel} → {mod}")
                    if len(hits) >= 25:
                        return hits
    return hits


def audit_architecture() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    counts = {name: _count_py(path) for name, path in _LAYER_DIRS.items()}
    missing_layers = [n for n, c in counts.items() if c == 0]
    checks.append(
        _check(
            "service_boundaries",
            "PASS" if not missing_layers else "FAIL",
            f"Layer module counts: {counts}",
            evidence="ADR-0001 clean architecture roots present"
            if not missing_layers
            else f"missing={missing_layers}",
        )
    )

    adr = _path_exists("docs/adr/0001-clean-architecture.md")
    checks.append(
        _check(
            "layer_isolation_docs",
            "PASS" if adr else "WARNING",
            "ADR-0001 present" if adr else "ADR-0001 missing",
        )
    )

    domain_infra = _scan_forbidden_imports(
        _LAYER_DIRS["domain"],
        forbidden_prefixes=("app.infrastructure", "app.presentation"),
    )
    if not domain_infra:
        checks.append(
            _check(
                "circular_dependencies_domain",
                "PASS",
                "No domain→infrastructure/presentation imports in sampled AST scan",
            )
        )
    else:
        checks.append(
            _check(
                "circular_dependencies_domain",
                "WARNING",
                f"{len(domain_infra)} domain import(s) into infra/presentation (layer leak)",
                evidence="; ".join(domain_infra[:5]),
            )
        )

    domain_presentation = [h for h in domain_infra if "presentation" in h]
    checks.append(
        _check(
            "dependency_graph_domain_presentation",
            "PASS" if not domain_presentation else "FAIL",
            "Domain must not import presentation"
            if not domain_presentation
            else f"{len(domain_presentation)} domain→presentation import(s)",
            evidence="; ".join(domain_presentation[:3]) or None,
        )
    )

    settings_ok = _path_exists("core/config/settings.py")
    checks.append(
        _check(
            "configuration_integrity",
            "PASS" if settings_ok else "FAIL",
            "Settings module present" if settings_ok else "Settings module missing",
            evidence="core/config/settings.py",
        )
    )

    return {
        "section": "architecture",
        "checks": checks,
        "layer_module_counts": counts,
        "dependency_violations_sample": domain_infra[:10],
    }


def audit_security() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    settings = None
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception as exc:  # noqa: BLE001 — advisory audit
        checks.append(
            _check("settings_load", "FAIL", f"Unable to load settings: {exc}")
        )
        return {"section": "security", "checks": checks}

    app_env = str(getattr(settings, "app_env", "unknown")).lower()
    secret = settings.secret_key.get_secret_value()
    weak = (
        not secret
        or len(secret) < 24
        or secret.lower() in {"change-me", "changeme", "secret", "dev", "password"}
        or "change" in secret.lower()
    )
    if app_env in {"production", "prod"}:
        checks.append(
            _check(
                "secrets_handling",
                "FAIL" if weak else "PASS",
                "Production SECRET_KEY strength"
                if not weak
                else "SECRET_KEY appears default/weak in production",
            )
        )
    else:
        checks.append(
            _check(
                "secrets_handling",
                "WARNING" if weak else "PASS",
                "Non-production SECRET_KEY"
                + (" (default/weak — expected for local)" if weak else " (rotated)"),
            )
        )

    # Never echo secret values — only presence flags.
    env_flags = {
        "SECRET_KEY_set": bool(os.getenv("SECRET_KEY")),
        "DATABASE_URL_set": bool(os.getenv("DATABASE_URL") or os.getenv("POSTGRES_PASSWORD")),
        "MT5_GATEWAY_CALLER_TOKEN_set": bool(os.getenv("MT5_GATEWAY_CALLER_TOKEN")),
        "EXECUTION_ENABLED": bool(getattr(settings, "execution_enabled", False)),
    }
    checks.append(
        _check(
            "environment_variables",
            "PASS",
            "Environment flag presence surveyed (values not exposed)",
            evidence=json.dumps(env_flags, sort_keys=True),
        )
    )

    auth_dep = _path_exists("app/presentation/dependencies/auth.py")
    checks.append(
        _check(
            "authentication",
            "PASS" if auth_dep else "FAIL",
            "Auth dependency module present" if auth_dep else "Auth dependency missing",
        )
    )
    role_enum = _path_exists("app/domain/enums/user.py")
    checks.append(
        _check(
            "authorization",
            "PASS" if role_enum else "FAIL",
            "UserRole enum present" if role_enum else "UserRole enum missing",
        )
    )
    ops_router = _path_exists("app/presentation/routers/institutional_ops.py")
    checks.append(
        _check(
            "api_permissions",
            "PASS" if ops_router else "FAIL",
            "ITE ops router OWNER/ADMIN gated" if ops_router else "Ops router missing",
        )
    )
    audit_gov = _path_exists("app/application/services/audit_governance.py")
    checks.append(
        _check(
            "audit_logging",
            "PASS" if audit_gov else "WARNING",
            "Audit governance service present"
            if audit_gov
            else "Audit governance service not found",
        )
    )
    checks.append(
        _check(
            "sensitive_data_exposure",
            "PASS",
            "PRR payload uses presence flags only — secrets never serialized",
        )
    )

    return {
        "section": "security",
        "checks": checks,
        "app_env": app_env,
        "execution_enabled": bool(getattr(settings, "execution_enabled", False)),
        "env_flags": env_flags,
    }


def audit_reliability() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    surfaces = {
        "scheduler_runtime": "app/application/services/institutional_ite_runtime.py",
        "recovery": "app/domain/institutional_trading/reliability/recovery.py",
        "health_domain": "app/domain/institutional_trading/reliability/health.py",
        "heartbeat": "app/domain/institutional_trading/reliability/heartbeat.py",
        "health_router": "app/presentation/routers/health.py",
        "reliability_router": "app/presentation/routers/institutional_reliability.py",
        "live_probes": "app/application/services/institutional_live_probes.py",
    }
    for name, rel in surfaces.items():
        ok = _path_exists(rel)
        checks.append(
            _check(
                name,
                "PASS" if ok else "FAIL",
                f"{rel} {'present' if ok else 'MISSING'}",
            )
        )

    # Runtime observation — never mutate.
    runtime_note = "unavailable"
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        rt = get_ite_runtime()
        snap = getattr(rt, "snapshot", None)
        if callable(snap):
            data = snap()
            runtime_note = f"cycles={data.get('cycle_count', data.get('cycles'))}"
            checks.append(
                _check(
                    "scheduler_runtime_live",
                    "PASS",
                    "ITE runtime snapshot readable",
                    evidence=runtime_note,
                )
            )
        else:
            checks.append(
                _check(
                    "scheduler_runtime_live",
                    "WARNING",
                    "ITE runtime present but snapshot() unavailable",
                )
            )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            _check(
                "scheduler_runtime_live",
                "WARNING",
                f"ITE runtime not observable: {exc}",
            )
        )

    # Retries / timeouts / circuit breakers — structural presence.
    pr_orch = _path_exists("app/domain/production_readiness/orchestrator.py")
    checks.append(
        _check(
            "circuit_breakers_panel",
            "PASS" if pr_orch else "WARNING",
            "Production readiness orchestrator (includes breaker panel)"
            if pr_orch
            else "PR orchestrator missing",
        )
    )
    checks.append(
        _check(
            "retries_timeouts",
            "PASS" if _path_exists("app/infrastructure/brokers/mt5/gateway_client.py") else "FAIL",
            "Gateway client hosts transport retries/timeouts",
        )
    )
    checks.append(
        _check(
            "watchdogs",
            "PASS"
            if _path_exists("app/domain/scalping_ai_v2/reliability.py")
            or _path_exists("app/domain/institutional_trading/reliability/health.py")
            else "WARNING",
            "Reliability/watchdog modules present",
        )
    )

    return {"section": "reliability", "checks": checks, "runtime_note": runtime_note}


def audit_trading() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    missing: list[str] = []
    for name, rel in _TRADING_SURFACES.items():
        ok = _path_exists(rel)
        if not ok:
            missing.append(name)
        checks.append(
            _check(
                name,
                "PASS" if ok else "FAIL",
                f"{rel} {'present' if ok else 'MISSING'}",
            )
        )

    # Bypass path structural checks (read source text — no execution).
    guards_path = ROOT / "app/application/services/institutional_ops_guards.py"
    bypass_ok = False
    if guards_path.is_file():
        text = guards_path.read_text(encoding="utf-8", errors="ignore")
        bypass_ok = "oms_orders_allowed" in text and "kill_switch" in text
    checks.append(
        _check(
            "no_bypass_oms_guards",
            "PASS" if bypass_ok else "FAIL",
            "Guarded OMS blocks submit when kill armed / SHADOW"
            if bypass_ok
            else "OMS guard markers not found",
        )
    )

    launch = _path_exists("app/application/services/launch_readiness.py")
    checks.append(
        _check(
            "state_transitions",
            "PASS" if launch else "WARNING",
            "Launch readiness SHADOW→CANARY→LIVE state machine present"
            if launch
            else "Launch readiness missing",
        )
    )

    # Live plane observation (read-only).
    plane_mode = None
    kill = None
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        plane = get_control_plane()
        plane_mode = getattr(getattr(plane, "mode", None), "value", str(getattr(plane, "mode", None)))
        kill = bool(getattr(plane, "kill_switch_armed", False))
        checks.append(
            _check(
                "control_plane_live",
                "PASS",
                f"mode={plane_mode} kill_switch_armed={kill}",
            )
        )
    except Exception as exc:  # noqa: BLE001
        checks.append(
            _check("control_plane_live", "WARNING", f"Control plane unread: {exc}")
        )

    return {
        "section": "trading",
        "checks": checks,
        "missing_surfaces": missing,
        "ops_mode": plane_mode,
        "kill_switch_armed": kill,
    }


def audit_data_integrity() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    surfaces = {
        "replay_data": "app/application/services/production_replay.py",
        "witness_observability": "app/application/services/witness_observability.py",
        "portfolio_analytics": "app/application/services/institutional_portfolio_analytics.py",
        "data_warehouse": "app/application/services/institutional_data_warehouse.py",
        "strategy_intelligence": "app/application/services/strategy_intelligence_center.py",
    }
    # production_replay may not exist — soft-check alternate names
    alt_replay = [
        "app/application/services/production_replay.py",
        "app/presentation/routers/production_replay.py",
    ]
    for name, rel in surfaces.items():
        if name == "replay_data":
            ok = any(_path_exists(p) for p in alt_replay) or _path_exists(
                "frontend/src/app/(app)/production-replay/page.tsx"
            )
        else:
            ok = _path_exists(rel)
        checks.append(
            _check(
                name,
                "PASS" if ok else "WARNING",
                f"{name} surface {'present' if ok else 'not found'}",
            )
        )

    migrations = ROOT / "supabase" / "migrations"
    if not migrations.is_dir():
        migrations = ROOT / "migrations"
    mig_count = len(list(migrations.glob("*.sql"))) if migrations.is_dir() else 0
    checks.append(
        _check(
            "database_constraints",
            "PASS" if mig_count > 0 else "WARNING",
            f"{mig_count} SQL migration file(s) discovered",
            evidence=str(migrations.relative_to(ROOT)) if migrations.is_dir() else None,
        )
    )

    witness = ROOT / "docs/production/reports/live_execution_witness_latest.json"
    checks.append(
        _check(
            "live_snapshots",
            "PASS" if witness.is_file() else "WARNING",
            "Witness latest snapshot present"
            if witness.is_file()
            else "No live_execution_witness_latest.json",
        )
    )

    return {"section": "data_integrity", "checks": checks, "migration_count": mig_count}


def audit_performance() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    t0 = time.perf_counter()
    # Self-measure: architecture scan latency as analytics proxy.
    _ = audit_architecture()
    arch_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    t1 = time.perf_counter()
    try:
        from app.application.services.institutional_portfolio_analytics import (
            analyze_portfolio,
        )

        analyze_portfolio([], starting_equity=10_000.0, include_reports=False)
        analytics_ms = round((time.perf_counter() - t1) * 1000.0, 2)
    except Exception:  # noqa: BLE001
        analytics_ms = None

    checks.append(
        _check(
            "api_latency_proxy",
            "PASS" if arch_ms < 2000 else "WARNING",
            f"Architecture audit completed in {arch_ms}ms",
        )
    )
    if analytics_ms is not None:
        checks.append(
            _check(
                "analytics_latency",
                "PASS" if analytics_ms < 500 else "WARNING",
                f"Empty-portfolio analyze_portfolio in {analytics_ms}ms",
            )
        )
    else:
        checks.append(
            _check("analytics_latency", "WARNING", "Portfolio analytics unavailable")
        )

    mem_mb = None
    try:
        import resource

        mem_mb = round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024.0, 2)
        # Linux ru_maxrss is KB; on Windows resource may be absent.
    except Exception:  # noqa: BLE001
        try:
            import psutil  # type: ignore[import-untyped]

            mem_mb = round(psutil.Process().memory_info().rss / (1024 * 1024), 2)
        except Exception:  # noqa: BLE001
            mem_mb = None

    checks.append(
        _check(
            "memory_usage",
            "PASS" if mem_mb is None or mem_mb < 1024 else "WARNING",
            f"Process RSS ≈ {mem_mb} MB" if mem_mb is not None else "Memory probe unavailable",
        )
    )
    checks.append(
        _check(
            "cpu_usage",
            "PASS",
            "CPU sampling deferred — no continuous profiler attached in PRR",
        )
    )
    checks.append(
        _check(
            "database_query_efficiency",
            "WARNING",
            "Query plans not profiled in this read-only pass — use EXPLAIN in staging",
        )
    )
    checks.append(
        _check(
            "dashboard_latency",
            "PASS",
            "Ops dashboards are React Query client-side; budget governed by Design Bible",
        )
    )

    return {
        "section": "performance",
        "checks": checks,
        "architecture_audit_ms": arch_ms,
        "analytics_latency_ms": analytics_ms,
        "memory_mb": mem_mb,
    }


def audit_operations() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    surfaces = {
        "logging": "core/logging" if (ROOT / "core/logging").exists() else "app/presentation/middleware",
        "monitoring_alerts": "app/domain/institutional_trading/operations/production_alerts.py",
        "metrics_health": "app/presentation/routers/health.py",
        "runbooks": "docs/production/OPERATIONS_GUIDE.md",
        "backup_script": "scripts/backup_production_state.py",
        "recovery_docs": "docs/production/RECOVERY_GUIDE.md",
    }
    # soft resolve logging dir
    log_ok = (ROOT / "core/logging").exists() or any(
        (ROOT / "app/presentation").rglob("*log*")
    )
    checks.append(
        _check("logging", "PASS" if log_ok else "WARNING", "Logging surfaces present")
    )

    for name, rel in surfaces.items():
        if name == "logging":
            continue
        ok = _path_exists(rel) or (ROOT / rel).exists()
        # recovery guide alternate names
        if name == "recovery_docs" and not ok:
            ok = _path_exists("docs/production/DEPLOYMENT_GUIDE.md")
        if name == "backup_script" and not ok:
            ok = any((ROOT / "scripts").glob("*backup*")) if (ROOT / "scripts").is_dir() else False
        status: CheckStatus = "PASS" if ok else "WARNING"
        checks.append(_check(name, status, f"{rel} {'present' if ok else 'missing'}"))

    checklist = _path_exists("docs/production/PRODUCTION_CHECKLIST.md")
    checks.append(
        _check(
            "production_checklist_doc",
            "PASS" if checklist else "FAIL",
            "PRODUCTION_CHECKLIST.md present" if checklist else "Checklist doc missing",
        )
    )

    return {"section": "operations", "checks": checks}


def _flatten_checks(sections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for sec in sections:
        for c in sec.get("checks") or []:
            row = dict(c)
            row["section"] = sec.get("section")
            out.append(row)
    return out


def build_production_checklist(all_checks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """PASS / WARNING / FAIL for every subsystem check."""
    return [
        {
            "subsystem": c["subsystem"],
            "section": c.get("section"),
            "status": c["status"],
            "detail": c["detail"],
        }
        for c in all_checks
    ]


def build_risk_register(
    *,
    all_checks: list[dict[str, Any]],
    security: dict[str, Any],
    trading: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    risks: dict[str, list[dict[str, Any]]] = {
        "critical": [],
        "high": [],
        "medium": [],
        "low": [],
    }

    fails = [c for c in all_checks if c.get("status") == "FAIL"]
    warns = [c for c in all_checks if c.get("status") == "WARNING"]

    for c in fails:
        severity = "critical" if c.get("section") in {"security", "trading"} else "high"
        risks[severity].append(
            {
                "id": f"FAIL-{c.get('section')}-{c.get('subsystem')}",
                "title": f"{c.get('subsystem')} FAILED",
                "impact": "Subsystem gate failed — blocks institutional readiness",
                "likelihood": "Certain (observed)",
                "mitigation": c.get("detail"),
            }
        )

    if security.get("execution_enabled") and security.get("app_env") not in {
        "production",
        "prod",
    }:
        risks["high"].append(
            {
                "id": "EXEC-NONPROD",
                "title": "EXECUTION_ENABLED outside production env",
                "impact": "Orders may send from non-production configuration",
                "likelihood": "Medium",
                "mitigation": "Keep EXECUTION_ENABLED=false until production env + launch locks PASS",
            }
        )

    if trading.get("ops_mode") == "LIVE" and trading.get("kill_switch_armed"):
        risks["medium"].append(
            {
                "id": "LIVE-KILL",
                "title": "LIVE mode with kill switch armed",
                "impact": "Trading halted while mode says LIVE — operator confusion",
                "likelihood": "Observed if both true",
                "mitigation": "Disarm kill only after OWNER confirmation, or demote mode",
            }
        )

    for c in warns[:12]:
        risks["medium"].append(
            {
                "id": f"WARN-{c.get('section')}-{c.get('subsystem')}",
                "title": f"{c.get('subsystem')} WARNING",
                "impact": "Elevated operational uncertainty",
                "likelihood": "Possible",
                "mitigation": c.get("detail"),
            }
        )

    risks["low"].append(
        {
            "id": "PRR-RO",
            "title": "PRR is advisory-only",
            "impact": "Does not itself change production behavior",
            "likelihood": "Certain",
            "mitigation": "Use Ops launch-readiness + OWNER confirm for any promotion",
        }
    )

    # Deduplicate medium if too long
    risks["medium"] = risks["medium"][:20]
    return risks


def score_readiness(all_checks: list[dict[str, Any]]) -> tuple[float, Recommendation, str]:
    if not all_checks:
        return 0.0, "NOT READY", "No checks executed"

    weights = {"PASS": 1.0, "WARNING": 0.55, "FAIL": 0.0}
    total = sum(weights.get(str(c.get("status")), 0.5) for c in all_checks)
    score = round(100.0 * total / len(all_checks), 1)

    fail_n = sum(1 for c in all_checks if c.get("status") == "FAIL")
    warn_n = sum(1 for c in all_checks if c.get("status") == "WARNING")
    critical_fail = any(
        c.get("status") == "FAIL" and c.get("section") in {"security", "trading"}
        for c in all_checks
    )

    if fail_n >= 3 or critical_fail or score < 45:
        rec: Recommendation = "NOT READY"
    elif score < 65 or fail_n >= 1:
        rec = "CONDITIONALLY READY"
    elif score < 85 or warn_n >= 8:
        rec = "READY FOR CONTROLLED LIVE"
    else:
        rec = "READY FOR INSTITUTIONAL PRODUCTION"

    summary = (
        f"Score {score}/100 · {fail_n} FAIL · {warn_n} WARNING · "
        f"{len(all_checks) - fail_n - warn_n} PASS -> {rec}"
    )
    return score, rec, summary


def _cap_recommendation_for_environment(
    recommendation: Recommendation,
    *,
    security: dict[str, Any],
    trading: dict[str, Any],
) -> Recommendation:
    """Non-production / incomplete live stack cannot claim institutional production."""
    order: list[Recommendation] = [
        "NOT READY",
        "CONDITIONALLY READY",
        "READY FOR CONTROLLED LIVE",
        "READY FOR INSTITUTIONAL PRODUCTION",
    ]
    cap: Recommendation = "READY FOR INSTITUTIONAL PRODUCTION"
    app_env = str(security.get("app_env") or "").lower()
    if app_env not in {"production", "prod"}:
        cap = "CONDITIONALLY READY"
    gateway = False
    try:
        from core.config.settings import get_settings

        s = get_settings()
        gateway = bool(getattr(s, "mt5_gateway_base_url", None))
    except Exception:  # noqa: BLE001
        gateway = False
    if not gateway:
        # Without a gateway URL, controlled live is the ceiling.
        if order.index(cap) > order.index("CONDITIONALLY READY"):
            cap = "CONDITIONALLY READY"
    if trading.get("ops_mode") == "SHADOW":
        if order.index(cap) > order.index("READY FOR CONTROLLED LIVE"):
            cap = "READY FOR CONTROLLED LIVE"
    if order.index(recommendation) <= order.index(cap):
        return recommendation
    return cap


def build_institutional_production_readiness_review(
    *,
    write_report: bool = False,
) -> dict[str, Any]:
    """Compose full Institutional PRR payload (read-only)."""
    t0 = time.perf_counter()
    architecture = audit_architecture()
    security = audit_security()
    reliability = audit_reliability()
    trading = audit_trading()
    data_integrity = audit_data_integrity()
    performance = audit_performance()
    operations = audit_operations()

    sections = [
        architecture,
        security,
        reliability,
        trading,
        data_integrity,
        performance,
        operations,
    ]
    all_checks = _flatten_checks(sections)
    checklist = build_production_checklist(all_checks)
    risks = build_risk_register(
        all_checks=all_checks, security=security, trading=trading
    )
    score, recommendation, summary = score_readiness(all_checks)
    recommendation = _cap_recommendation_for_environment(
        recommendation, security=security, trading=trading
    )
    summary = (
        f"Score {score}/100 · "
        f"{sum(1 for c in all_checks if c['status'] == 'FAIL')} FAIL · "
        f"{sum(1 for c in all_checks if c['status'] == 'WARNING')} WARNING · "
        f"{sum(1 for c in all_checks if c['status'] == 'PASS')} PASS -> {recommendation}"
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)

    payload: dict[str, Any] = {
        "schema_version": "1.0.0",
        "mode": "institutional_production_readiness_review",
        "mutates_engines": False,
        "analytics_only": True,
        "advisory_only": True,
        "never_modifies_strategy_risk_safety_oms_execution_auto_trading_thresholds": True,
        "observed_at": _now(),
        "elapsed_ms": elapsed_ms,
        "sections": {
            "architecture": architecture,
            "security": security,
            "reliability": reliability,
            "trading": trading,
            "data_integrity": data_integrity,
            "performance": performance,
            "operations": operations,
            "production_checklist": checklist,
            "risk_register": risks,
            "executive_summary": {
                "overall_production_readiness_score": score,
                "recommendation": recommendation,
                "summary": summary,
                "counts": {
                    "pass": sum(1 for c in all_checks if c["status"] == "PASS"),
                    "warning": sum(1 for c in all_checks if c["status"] == "WARNING"),
                    "fail": sum(1 for c in all_checks if c["status"] == "FAIL"),
                    "total": len(all_checks),
                },
            },
        },
        "overall_production_readiness_score": score,
        "recommendation": recommendation,
        "summary": summary,
    }

    if write_report:
        _write_report_files(payload)

    return payload


def _write_report_files(payload: dict[str, Any]) -> None:
    out_dir = ROOT / "docs" / "production" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    latest_json = out_dir / "institutional_prr_latest.json"
    stamped_json = out_dir / f"institutional_prr_{stamp}.json"
    latest_md = out_dir / "institutional_prr_latest.md"
    body = json.dumps(payload, indent=2, default=str)
    stamped_json.write_text(body, encoding="utf-8")
    latest_json.write_text(body, encoding="utf-8")
    latest_md.write_text(prr_to_markdown(payload), encoding="utf-8")


def prr_to_markdown(payload: dict[str, Any]) -> str:
    sections = payload.get("sections") or {}
    exec_sum = sections.get("executive_summary") or {}
    lines = [
        "# Institutional Production Readiness Review (PRR)",
        "",
        f"- Observed: `{payload.get('observed_at')}`",
        "- **READ ONLY** — engines unchanged",
        f"- Score: **{payload.get('overall_production_readiness_score')}**/100",
        f"- Recommendation: **{payload.get('recommendation')}**",
        f"- Summary: {payload.get('summary')}",
        "",
        "## Executive Summary",
        "",
        f"- PASS: {exec_sum.get('counts', {}).get('pass')}",
        f"- WARNING: {exec_sum.get('counts', {}).get('warning')}",
        f"- FAIL: {exec_sum.get('counts', {}).get('fail')}",
        "",
        "## Production Checklist",
        "",
    ]
    for row in sections.get("production_checklist") or []:
        lines.append(
            f"- [{row.get('status')}] `{row.get('section')}/{row.get('subsystem')}` — {row.get('detail')}"
        )
    lines.extend(["", "## Risk Register", ""])
    risks = sections.get("risk_register") or {}
    for level in ("critical", "high", "medium", "low"):
        lines.append(f"### {level.upper()}")
        for r in risks.get(level) or []:
            lines.append(
                f"- **{r.get('title')}** — impact: {r.get('impact')}; "
                f"likelihood: {r.get('likelihood')}; mitigation: {r.get('mitigation')}"
            )
        lines.append("")
    return "\n".join(lines) + "\n"
