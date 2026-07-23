"""Warehouse health / coverage / quality / correlation reports."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.domain.institutional_data_warehouse.analytics import run_analytics
from app.domain.institutional_data_warehouse.models import DATA_DOMAINS, HARD_LOCKS
from app.domain.institutional_data_warehouse.store import InstitutionalDataWarehouse


def _quality_flags(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if not row.get("timestamp"):
        flags.append("missing_timestamp")
    if not row.get("correlation_id"):
        flags.append("missing_correlation_id")
    if not row.get("strategy_version"):
        flags.append("missing_strategy_version")
    if not row.get("risk_version"):
        flags.append("missing_risk_version")
    if not row.get("safety_version"):
        flags.append("missing_safety_version")
    if not row.get("execution_version"):
        flags.append("missing_execution_version")
    return flags


def build_health_report(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    inv = wh.inventory()
    empty = [d for d, n in (inv.get("domains") or {}).items() if int(n) == 0]
    return {
        "report": "warehouse_health",
        "status": "available",
        "total_records": inv.get("total_records"),
        "domains": inv.get("domains"),
        "empty_domains": empty,
        "ingest_batches": inv.get("ingest_batches"),
        "healthy": int(inv.get("total_records") or 0) > 0,
        "read_only": True,
    }


def build_coverage_report(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    counts = wh.counts()
    required = {
        "trades": 50,
        "replay": 500,
        "evidence": 100,
        "governance": 10,
        "market": 100,
    }
    coverage = {
        d: {
            "observed": counts.get(d, 0),
            "target": required.get(d),
            "ratio": (
                round(min(1.0, counts.get(d, 0) / tgt), 4)
                if (tgt := required.get(d))
                else None
            ),
        }
        for d in DATA_DOMAINS
    }
    return {
        "report": "data_coverage",
        "status": "available",
        "coverage": coverage,
        "read_only": True,
    }


def build_quality_report(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    flag_counts: dict[str, int] = defaultdict(int)
    scanned = 0
    complete = 0
    for domain in DATA_DOMAINS:
        for row in wh.list(domain, limit=5_000):  # type: ignore[arg-type]
            scanned += 1
            flags = _quality_flags(row)
            if not flags:
                complete += 1
            for f in flags:
                flag_counts[f] += 1
    return {
        "report": "data_quality",
        "status": "available",
        "records_scanned": scanned,
        "fully_keyed_records": complete,
        "completeness_ratio": (
            round(complete / scanned, 4) if scanned else None
        ),
        "flag_histogram": dict(flag_counts),
        "read_only": True,
        "note": "Missing fields stay null — never fabricated",
    }


def build_correlation_report(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    by_corr: dict[str, list[str]] = defaultdict(list)
    linked = 0
    for domain in DATA_DOMAINS:
        for row in wh.list(domain, limit=5_000):  # type: ignore[arg-type]
            cid = row.get("correlation_id")
            if not cid:
                continue
            linked += 1
            by_corr[str(cid)].append(str(domain))
    multi = {k: sorted(set(v)) for k, v in by_corr.items() if len(set(v)) > 1}
    return {
        "report": "correlation",
        "status": "available",
        "records_with_correlation_id": linked,
        "unique_correlation_ids": len(by_corr),
        "cross_domain_correlations": len(multi),
        "examples": dict(list(multi.items())[:20]),
        "read_only": True,
    }


def build_recommendations(
    *,
    health: dict[str, Any],
    coverage: dict[str, Any],
    quality: dict[str, Any],
) -> list[str]:
    recs: list[str] = []
    if not health.get("healthy"):
        recs.append("Ingest operational snapshots into the warehouse")
    for d in health.get("empty_domains") or []:
        recs.append(f"Populate empty warehouse domain: {d}")
    cov = coverage.get("coverage") or {}
    for domain, meta in cov.items():
        if not isinstance(meta, dict):
            continue
        target = meta.get("target")
        ratio = meta.get("ratio")
        if target and ratio is not None and ratio < 1.0:
            recs.append(
                f"Grow {domain} coverage "
                f"({meta.get('observed')}/{target})"
            )
    completeness = quality.get("completeness_ratio")
    if completeness is not None and completeness < 0.8:
        recs.append(
            "Improve version/correlation key completeness on ingested rows"
        )
    recs.append(
        "Warehouse is read-only — never modify production trading systems"
    )
    return recs


def build_warehouse_pack(wh: InstitutionalDataWarehouse) -> dict[str, Any]:
    from app.domain.institutional_data_warehouse.dimensional import build_dimensional_model
    from app.domain.institutional_data_warehouse.quality_monitor import (
        run_data_quality_monitor,
    )
    from app.domain.institutional_data_warehouse.retention import retention_status

    health = build_health_report(wh)
    coverage = build_coverage_report(wh)
    quality = build_quality_report(wh)
    correlation = build_correlation_report(wh)
    analytics = run_analytics(wh)
    recommendations = build_recommendations(
        health=health, coverage=coverage, quality=quality
    )
    dq = run_data_quality_monitor(wh)
    retention = retention_status(wh)
    dimensional = build_dimensional_model(wh)
    return {
        "version": "1.1.0",
        "status": "available",
        "read_only": True,
        "analytics_infrastructure_only": True,
        "hard_locks": HARD_LOCKS,
        "inventory": wh.inventory(),
        "storage": wh.storage_stats(),
        "growth": {
            "ingest_batches": wh.inventory().get("ingest_batches"),
            "event_flow": wh.event_flow(limit=30),
            "total_records": wh.inventory().get("total_records"),
        },
        "event_flow": wh.event_flow(limit=40),
        "data_quality_monitor": dq,
        "retention": retention,
        "dimensional_model": dimensional,
        "analytics": analytics,
        "reports": {
            "warehouse_health_report": health,
            "data_coverage_report": coverage,
            "data_quality_report": quality,
            "correlation_report": correlation,
            "data_quality_monitor": dq,
            "retention_policy": retention,
        },
        "recommendations": recommendations,
        "evidence_summary": {
            "total_records": wh.inventory().get("total_records"),
            "domains_populated": sum(
                1 for n in wh.counts().values() if n > 0
            ),
            "domains_total": len(DATA_DOMAINS),
            "completeness_ratio": quality.get("completeness_ratio"),
            "integrity_score": dq.get("integrity_score"),
            "cross_domain_correlations": correlation.get(
                "cross_domain_correlations"
            ),
            "read_only": True,
        },
    }
