"""MT5 Gateway settings — credentials never stored in Railway."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.mt5_gateway.token_util import (
    mask_gateway_token,
    normalize_gateway_token,
    tokens_equal,
)

logger = logging.getLogger("quantforg.mt5_gateway.settings")


def _repo_root() -> Path:
    # services/mt5_gateway/settings.py → parents[2] == repository root
    return Path(__file__).resolve().parents[2]


def gateway_env_file_candidates() -> list[Path]:
    """Ordered ``.env`` candidates (repo root first, then deploy/, then CWD)."""
    root = _repo_root()
    return [
        root / ".env",
        root / "deploy" / "mt5_gateway" / ".env",
        Path.cwd() / ".env",
    ]


def _existing_env_files() -> tuple[str, ...]:
    found = [str(path) for path in gateway_env_file_candidates() if path.is_file()]
    return tuple(found) if found else (".env",)


def _read_token_from_dotenv_files() -> tuple[str, str]:
    """Return ``(token, source_path)`` from the first file that defines the key."""
    for path in gateway_env_file_candidates():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")  # utf-8-sig strips BOM
        except OSError:
            continue
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip().upper() != "MT5_GATEWAY_TOKEN":
                continue
            return normalize_gateway_token(value), str(path)
    return "", ""


class MT5GatewaySettings(BaseSettings):
    """Environment for the Windows MT5 Gateway process only."""

    model_config = SettingsConfigDict(
        # env_file is passed dynamically via ``_env_file=`` in get_gateway_settings
        # so Windows CWD / repo-root candidates resolve at process start, not import.
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    mt5_gateway_token: str = Field(
        default="",
        description="Shared bearer token required by all gateway routes except /health",
        validation_alias=AliasChoices("MT5_GATEWAY_TOKEN", "mt5_gateway_token"),
    )
    mt5_gateway_host: str = Field(default="127.0.0.1")
    mt5_gateway_port: int = Field(default=8765, ge=1, le=65535)
    mt5_terminal_path: str = Field(
        default="",
        description="Optional path to terminal64.exe on the Windows host",
    )
    mt5_heartbeat_interval_seconds: float = Field(default=5.0, gt=0)
    mt5_reconnect_enabled: bool = Field(default=True)
    mt5_reconnect_max_attempts: int = Field(default=5, ge=0)
    mt5_reconnect_backoff_seconds: float = Field(default=2.0, gt=0)
    mt5_gateway_allow_unauthenticated_health: bool = Field(default=True)
    mt5_gateway_enable_websocket: bool = Field(default=True)
    mt5_gateway_auto_attach: bool = Field(
        default=False,
        description=(
            "On startup, initialize MetaTrader5 and adopt an already logged-in "
            "terminal session without collecting the broker password. "
            "Recommended for local Windows DX; leave false in hardened production "
            "unless the host is private and the terminal is operator-managed."
        ),
    )
    mt5_gateway_auth_debug: bool = Field(
        default=True,
        description=(
            "Log masked token fingerprints on each auth check "
            "(first/last 6 chars only)."
        ),
        validation_alias=AliasChoices(
            "MT5_GATEWAY_AUTH_DEBUG", "mt5_gateway_auth_debug"
        ),
    )

    @field_validator("mt5_gateway_token", mode="before")
    @classmethod
    def _normalize_token(cls, value: object) -> str:
        return normalize_gateway_token(str(value) if value is not None else "")


@lru_cache(maxsize=1)
def get_gateway_settings() -> MT5GatewaySettings:
    env_files = _existing_env_files()
    logger.info(
        "gateway_settings_loading cwd=%s env_files=%s "
        "process_env_token_set=%s",
        str(Path.cwd()),
        list(env_files),
        bool(normalize_gateway_token(os.environ.get("MT5_GATEWAY_TOKEN"))),
    )
    settings = MT5GatewaySettings(_env_file=env_files)
    process_token = normalize_gateway_token(os.environ.get("MT5_GATEWAY_TOKEN"))
    file_token, file_source = _read_token_from_dotenv_files()
    effective = normalize_gateway_token(settings.mt5_gateway_token)

    # Windows operators usually edit repo `.env`. Stale User/NSSM process env
    # silently wins in pydantic-settings and causes HTTP 401 with "same" token.
    # Prefer the dotenv file when both are set and disagree.
    if (
        file_token
        and process_token
        and not tokens_equal(process_token, file_token)
    ):
        logger.warning(
            "MT5_GATEWAY_TOKEN mismatch: process environment (%s) differs from "
            ".env file %s (%s). Preferring .env file token. Clear the stale "
            "Windows/NSSM MT5_GATEWAY_TOKEN to avoid confusion.",
            mask_gateway_token(process_token),
            file_source,
            mask_gateway_token(file_token),
        )
        settings.mt5_gateway_token = file_token
        effective = file_token
    elif file_token and not effective:
        settings.mt5_gateway_token = file_token
        effective = file_token

    logger.info(
        "gateway_token_loaded configured=%s length=%s fingerprint=%s "
        "process_env=%s file_source=%s file=%s",
        bool(effective),
        len(effective),
        mask_gateway_token(effective),
        mask_gateway_token(process_token),
        file_source or "<none>",
        mask_gateway_token(file_token),
    )
    return settings
