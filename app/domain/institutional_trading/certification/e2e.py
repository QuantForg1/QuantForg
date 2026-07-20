"""End-to-end certification — validate full institutional pipeline (no trading)."""

from __future__ import annotations

from app.domain.institutional_trading.certification.models import (
    CERTIFICATION_PIPELINE,
    CertificationEvidence,
    StageCheck,
)


class EndToEndCertifier:
    """Validate Decision → … → Reliability without sending orders."""

    def validate(self, evidence: CertificationEvidence) -> list[StageCheck]:
        checks: list[StageCheck] = []
        for stage in CERTIFICATION_PIPELINE:
            key = stage.value
            ok = evidence.stage_ok.get(key, False)
            lat = float(evidence.stage_latency_ms.get(key, 0.0))
            detail = "ok" if ok else f"stage '{key}' not certified"
            # Soft latency budget for certification (measurement, not gate alone)
            if ok and lat > 5_000:
                ok = False
                detail = f"stage '{key}' latency {lat}ms exceeds 5000ms budget"
            checks.append(
                StageCheck(stage=stage, passed=ok, detail=detail, latency_ms=lat)
            )
        return checks

    def all_passed(self, evidence: CertificationEvidence) -> bool:
        return all(c.passed for c in self.validate(evidence))
