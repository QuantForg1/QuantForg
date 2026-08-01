"""Enterprise RBAC — additive permission matrix. Does not replace auth."""

from __future__ import annotations

from typing import Any

# Enterprise roles (overlay). Maps to existing org roles where applicable.
ENTERPRISE_ROLES = (
    "owner",
    "admin",
    "trader",
    "risk_manager",
    "support",
    "read_only",
)

# capability -> roles allowed
PERMISSION_MATRIX: dict[str, frozenset[str]] = {
    "org.manage": frozenset({"owner", "admin"}),
    "org.invite": frozenset({"owner", "admin"}),
    "org.view": frozenset(ENTERPRISE_ROLES),
    "members.manage": frozenset({"owner", "admin"}),
    "rbac.view": frozenset({"owner", "admin", "risk_manager", "support", "read_only"}),
    "api_keys.manage": frozenset({"owner", "admin"}),
    "api_keys.view": frozenset({"owner", "admin", "support"}),
    "audit.view": frozenset({"owner", "admin", "risk_manager", "support", "read_only"}),
    "audit.export": frozenset({"owner", "admin", "risk_manager"}),
    "security.view": frozenset({"owner", "admin", "support", "risk_manager"}),
    "security.manage": frozenset({"owner", "admin"}),
    "reports.view": frozenset(
        {"owner", "admin", "risk_manager", "support", "read_only"}
    ),
    "reports.compliance": frozenset({"owner", "admin", "risk_manager"}),
    "admin.console": frozenset({"owner", "admin"}),
    "compliance.export": frozenset({"owner", "admin"}),
    "dashboard.view": frozenset(ENTERPRISE_ROLES),
    "trading.view": frozenset(
        {"owner", "admin", "trader", "risk_manager", "read_only"}
    ),
    "support.manage": frozenset({"owner", "admin", "support"}),
}


def normalize_enterprise_role(role: str | None) -> str:
    r = str(role or "read_only").strip().lower()
    # Map existing org membership roles
    if r == "member":
        return "trader"
    if r == "viewer":
        return "read_only"
    if r in ENTERPRISE_ROLES:
        return r
    # Platform UserRole support → support
    if r == "support":
        return "support"
    return "read_only"


def check_permission(role: str | None, capability: str) -> bool:
    allowed = PERMISSION_MATRIX.get(capability)
    if allowed is None:
        return False
    return normalize_enterprise_role(role) in allowed


def require_permission(role: str | None, capability: str) -> dict[str, Any]:
    ok = check_permission(role, capability)
    return {
        "allowed": ok,
        "role": normalize_enterprise_role(role),
        "capability": capability,
        "denied": not ok,
    }


def permission_matrix_table() -> dict[str, Any]:
    rows = []
    for capability, roles in sorted(PERMISSION_MATRIX.items()):
        rows.append(
            {
                "capability": capability,
                **{r: ("Yes" if r in roles else "—") for r in ENTERPRISE_ROLES},
            }
        )
    return {
        "roles": list(ENTERPRISE_ROLES),
        "rows": rows,
        "additive_only": True,
        "replaces_auth": False,
        "fabricated": False,
    }
