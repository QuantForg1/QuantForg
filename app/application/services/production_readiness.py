"""Application service — QuantForg Production Readiness Program."""

from __future__ import annotations

from typing import Any

from app.domain.institutional_trading.certification.platform import (
    get_certification_platform,
)
from app.domain.institutional_trading.operations.control_plane import get_control_plane
from app.domain.institutional_trading.reliability.platform import (
    get_reliability_platform,
)
from app.domain.production_readiness import (
    ProductionReadinessCenter,
    ReadinessFeeds,
)
from app.domain.production_readiness.config import (
    DEFAULT_PR_CONFIG,
    ProductionReadinessConfig,
)


class ProductionReadinessService:
    """Readiness facade — compose ITE; never mutate execution architecture."""

    def __init__(self, config: ProductionReadinessConfig | None = None) -> None:
        self._center = ProductionReadinessCenter(config or DEFAULT_PR_CONFIG)

    def status(self) -> dict[str, object]:
        return self._center.status()

    def policies(self) -> dict[str, Any]:
        return self._center.policies.to_dict()

    def update_policies(
        self, updates: dict[str, Any], *, operator: str = "operator"
    ) -> dict[str, Any]:
        payload = dict(updates)
        payload["operator"] = operator
        return self._center.update_policies(payload)

    def audit(self, *, limit: int = 50) -> dict[str, Any]:
        return self._center.list_audit(limit=limit)

    def log_recovery(
        self,
        *,
        action: str,
        ok: bool,
        detail: str,
        operator: str = "system",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._center.log_recovery(
            action=action, ok=ok, detail=detail, operator=operator, meta=meta
        )

    def log_failure(
        self,
        *,
        action: str,
        detail: str,
        operator: str = "system",
        meta: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self._center.log_failure(
            action=action, detail=detail, operator=operator, meta=meta
        )

    def dashboard(
        self,
        *,
        pre_trade_facts: dict[str, Any] | None = None,
        post_trade_rows: list[dict[str, Any]] | None = None,
        security: dict[str, Any] | None = None,
        shadow_readiness: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        feeds = self._collect_feeds(
            pre_trade_facts=pre_trade_facts,
            post_trade_rows=post_trade_rows,
            security=security,
            shadow_readiness=shadow_readiness,
        )
        return self._center.build_dashboard(feeds)

    def _collect_feeds(
        self,
        *,
        pre_trade_facts: dict[str, Any] | None,
        post_trade_rows: list[dict[str, Any]] | None,
        security: dict[str, Any] | None,
        shadow_readiness: dict[str, Any] | None,
    ) -> ReadinessFeeds:
        plane = get_control_plane()
        reliability = get_reliability_platform()
        try:
            control_center = plane.control_center()
        except Exception:
            control_center = None
        try:
            readiness = plane.readiness_dashboard()
        except Exception:
            readiness = None
        try:
            rel_dash = reliability.operational_dashboard()
        except Exception:
            rel_dash = None
        try:
            incidents = [
                i.to_dict()
                for i in reliability.incidents.list(limit=30)
                if i.status.value != "RESOLVED"
            ]
        except Exception:
            incidents = None
        try:
            recovery_events = [
                e.to_dict() for e in reliability.recovery.list(limit=30)
            ]
        except Exception:
            recovery_events = None
        try:
            runbooks = plane.runbooks.list()
        except Exception:
            runbooks = None
        try:
            ops_audit = [a.to_dict() for a in plane.audit.list(limit=30)]
        except Exception:
            ops_audit = None
        try:
            timeline = [
                e.to_dict() for e in reliability.timeline.search(limit=30)
            ]
        except Exception:
            timeline = None

        certification: dict[str, Any] | None
        go_nogo: dict[str, Any] | None
        try:
            cert = get_certification_platform()
            certification = cert.dashboard_payload()
            go_nogo = {"status": certification.get("go_nogo")}
        except Exception:
            certification = None
            go_nogo = None

        return ReadinessFeeds(
            control_center=control_center,
            readiness=readiness,
            reliability=rel_dash,
            incidents=incidents,
            recovery_events=recovery_events,
            runbooks=runbooks,
            ops_audit=ops_audit,
            certification=certification,
            go_nogo=go_nogo,
            shadow_readiness=shadow_readiness,
            pre_trade_facts=pre_trade_facts,
            post_trade_rows=post_trade_rows,
            security=security,
            timeline=timeline,
        )
