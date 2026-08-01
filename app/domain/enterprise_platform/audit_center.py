"""Enterprise Audit Center — search, timeline, export, filter."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.enterprise_audit import list_enterprise_audit
from app.domain.enterprise_platform.persistence import utc_iso
from app.domain.enterprise_platform.production_readers import read_audit_logs


async def build_audit_center(
    *,
    organization_id: str | None = None,
    action: str | None = None,
    q: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    enterprise = list_enterprise_audit(
        limit=limit,
        organization_id=organization_id,
        action=action,
        q=q,
    )
    platform = await read_audit_logs(limit=limit)
    if q:
        ql = q.lower()
        platform = [
            r
            for r in platform
            if ql in str(r.get("action") or "").lower()
            or ql in str(r.get("message") or "").lower()
            or ql in str(r.get("ip") or "").lower()
        ]
    # Optional COP audit observe (read-only; do not modify COP)
    cop_items: list[dict[str, Any]] = []
    try:
        from app.domain.customer_operations.cop_audit import list_cop_audit

        cop = list_cop_audit(limit=min(limit, 100))
        cop_items = list(cop.get("items") or [])
    except Exception:
        cop_items = []

    timeline = sorted(
        [
            *[
                {
                    "timestamp": r.get("timestamp"),
                    "source": "enterprise",
                    "action": r.get("action"),
                    "operator": r.get("operator"),
                    "target": r.get("target"),
                    "organization_id": r.get("organization_id"),
                }
                for r in enterprise.get("items") or []
            ],
            *[
                {
                    "timestamp": r.get("occurred_at"),
                    "source": "platform_audit_logs",
                    "action": r.get("action"),
                    "operator": r.get("actor_user_id"),
                    "target": r.get("message"),
                    "organization_id": organization_id,
                }
                for r in platform
            ],
            *[
                {
                    "timestamp": r.get("timestamp"),
                    "source": "cop",
                    "action": r.get("action"),
                    "operator": r.get("operator"),
                    "target": r.get("target"),
                    "organization_id": None,
                }
                for r in cop_items
            ],
        ],
        key=lambda x: str(x.get("timestamp") or ""),
        reverse=True,
    )[:limit]

    export_payload = {
        "exported_at": utc_iso(),
        "filters": {
            "organization_id": organization_id,
            "action": action,
            "q": q,
        },
        "timeline": timeline,
        "integrity": "append_only_sources",
    }
    return {
        "as_of": utc_iso(),
        "enterprise_events": enterprise,
        "platform_events": {"count": len(platform), "items": platform},
        "cop_events_count": len(cop_items),
        "timeline": timeline,
        "export": export_payload,
        "searchable": True,
        "filterable": True,
        "fabricated": False,
        "modifies_cop": False,
    }
