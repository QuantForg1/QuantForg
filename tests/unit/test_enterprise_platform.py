"""Enterprise Platform — additive SaaS; never touches trading/auth/COP logic."""

from __future__ import annotations

import pytest

from app.domain.enterprise_platform.api_keys import (
    create_api_key,
    disable_api_key,
    list_api_keys,
    rotate_api_key,
    verify_api_key,
)
from app.domain.enterprise_platform.persistence import redact
from app.domain.enterprise_platform.rbac import (
    check_permission,
    normalize_enterprise_role,
    permission_matrix_table,
    require_permission,
)
from app.domain.enterprise_platform.organizations import isolation_scope


def test_redact_secrets() -> None:
    out = redact({"token": "x", "ok": 1})
    assert out["token"] == "[REDACTED]"
    assert out["ok"] == 1


def test_rbac_matrix_and_checks() -> None:
    assert normalize_enterprise_role("member") == "trader"
    assert normalize_enterprise_role("viewer") == "read_only"
    assert check_permission("owner", "api_keys.manage") is True
    assert check_permission("trader", "api_keys.manage") is False
    assert check_permission("read_only", "dashboard.view") is True
    denied = require_permission("trader", "admin.console")
    assert denied["denied"] is True
    matrix = permission_matrix_table()
    assert matrix["replaces_auth"] is False
    assert "owner" in matrix["roles"]
    assert "risk_manager" in matrix["roles"]


def test_api_key_lifecycle_never_persists_plaintext() -> None:
    created = create_api_key(
        organization_id="org_test",
        name="unit",
        scopes=["read:dashboard"],
        operator="admin@quantforg.com",
        expires_days=30,
    )
    assert created.get("plaintext")
    assert created.get("secret_exposed_once") is True
    key_id = created["id"]
    listed = list_api_keys(organization_id="org_test")
    for row in listed["keys"]:
        assert row.get("plaintext") is None
        assert "key_hash" not in row
    assert verify_api_key(created["plaintext"]) is not None
    rotated = rotate_api_key(key_id=key_id, operator="admin@quantforg.com")
    assert rotated.get("ok") is True
    assert rotated.get("plaintext")
    # old secret invalid
    assert verify_api_key(created["plaintext"]) is None
    disabled = disable_api_key(key_id=key_id, operator="admin@quantforg.com")
    assert disabled.get("ok") is True


def test_isolation_namespaces() -> None:
    scope = isolation_scope("abc-123")
    assert scope["data_leakage_forbidden"] is True
    assert "org:abc-123:trades" in scope["namespaces"]["trades"]


@pytest.mark.asyncio
async def test_enterprise_platform_flags() -> None:
    from app.application.services.enterprise_platform import (
        build_enterprise_platform,
    )

    pack = await build_enterprise_platform()
    flags = pack["flags"]
    assert flags["modifies_trading"] is False
    assert flags["modifies_ai"] is False
    assert flags["modifies_oms"] is False
    assert flags["modifies_mt5"] is False
    assert flags["modifies_risk"] is False
    assert flags["modifies_cop"] is False
    assert flags["modifies_auth"] is False
    assert flags["modifies_pricing"] is False
    assert flags["additive_only"] is True
    assert pack["fabricated"] is False
    assert "rbac" in pack
    assert "dashboard" in pack
    assert "security_center" in pack
    assert "compliance" in pack
