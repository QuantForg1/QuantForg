"""MT5 Gateway settings — credentials never stored in Railway."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.mt5_gateway.token_util import (
    mask_gateway_token,
    normalize_gateway_token,
    tokens_equal,
)

logger = logging.getLogger("quantforg.mt5_gateway.settings")

# Copied from deploy/mt5_gateway/gateway.env.example — len == 32.
_PLACEHOLDER_TOKEN = "replace-with-strong-random-token"  # noqa: S105
_PLACEHOLDER_PREFIXES = (
    "replace-with",
    "changeme",
    "your-token",
    "todo-",
    "xxx",
)

# Resolved after get_gateway_settings(); exposed for /health + auth logs.
_TOKEN_LOAD_META: dict[str, Any] = {
    "source": "unset",
    "dotenv_path": None,
    "process_env_len": 0,
    "dotenv_len": 0,
    "effective_len": 0,
}


def token_load_meta() -> dict[str, Any]:
    return dict(_TOKEN_LOAD_META)


def _is_placeholder_token(token: str) -> bool:
    text = normalize_gateway_token(token)
    if not text:
        return True
    lower = text.lower()
    if lower == _PLACEHOLDER_TOKEN:
        return True
    return any(lower.startswith(p) for p in _PLACEHOLDER_PREFIXES)


def _repo_root() -> Path:
    # services/mt5_gateway/settings.py → parents[2] == repository root
    return Path(__file__).resolve().parents[2]


def _walk_up_env_files(start: Path, *, limit: int = 8) -> list[Path]:
    found: list[Path] = []
    current = start.resolve()
    for _ in range(limit):
        candidate = current / ".env"
        if candidate.is_file():
            found.append(candidate)
        if current.parent == current:
            break
        current = current.parent
    return found


def gateway_env_file_candidates() -> list[Path]:
    """Ordered ``.env`` discovery — explicit env, package root, CWD walk-up."""
    ordered: list[Path] = []
    seen: set[str] = set()

    def _add(path: Path) -> None:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            return
        seen.add(key)
        ordered.append(path)

    explicit = (os.environ.get("MT5_GATEWAY_ENV_FILE") or "").strip()
    if explicit:
        _add(Path(explicit))

    root = _repo_root()
    _add(root / ".env")
    _add(root / "deploy" / "mt5_gateway" / ".env")

    for path in _walk_up_env_files(Path.cwd()):
        _add(path)
    for path in _walk_up_env_files(Path(__file__).resolve().parent):
        _add(path)

    return ordered


def _existing_env_files() -> tuple[str, ...]:
    found = [str(path) for path in gateway_env_file_candidates() if path.is_file()]
    return tuple(found) if found else (".env",)


def _parse_token_from_env_text(text: str) -> str:
    """Return the last MT5_GATEWAY_TOKEN assignment in a .env body (wins)."""
    found = ""
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if key.strip().upper() != "MT5_GATEWAY_TOKEN":
            continue
        found = normalize_gateway_token(value)
    return found


def _read_token_from_dotenv_files() -> tuple[str, str]:
    """Return best ``(token, source_path)`` from discovered ``.env`` files.

    Prefer a non-placeholder token. If multiple files define the key, the first
    non-placeholder wins; otherwise the first definition is returned.
    """
    placeholder_hit = ("", "")
    for path in gateway_env_file_candidates():
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except OSError as exc:
            logger.warning("gateway_env_read_failed path=%s error=%s", path, exc)
            continue
        token = _parse_token_from_env_text(text)
        if not token:
            continue
        if _is_placeholder_token(token):
            if not placeholder_hit[0]:
                placeholder_hit = (token, str(path.resolve()))
            logger.warning(
                "gateway_env_placeholder_ignored path=%s length=%s preview=%s",
                path,
                len(token),
                mask_gateway_token(token),
            )
            continue
        return token, str(path.resolve())
    return placeholder_hit


def _classify_process_source() -> str:
    """Python only sees process env — NSSM/User/System all look the same."""
    if "MT5_GATEWAY_TOKEN" not in os.environ:
        return "unset"
    # NSSM injects AppEnvironmentExtra into the process environment.
    return "process_env"


class MT5GatewaySettings(BaseSettings):
    """Environment for the Windows MT5 Gateway process only."""

    model_config = SettingsConfigDict(
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
    mt5_health_probe_timeout_seconds: float = Field(
        default=0.35,
        gt=0,
        le=2.0,
        description=(
            "Max seconds /health may wait on MetaTrader5 account_info. "
            "Must stay well under 500ms end-to-end. On timeout, health returns "
            "degraded from last heartbeat instead of hanging forever."
        ),
        validation_alias=AliasChoices(
            "MT5_HEALTH_PROBE_TIMEOUT_SECONDS",
            "mt5_health_probe_timeout_seconds",
        ),
    )
    mt5_api_call_timeout_seconds: float = Field(
        default=2.0,
        gt=0,
        le=30.0,
        description=(
            "Bound MetaTrader5 API calls used by heartbeat (never block forever)."
        ),
        validation_alias=AliasChoices(
            "MT5_API_CALL_TIMEOUT_SECONDS",
            "mt5_api_call_timeout_seconds",
        ),
    )
    mt5_reconnect_enabled: bool = Field(default=True)
    mt5_reconnect_max_attempts: int = Field(default=5, ge=0)
    mt5_reconnect_backoff_seconds: float = Field(default=2.0, gt=0)
    mt5_gateway_allow_unauthenticated_health: bool = Field(default=True)
    mt5_gateway_enable_websocket: bool = Field(default=True)
    mt5_gateway_auto_attach: bool = Field(
        default=False,
        description=(
            "On startup, initialize MetaTrader5 and adopt an already logged-in "
            "terminal session without collecting the broker password."
        ),
    )
    mt5_gateway_auth_debug: bool = Field(
        default=False,
        description=(
            "Log token load diagnostics (masked). Never enable in production "
            "longer than needed to debug auth."
        ),
        validation_alias=AliasChoices(
            "MT5_GATEWAY_AUTH_DEBUG", "mt5_gateway_auth_debug"
        ),
    )

    # Not loaded from env — set by get_gateway_settings after resolution.
    token_source: str = Field(default="unset", exclude=True)

    @field_validator("mt5_gateway_token", mode="before")
    @classmethod
    def _normalize_token(cls, value: object) -> str:
        return normalize_gateway_token(str(value) if value is not None else "")


def _resolve_token(
    *,
    process_token: str,
    file_token: str,
    file_source: str,
) -> tuple[str, str]:
    """Choose effective token + source label.

    Rules (Windows DX):
    1. Real dotenv token beats placeholder / conflicting process env (NSSM).
    2. Real process env used when dotenv missing.
    3. Never keep ``replace-with-strong-random-token`` (len 32) when a real
       dotenv value exists (typical mismatch: expected_len=32 vs received_len=43).
    """
    process_ok = bool(process_token) and not _is_placeholder_token(process_token)
    file_ok = bool(file_token) and not _is_placeholder_token(file_token)

    if file_ok and process_ok and not tokens_equal(process_token, file_token):
        return file_token, f"dotenv:{file_source}"
    if file_ok and not process_ok:
        return file_token, f"dotenv:{file_source}"
    if file_ok and process_ok and tokens_equal(process_token, file_token):
        return file_token, f"dotenv:{file_source}"
    if process_ok:
        return process_token, _classify_process_source()
    if file_token:
        # Placeholder-only dotenv (misconfigured host).
        return file_token, f"dotenv_placeholder:{file_source}"
    if process_token:
        return process_token, "process_env_placeholder"
    return "", "unset"


@lru_cache(maxsize=1)
def get_gateway_settings() -> MT5GatewaySettings:
    env_files = _existing_env_files()
    raw_process = os.environ.get("MT5_GATEWAY_TOKEN")
    process_token = normalize_gateway_token(raw_process)
    file_token, file_source = _read_token_from_dotenv_files()

    logger.info(
        "gateway_settings_loading cwd=%s repo_root=%s env_files=%s "
        "process_env_set=%s process_env_len=%s dotenv_path=%s dotenv_len=%s",
        str(Path.cwd()),
        str(_repo_root()),
        list(env_files),
        "MT5_GATEWAY_TOKEN" in os.environ,
        len(process_token),
        file_source or "<none>",
        len(file_token),
    )

    # Build settings without letting a stale process env permanently win.
    # We still construct via pydantic for other fields, then overwrite token.
    settings = MT5GatewaySettings(_env_file=env_files)
    effective, source = _resolve_token(
        process_token=process_token,
        file_token=file_token,
        file_source=file_source,
    )
    settings.mt5_gateway_token = effective
    settings.token_source = source

    _TOKEN_LOAD_META.clear()
    _TOKEN_LOAD_META.update(
        {
            "source": source,
            "dotenv_path": file_source or None,
            "process_env_len": len(process_token),
            "dotenv_len": len(file_token),
            "effective_len": len(effective),
            "process_is_placeholder": _is_placeholder_token(process_token),
            "dotenv_is_placeholder": _is_placeholder_token(file_token),
            "process_equals_settings": tokens_equal(process_token, effective),
            "dotenv_equals_settings": tokens_equal(file_token, effective),
        }
    )

    # Temporary diagnostics requested for the 32-vs-43 mismatch.
    logger.info(
        "gateway_token_resolved source=%s effective_len=%s "
        "process_env_len=%s dotenv_len=%s "
        "os.environ_repr_len=%s settings_repr_len=%s "
        "process_equals_settings=%s fingerprint=%s",
        source,
        len(effective),
        len(process_token),
        len(file_token),
        len(repr(raw_process) if raw_process is not None else "None"),
        len(repr(settings.mt5_gateway_token)),
        tokens_equal(process_token, effective),
        mask_gateway_token(effective),
    )
    logger.info(
        "gateway_token_debug os.environ.get=%r settings.mt5_gateway_token=%r "
        "os.environ_len=%s settings_len=%s differ=%s",
        mask_gateway_token(process_token)
        if not settings.mt5_gateway_auth_debug
        else (raw_process if raw_process is not None else None),
        mask_gateway_token(effective)
        if not settings.mt5_gateway_auth_debug
        else settings.mt5_gateway_token,
        len(process_token),
        len(effective),
        not tokens_equal(process_token, effective),
    )
    if settings.mt5_gateway_auth_debug:
        logger.warning(
            "MT5_GATEWAY_AUTH_DEBUG: full token repr logged above — "
            "set MT5_GATEWAY_AUTH_DEBUG=false after auth works."
        )
    if _is_placeholder_token(effective):
        logger.error(
            "MT5_GATEWAY_TOKEN is still the example placeholder "
            "(length %s). Put the real 43-char token in the repo .env and "
            "remove the stale NSSM/process value, then restart.",
            len(effective),
        )
    return settings
