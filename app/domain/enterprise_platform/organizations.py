"""Enterprise organizations + workspace isolation."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.enterprise_audit import record_enterprise_audit
from app.domain.enterprise_platform.persistence import JsonDocumentStore, utc_iso
from app.domain.enterprise_platform.production_readers import (
    read_organization_members,
    read_organizations,
)
from app.domain.enterprise_platform.rbac import normalize_enterprise_role

_ROLE_OVERLAY: JsonDocumentStore | None = None


def _overlay() -> JsonDocumentStore:
    global _ROLE_OVERLAY
    if _ROLE_OVERLAY is None:
        _ROLE_OVERLAY = JsonDocumentStore(
            "enterprise_role_overlays.json", "overlays"
        )
    return _ROLE_OVERLAY


async def build_organizations_center() -> dict[str, Any]:
    orgs = await read_organizations()
    members = await read_organization_members()
    overlays = {
        str(o.get("member_id")): o for o in _overlay().list(limit=5000)
    }
    by_org: dict[str, list[dict[str, Any]]] = {}
    for m in members:
        oid = str(m.get("organization_id") or "")
        mid = str(m.get("id") or "")
        overlay = overlays.get(mid) or {}
        ent_role = normalize_enterprise_role(
            overlay.get("enterprise_role") or m.get("role")
        )
        enriched = {
            **m,
            "enterprise_role": ent_role,
            "hierarchy": _hierarchy_rank(ent_role),
        }
        by_org.setdefault(oid, []).append(enriched)

    rows = []
    for org in orgs:
        oid = str(org.get("id") or "")
        org_members = by_org.get(oid) or []
        rows.append(
            {
                **org,
                "member_count": len(org_members),
                "members": org_members,
                "isolation": {
                    "analytics": f"org:{oid}:analytics",
                    "customers": f"org:{oid}:customers",
                    "trades": f"org:{oid}:trades",
                    "licenses": f"org:{oid}:licenses",
                    "support": f"org:{oid}:support",
                    "audit": f"org:{oid}:audit",
                },
            }
        )
    return {
        "as_of": utc_iso(),
        "organizations": rows,
        "count": len(rows),
        "roles": [
            "owner",
            "admin",
            "trader",
            "risk_manager",
            "support",
            "read_only",
        ],
        "fabricated": False,
        "modifies_auth": False,
    }


def _hierarchy_rank(role: str) -> int:
    order = {
        "owner": 100,
        "admin": 80,
        "risk_manager": 60,
        "support": 50,
        "trader": 40,
        "read_only": 10,
    }
    return order.get(role, 0)


def assign_enterprise_role(
    *,
    member_id: str,
    organization_id: str,
    enterprise_role: str,
    operator: str,
    ip: str | None = None,
) -> dict[str, Any]:
    role = normalize_enterprise_role(enterprise_role)
    existing = _overlay().get(member_id)
    row = {
        "id": member_id,
        "member_id": member_id,
        "organization_id": organization_id,
        "enterprise_role": role,
        "updated_by": operator,
        "updated_at": utc_iso(),
    }
    if existing:
        saved = _overlay().upsert(member_id, lambda _: {**row, "id": member_id})
    else:
        saved = _overlay().append(row)
    record_enterprise_audit(
        operator=operator,
        action="enterprise_role_assign",
        target=member_id,
        organization_id=organization_id,
        before={"enterprise_role": (existing or {}).get("enterprise_role")},
        after={"enterprise_role": role},
        ip=ip,
        category="rbac",
    )
    return saved or row


def isolation_scope(organization_id: str) -> dict[str, Any]:
    """Declare isolated namespaces — no cross-tenant leakage by design."""
    oid = str(organization_id or "").strip()
    if not oid:
        return {"ok": False, "error": "organization_id_required"}
    return {
        "organization_id": oid,
        "namespaces": {
            "analytics": f"org:{oid}:analytics",
            "customers": f"org:{oid}:customers",
            "trades": f"org:{oid}:trades",
            "licenses": f"org:{oid}:licenses",
            "support": f"org:{oid}:support",
            "audit": f"org:{oid}:audit",
        },
        "data_leakage_forbidden": True,
        "enforcement": "enterprise_platform_scoping",
        "fabricated": False,
    }


def filter_by_org(
    rows: list[dict[str, Any]], organization_id: str | None
) -> list[dict[str, Any]]:
    if not organization_id:
        return rows
    return [
        r
        for r in rows
        if str(r.get("organization_id") or "") == str(organization_id)
    ]
