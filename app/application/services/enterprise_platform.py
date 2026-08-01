"""Enterprise Platform facade."""

from __future__ import annotations

from typing import Any

from app.domain.enterprise_platform.admin_console import build_enterprise_dashboard
from app.domain.enterprise_platform.api_keys import list_api_keys
from app.domain.enterprise_platform.audit_center import build_audit_center
from app.domain.enterprise_platform.compliance import build_compliance_center
from app.domain.enterprise_platform.organizations import build_organizations_center
from app.domain.enterprise_platform.persistence import utc_iso
from app.domain.enterprise_platform.rbac import permission_matrix_table
from app.domain.enterprise_platform.reporting import build_enterprise_reports
from app.domain.enterprise_platform.security_center import build_security_center
from app.domain.enterprise_platform.system_admin import build_admin_console


async def build_enterprise_platform(
    *, organization_id: str | None = None
) -> dict[str, Any]:
    dashboard = await build_enterprise_dashboard()
    orgs = await build_organizations_center()
    security = await build_security_center()
    audit = await build_audit_center(organization_id=organization_id, limit=100)
    reports = await build_enterprise_reports(organization_id=organization_id)
    compliance = await build_compliance_center()
    admin = await build_admin_console()
    keys = list_api_keys(organization_id=organization_id)
    return {
        "as_of": utc_iso(),
        "dashboard": dashboard,
        "organizations": orgs,
        "rbac": permission_matrix_table(),
        "api_keys": keys,
        "audit_center": audit,
        "security_center": security,
        "reports": reports,
        "compliance": compliance,
        "admin_console": admin,
        "flags": {
            "modifies_trading": False,
            "modifies_ai": False,
            "modifies_oms": False,
            "modifies_mt5": False,
            "modifies_risk": False,
            "modifies_cop": False,
            "modifies_auth": False,
            "modifies_pricing": False,
            "additive_only": True,
            "credentials_exposed": False,
            "enterprise_version": "v1.0.0",
        },
        "fabricated": False,
    }


async def build_enterprise_noc_panels() -> dict[str, Any]:
    dash = await build_enterprise_dashboard()
    orgs = await build_organizations_center()
    return {
        "enterprise_dashboard": {
            "metrics": dash.get("metrics") or {},
            "observe_only": True,
        },
        "organizations": {
            "count": orgs.get("count") or 0,
            "observe_only": True,
        },
        "flags": {
            "observe_only": True,
            "never_modifies_trading": True,
            "enterprise_version": "v1.0.0",
        },
        "fabricated": False,
    }
