"""QCS platform — institutional certification gate, never mutates production."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.quantforg_certification_suite.analytics import (
    build_blockers,
    build_checks,
    build_domain_readiness,
    build_evidence_explorer,
    build_reports,
    build_scores,
    certification_consistency_check,
    infer_certification_level,
)
from app.domain.quantforg_certification_suite.gather import gather_certification_sources
from app.domain.quantforg_certification_suite.models import (
    CERTIFICATION_DOMAINS,
    ISOLATION_FLAGS,
)
from app.domain.quantforg_certification_suite.store import QcsStore


class QuantForgCertificationSuite:
    def __init__(self, store: QcsStore | None = None) -> None:
        self.store = store or QcsStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_certification_sources()
        checks = build_checks(ctx)
        scores = build_scores(ctx, checks)
        blockers = build_blockers(ctx, checks, scores)
        level = infer_certification_level(scores, checks, blockers)
        domains = build_domain_readiness(checks, scores)
        evidence = build_evidence_explorer(ctx)
        reports = build_reports(
            scores=scores,
            level=level,
            checks=checks,
            blockers=blockers,
            domains=domains,
            evidence=evidence,
            ctx=ctx,
        )
        consistency = certification_consistency_check(
            scores=scores, level=level, blockers=blockers, evidence=evidence
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "quantforg_certification_suite",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
                "domains": list(CERTIFICATION_DOMAINS),
            },
            "checks": checks,
            "scores": scores,
            "level": level,
            "blockers": blockers,
            "domains": domains,
            "evidence": evidence,
            "reports": reports,
            "certification_consistency": consistency,
            "read_only": True,
            "never_executes_trades": True,
            "never_modifies_production": True,
            "never_modifies_strategies": True,
            "never_modifies_risk": True,
            "never_modifies_safety": True,
            "never_approves_releases_automatically": True,
            "human_approval_required_for_certification": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in (
                "certification_report",
                "release_certification",
                "strategy_certification",
                "platform_certification",
                "executive_readiness_report",
            ):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"qcs-{key}-{datetime.now(UTC).date()}",
                            "kind": key,
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "certification_dashboard": {
                "level": pack["level"],
                "scores": pack["scores"],
                "blockers": pack["blockers"][:12],
            },
            "readiness_center": {
                "level": pack["level"],
                "domains": pack["domains"],
                "scores": pack["scores"],
            },
            "evidence_explorer": pack["evidence"],
            "certification_timeline": self.store.list_timeline(limit=40),
            "blocker_center": pack["blockers"],
            "reports": self.store.list_reports(limit=20),
        }
        return pack
