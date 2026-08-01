"""Enterprise API key management — hash stored; secret shown once."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from app.domain.enterprise_platform.enterprise_audit import record_enterprise_audit
from app.domain.enterprise_platform.persistence import (
    JsonDocumentStore,
    generate_api_key_material,
    hash_secret,
    new_id,
    redact,
    utc_iso,
)

SCOPES = frozenset(
    {
        "read:dashboard",
        "read:reports",
        "read:audit",
        "read:fleet",
        "write:support",
        "admin:org",
    }
)

_STORE: JsonDocumentStore | None = None


def get_api_key_store() -> JsonDocumentStore:
    global _STORE
    if _STORE is None:
        _STORE = JsonDocumentStore("enterprise_api_keys.json", "keys")
    return _STORE


def _public_view(row: dict[str, Any]) -> dict[str, Any]:
    out = redact(dict(row))
    out.pop("key_hash", None)
    out["secret_exposed"] = False
    out["plaintext"] = None
    return out


def list_api_keys(*, organization_id: str | None = None) -> dict[str, Any]:
    rows = get_api_key_store().list(limit=2000)
    if organization_id:
        rows = [
            r for r in rows if str(r.get("organization_id") or "") == organization_id
        ]
    return {
        "keys": [_public_view(r) for r in reversed(rows)],
        "count": len(rows),
        "scopes_available": sorted(SCOPES),
        "never_exposes_secrets": True,
        "fabricated": False,
    }


def create_api_key(
    *,
    organization_id: str,
    name: str,
    scopes: list[str] | None,
    operator: str,
    ip: str | None = None,
    expires_days: int | None = 90,
) -> dict[str, Any]:
    full, prefix, digest = generate_api_key_material()
    clean_scopes = [s for s in (scopes or ["read:dashboard"]) if s in SCOPES]
    if not clean_scopes:
        clean_scopes = ["read:dashboard"]
    expires_at = None
    if expires_days and expires_days > 0:
        expires_at = (
            datetime.now(UTC) + timedelta(days=int(expires_days))
        ).isoformat().replace("+00:00", "Z")
    row = {
        "id": new_id("key"),
        "organization_id": organization_id,
        "name": str(name or "API key").strip() or "API key",
        "prefix": prefix,
        "key_hash": digest,
        "scopes": clean_scopes,
        "status": "active",
        "created_at": utc_iso(),
        "created_by": operator,
        "rotated_at": None,
        "disabled_at": None,
        "expires_at": expires_at,
        "last_used_at": None,
    }
    saved = get_api_key_store().append(row)
    record_enterprise_audit(
        operator=operator,
        action="api_key_create",
        target=saved["id"],
        organization_id=organization_id,
        after={"prefix": prefix, "scopes": clean_scopes},
        ip=ip,
        category="api_keys",
    )
    # Return secret ONCE
    public = _public_view(saved)
    public["plaintext"] = full
    public["secret_exposed_once"] = True
    public["note"] = "Store this secret now — it will never be shown again"
    return public


def rotate_api_key(
    *,
    key_id: str,
    operator: str,
    ip: str | None = None,
) -> dict[str, Any]:
    before = get_api_key_store().get(key_id)
    if before is None:
        return {"ok": False, "error": "not_found"}
    full, prefix, digest = generate_api_key_material()

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        row["prefix"] = prefix
        row["key_hash"] = digest
        row["rotated_at"] = utc_iso()
        row["status"] = "active"
        row["disabled_at"] = None
        return row

    updated = get_api_key_store().upsert(key_id, mutator)
    record_enterprise_audit(
        operator=operator,
        action="api_key_rotate",
        target=key_id,
        organization_id=str((before or {}).get("organization_id") or ""),
        before={"prefix": before.get("prefix")},
        after={"prefix": prefix},
        ip=ip,
        category="api_keys",
    )
    public = _public_view(updated or {})
    public["plaintext"] = full
    public["secret_exposed_once"] = True
    public["ok"] = True
    return public


def disable_api_key(
    *,
    key_id: str,
    operator: str,
    ip: str | None = None,
) -> dict[str, Any]:
    before = get_api_key_store().get(key_id)
    if before is None:
        return {"ok": False, "error": "not_found"}

    def mutator(row: dict[str, Any]) -> dict[str, Any]:
        row["status"] = "disabled"
        row["disabled_at"] = utc_iso()
        return row

    updated = get_api_key_store().upsert(key_id, mutator)
    record_enterprise_audit(
        operator=operator,
        action="api_key_disable",
        target=key_id,
        organization_id=str((before or {}).get("organization_id") or ""),
        before={"status": before.get("status")},
        after={"status": "disabled"},
        ip=ip,
        category="api_keys",
    )
    return {"ok": True, "key": _public_view(updated or {})}


def verify_api_key(plaintext: str) -> dict[str, Any] | None:
    """Internal verify — never logs plaintext."""
    digest = hash_secret(plaintext)
    for row in get_api_key_store().list(limit=5000):
        if row.get("key_hash") == digest and row.get("status") == "active":
            exp = row.get("expires_at")
            if exp:
                try:
                    dt = datetime.fromisoformat(str(exp).replace("Z", "+00:00"))
                    if dt < datetime.now(UTC):
                        return None
                except Exception:  # noqa: S110  # best-effort optional path
                    pass
            return _public_view(row)
    return None
