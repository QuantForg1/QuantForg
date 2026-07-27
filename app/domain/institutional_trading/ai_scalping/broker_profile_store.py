"""Encrypted broker runtime profile persistence (v7.1).

Persists broker / server / login / terminal_path for automatic restore.
Passwords are NEVER stored in plain text — only optional AES ciphertext.
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from core.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class BrokerRuntimeProfile:
    broker: str
    server: str
    login: int
    terminal_path: str = ""
    password_ciphertext: str | None = None
    updated_at: str | None = None

    def to_public_dict(self) -> dict[str, Any]:
        """Safe for logs/API — never includes ciphertext."""
        return {
            "broker": self.broker,
            "server": self.server,
            "login": self.login,
            "terminal_path": self.terminal_path,
            "has_encrypted_password": bool(self.password_ciphertext),
            "updated_at": self.updated_at,
        }

    def to_storage_dict(self) -> dict[str, Any]:
        return {
            "broker": self.broker,
            "server": self.server,
            "login": int(self.login),
            "terminal_path": self.terminal_path,
            "password_ciphertext": self.password_ciphertext,
            "updated_at": self.updated_at,
        }


def _default_path() -> Path:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        base = Path(
            getattr(settings, "data_dir", None)
            or getattr(settings, "ops_state_dir", None)
            or "data"
        )
    except Exception:
        base = Path("data")
    return base / "broker_runtime_profile.json"


@dataclass
class BrokerProfileStore:
    """Encrypted-at-rest broker restore profile (file-backed)."""

    path: Path | None = None
    _lock: threading.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_lock", threading.Lock())
        if self.path is None:
            object.__setattr__(self, "path", _default_path())

    def save(
        self,
        *,
        broker: str,
        server: str,
        login: int,
        terminal_path: str = "",
        password_plaintext: str | None = None,
        secret_key: str | None = None,
        preserve_existing_password: bool = True,
    ) -> BrokerRuntimeProfile:
        ciphertext: str | None = None
        if password_plaintext:
            if not secret_key or len(secret_key) < 32:
                raise ValueError(
                    "Cannot store password without a strong encryption secret"
                )
            from core.security.credential_encryption import encrypt_aes256_gcm

            ciphertext = encrypt_aes256_gcm(
                password_plaintext, secret_key=secret_key, key_version=1
            )
        elif preserve_existing_password:
            prior = self.load()
            if prior is not None and prior.password_ciphertext:
                ciphertext = prior.password_ciphertext
        profile = BrokerRuntimeProfile(
            broker=str(broker or "").strip(),
            server=str(server or "").strip(),
            login=int(login),
            terminal_path=str(terminal_path or "").strip(),
            password_ciphertext=ciphertext,
            updated_at=datetime.now(UTC).isoformat(),
        )
        path = self.path or _default_path()
        with self._lock:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(profile.to_storage_dict(), indent=2),
                encoding="utf-8",
            )
        logger.info(
            "broker_runtime_profile_saved",
            broker=profile.broker,
            server=profile.server,
            login=profile.login,
            has_password=bool(ciphertext),
        )
        return profile

    def load(self) -> BrokerRuntimeProfile | None:
        path = self.path or _default_path()
        if not path.exists():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(raw, dict):
                return None
            return BrokerRuntimeProfile(
                broker=str(raw.get("broker") or ""),
                server=str(raw.get("server") or ""),
                login=int(raw.get("login") or 0),
                terminal_path=str(raw.get("terminal_path") or ""),
                password_ciphertext=(
                    str(raw["password_ciphertext"])
                    if raw.get("password_ciphertext")
                    else None
                ),
                updated_at=raw.get("updated_at"),
            )
        except Exception:
            logger.exception("broker_runtime_profile_load_failed")
            return None

    def decrypt_password(
        self, profile: BrokerRuntimeProfile, *, secret_key: str
    ) -> str | None:
        if not profile.password_ciphertext:
            return None
        from core.security.credential_encryption import decrypt_aes256_gcm

        return decrypt_aes256_gcm(profile.password_ciphertext, secret_key=secret_key)

    def clear(self) -> None:
        path = self.path or _default_path()
        with self._lock:
            if path.exists():
                path.unlink()


_STORE: BrokerProfileStore | None = None
_STORE_LOCK = threading.Lock()


def get_broker_profile_store() -> BrokerProfileStore:
    global _STORE
    with _STORE_LOCK:
        if _STORE is None:
            _STORE = BrokerProfileStore()
        return _STORE
