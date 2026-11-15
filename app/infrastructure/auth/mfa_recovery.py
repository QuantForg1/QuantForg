"""Hashed MFA recovery codes (application-managed)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from typing import Any
from uuid import UUID

from core.config.settings import Settings
from core.logging import get_logger

logger = get_logger(__name__)

_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def _pepper(settings: Settings) -> bytes:
    raw = settings.secret_key
    if raw is None:
        value = "quantforg-dev-pepper"
    elif hasattr(raw, "get_secret_value"):
        value = str(raw.get_secret_value() or "quantforg-dev-pepper")
    else:
        value = str(raw) or "quantforg-dev-pepper"
    return value.encode("utf-8")


def hash_recovery_code(settings: Settings, code: str) -> str:
    normalized = code.strip().upper().replace("-", "").replace(" ", "")
    digest = hmac.new(_pepper(settings), normalized.encode("utf-8"), hashlib.sha256)
    return digest.hexdigest()


def generate_recovery_codes(count: int = 8) -> list[str]:
    codes: list[str] = []
    for _ in range(count):
        raw = "".join(secrets.choice(_ALPHABET) for _ in range(10))
        codes.append(f"{raw[:5]}-{raw[5:]}")
    return codes


class MfaRecoveryCodeStore:
    """Persist recovery code hashes via Supabase service client."""

    def __init__(self, supabase: Any, settings: Settings) -> None:
        self._supabase = supabase
        self._settings = settings

    def _client(self) -> Any:
        return self._supabase.client

    def replace_codes(self, *, user_id: UUID, codes: list[str]) -> None:
        hashes = [hash_recovery_code(self._settings, c) for c in codes]
        table = self._client().table("auth_mfa_recovery_codes")
        table.delete().eq("user_id", str(user_id)).execute()
        rows = [{"user_id": str(user_id), "code_hash": h} for h in hashes]
        if rows:
            table.insert(rows).execute()
        logger.info(
            "mfa_recovery_codes_rotated",
            user_id=str(user_id),
            count=len(codes),
        )

    def consume(self, *, user_id: UUID, code: str) -> bool:
        code_hash = hash_recovery_code(self._settings, code)
        table = self._client().table("auth_mfa_recovery_codes")
        result = (
            table.select("id,used_at")
            .eq("user_id", str(user_id))
            .eq("code_hash", code_hash)
            .is_("used_at", "null")
            .limit(1)
            .execute()
        )
        rows = getattr(result, "data", None) or []
        if not rows:
            return False
        row_id = rows[0]["id"]
        from datetime import UTC, datetime

        table.update({"used_at": datetime.now(UTC).isoformat()}).eq(
            "id", row_id
        ).execute()
        logger.info("mfa_recovery_code_consumed", user_id=str(user_id))
        return True

    def remaining_count(self, *, user_id: UUID) -> int:
        result = (
            self._client()
            .table("auth_mfa_recovery_codes")
            .select("id", count="exact")
            .eq("user_id", str(user_id))
            .is_("used_at", "null")
            .execute()
        )
        count = getattr(result, "count", None)
        if isinstance(count, int):
            return count
        data = getattr(result, "data", None) or []
        return len(data)
