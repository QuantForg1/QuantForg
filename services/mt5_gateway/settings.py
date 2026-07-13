"""MT5 Gateway settings — credentials never stored in Railway."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MT5GatewaySettings(BaseSettings):
    """Environment for the Windows MT5 Gateway process only."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    mt5_gateway_token: str = Field(
        default="",
        description="Shared bearer token required by all gateway routes except /health",
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


@lru_cache(maxsize=1)
def get_gateway_settings() -> MT5GatewaySettings:
    return MT5GatewaySettings()
