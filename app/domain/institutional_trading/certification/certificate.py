"""Production certificate issuer."""

from __future__ import annotations

from datetime import UTC, datetime

from app.domain.institutional_trading.certification.models import (
    CertificationEvidence,
    GoNoGoStatus,
    ProductionCertificate,
)


DEFAULT_LIMITATIONS: tuple[str, ...] = (
    "Live MT5 canary under AutoTrading is operator-gated",
    "In-memory certification store must be flushed to SQL for durability",
    "No AI on hot path (by design)",
    "OMS is not modified by Phase H — certification is measurement-only",
)


class CertificateIssuer:
    def issue(
        self,
        *,
        evidence: CertificationEvidence,
        go_nogo: GoNoGoStatus,
        passed_tests: list[str],
        operator_approval: str | None = None,
        now: datetime | None = None,
    ) -> ProductionCertificate:
        return ProductionCertificate(
            version=evidence.engine_version,
            git_commit=evidence.git_commit,
            strategy_version=evidence.strategy_version,
            config_version=evidence.config_version,
            promotion_status=go_nogo.value,
            passed_tests=list(passed_tests),
            known_limitations=list(
                evidence.known_limitations or DEFAULT_LIMITATIONS
            ),
            operator_approval=operator_approval,
            timestamp=now or datetime.now(UTC),
            go_nogo=go_nogo,
        )
