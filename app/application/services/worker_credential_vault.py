"""Read a customer's own MT5 credentials from the encrypted broker vault.

Used only to seal an envelope for the worker that is assigned to that
exact broker account. The password is decrypted in memory, sealed at once,
and never logged or returned in plaintext. Returns ``None`` when anything is
missing; callers then refuse to issue an envelope (no invented login).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class VaultCredential:
    login: str
    server: str
    environment: str
    password: str

    def __repr__(self) -> str:  # never print the secret
        return (
            f"VaultCredential(login=***{self.login[-4:]}, server={self.server!r}, "
            f"environment={self.environment!r})"
        )


def _settings_keys() -> tuple[str, tuple[str, ...]]:
    from core.config.settings import get_settings

    s = get_settings()
    key = s.secret_key.get_secret_value()
    previous = tuple(
        k.get_secret_value() for k in s.credential_encryption_previous_keys
    )
    return key, previous


def load_vault_credential(
    *,
    broker_account_id: UUID,
    user_id: UUID,
    fetch: Any | None = None,
    keys: tuple[str, tuple[str, ...]] | None = None,
) -> VaultCredential | None:
    """Ownership-checked read: the account must belong to ``user_id``."""
    from core.security.crypto import decrypt_secret

    if fetch is None:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch as _fetch,
        )

        if not direct_postgres_available():
            return None
        fetch = _fetch
    try:
        rows = fetch(
            """
            SELECT a.external_account_id, a.server, a.environment, a.status,
                   c.encrypted_payload
              FROM public.broker_accounts a
              JOIN public.broker_credentials c
                ON c.broker_account_id = a.id
             WHERE a.id = $1::uuid
               AND a.user_id = $2::uuid
               AND lower(c.credential_type) = 'password'
               AND coalesce(lower(c.status), 'active') = 'active'
             ORDER BY c.updated_at DESC
             LIMIT 1
            """,
            str(broker_account_id),
            str(user_id),
        )
    except Exception:
        logger.exception("worker_vault_read_failed")
        return None
    if not rows:
        return None
    row = rows[0]
    if str(row.get("status") or "").lower() in {"revoked", "disabled", "deleted"}:
        return None
    login = str(row.get("external_account_id") or "").strip()
    server = str(row.get("server") or "").strip()
    if not login or not server:
        return None
    key, previous = keys if keys is not None else _settings_keys()
    try:
        password = decrypt_secret(
            str(row["encrypted_payload"]), secret_key=key, previous_keys=previous
        )
    except Exception:
        logger.warning("worker_vault_decrypt_failed")
        return None
    if not password:
        return None
    return VaultCredential(
        login=login,
        server=server,
        environment=str(row.get("environment") or "").lower(),
        password=password,
    )


def assigned_account_login(
    *, broker_account_id: UUID, user_id: UUID, fetch: Any | None = None
) -> str | None:
    """MT5 login of the account a worker is assigned to (owner-checked).

    ``None`` means it cannot be read; ``""`` means no such owned account.
    """
    if fetch is None:
        from app.infrastructure.persistence.direct_postgres import (
            direct_postgres_available,
            fetch as _fetch,
        )

        if not direct_postgres_available():
            return None
        fetch = _fetch
    try:
        rows = fetch(
            """
            SELECT external_account_id FROM public.broker_accounts
             WHERE id = $1::uuid AND user_id = $2::uuid
             LIMIT 1
            """,
            str(broker_account_id),
            str(user_id),
        )
    except Exception:
        logger.exception("worker_assigned_login_read_failed")
        return None
    if not rows:
        return ""
    return str(rows[0].get("external_account_id") or "").strip()
