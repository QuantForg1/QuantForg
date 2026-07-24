"""CVF platform orchestrator — continuous validation, evidence only."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from app.domain.continuous_validation_framework.analytics import (
    build_evidence_chains,
    build_executive_reports,
    build_parameter_stability,
    build_regime_validation,
    build_replay_vs_live,
    build_statistical_confidence,
    build_strategy_drift,
    build_validation_alerts,
)
from app.domain.continuous_validation_framework.gather import gather_validation_sources
from app.domain.continuous_validation_framework.models import ISOLATION_FLAGS
from app.domain.continuous_validation_framework.store import CvfStore


class ContinuousValidationFramework:
    def __init__(self, store: CvfStore | None = None) -> None:
        self.store = store or CvfStore()
        self.isolation = dict(ISOLATION_FLAGS)

    def run(self, *, persist: bool = True) -> dict[str, Any]:
        t0 = time.perf_counter()
        ctx = gather_validation_sources()
        replay_vs_live = build_replay_vs_live(ctx)
        drift = build_strategy_drift(ctx, replay_vs_live)
        regime_validation = build_regime_validation(ctx)
        parameter_stability = build_parameter_stability(ctx)
        confidence = build_statistical_confidence(
            ctx,
            replay_vs_live=replay_vs_live,
            drift=drift,
            parameter_stability=parameter_stability,
        )
        alerts = build_validation_alerts(
            ctx,
            drift=drift,
            regime_validation=regime_validation,
            confidence=confidence,
            replay_vs_live=replay_vs_live,
        )
        evidence_chains = build_evidence_chains(
            ctx,
            alerts=alerts,
            replay_vs_live=replay_vs_live,
            confidence=confidence,
        )
        reports = build_executive_reports(
            replay_vs_live=replay_vs_live,
            drift=drift,
            regime_validation=regime_validation,
            confidence=confidence,
            alerts=alerts,
            evidence_chains=evidence_chains,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 2)
        pack = {
            "schema_version": "1.0.0",
            "mode": "continuous_validation_framework",
            "isolation": self.isolation,
            "observed_at": datetime.now(UTC).isoformat(),
            "elapsed_ms": elapsed_ms,
            "context": {
                "availability": ctx.get("availability"),
                "source_count": ctx.get("source_count"),
            },
            "replay_vs_live": replay_vs_live,
            "drift": drift,
            "regime_validation": regime_validation,
            "parameter_stability": parameter_stability,
            "confidence": confidence,
            "alerts": alerts,
            "evidence_chains": evidence_chains,
            "reports": reports,
            "read_only": True,
            "never_modifies_production": True,
            "never_approves_promotions": True,
            "humans_remain_responsible": True,
        }
        if persist:
            self.store.save_snapshot(pack)
            for key in ("daily", "weekly", "monthly", "quarterly"):
                body = reports.get(key)
                if isinstance(body, dict):
                    self.store.save_report(
                        {
                            "report_id": f"cvf-{key}-{datetime.now(UTC).date()}",
                            "kind": "executive_validation",
                            **body,
                        }
                    )
        return pack

    def dashboard(self) -> dict[str, Any]:
        pack = self.run(persist=True)
        pack["sections"] = {
            "validation_dashboard": {
                "confidence": pack["confidence"],
                "alerts": pack["alerts"],
                "drift_count": (pack["drift"] or {}).get("drift_count"),
            },
            "drift_explorer": pack["drift"],
            "replay_vs_live": pack["replay_vs_live"],
            "confidence_explorer": pack["confidence"],
            "evidence_viewer": pack["evidence_chains"],
            "validation_reports": self.store.list_reports(limit=20),
            "regime_validation": pack["regime_validation"],
            "parameter_stability": pack["parameter_stability"],
        }
        return pack
