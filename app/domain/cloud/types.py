"""Gateway Manager domain types — cloud registry, never invents live MT5 data."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class GatewayStatus(StrEnum):
    ONLINE = "online"
    OFFLINE = "offline"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    DRAINING = "draining"


@dataclass
class GatewayCapabilities:
    quotes: bool = True
    candles: bool = True
    positions: bool = True
    orders: bool = True
    history: bool = True
    heartbeat: bool = True
    account_sync: bool = True
    websocket: bool = False

    def to_dict(self) -> dict[str, bool]:
        return {
            "quotes": self.quotes,
            "candles": self.candles,
            "positions": self.positions,
            "orders": self.orders,
            "history": self.history,
            "heartbeat": self.heartbeat,
            "account_sync": self.account_sync,
            "websocket": self.websocket,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> GatewayCapabilities:
        data = raw or {}
        return cls(
            quotes=bool(data.get("quotes", True)),
            candles=bool(data.get("candles", True)),
            positions=bool(data.get("positions", True)),
            orders=bool(data.get("orders", True)),
            history=bool(data.get("history", True)),
            heartbeat=bool(data.get("heartbeat", True)),
            account_sync=bool(data.get("account_sync", True)),
            websocket=bool(data.get("websocket", False)),
        )


@dataclass
class GatewayMetrics:
    cpu_percent: float | None = None
    memory_percent: float | None = None
    heartbeat_ms: float | None = None
    latency_ms: float | None = None
    quotes_per_sec: float | None = None
    orders_per_sec: float | None = None
    history_sync_ok: bool | None = None
    reconnect_count: int = 0
    connected_users: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "heartbeat_ms": self.heartbeat_ms,
            "latency_ms": self.latency_ms,
            "quotes_per_sec": self.quotes_per_sec,
            "orders_per_sec": self.orders_per_sec,
            "history_sync_ok": self.history_sync_ok,
            "reconnect_count": self.reconnect_count,
            "connected_users": self.connected_users,
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None) -> GatewayMetrics:
        data = raw or {}
        return cls(
            cpu_percent=_f(data.get("cpu_percent")),
            memory_percent=_f(data.get("memory_percent")),
            heartbeat_ms=_f(data.get("heartbeat_ms")),
            latency_ms=_f(data.get("latency_ms")),
            quotes_per_sec=_f(data.get("quotes_per_sec")),
            orders_per_sec=_f(data.get("orders_per_sec")),
            history_sync_ok=(
                bool(data["history_sync_ok"])
                if data.get("history_sync_ok") is not None
                else None
            ),
            reconnect_count=int(data.get("reconnect_count") or 0),
            connected_users=int(data.get("connected_users") or 0),
        )


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass
class GatewayRecord:
    gateway_id: str
    hostname: str
    broker: str
    region: str
    version: str
    status: GatewayStatus = GatewayStatus.UNKNOWN
    latency_ms: float | None = None
    last_heartbeat_at: str | None = None
    last_seen_at: str | None = None
    capabilities: GatewayCapabilities = field(default_factory=GatewayCapabilities)
    metrics: GatewayMetrics = field(default_factory=GatewayMetrics)
    base_url: str = ""
    ip_allowlist: tuple[str, ...] = ()
    token_fingerprint: str = ""
    token_version: int = 1
    compatible: bool = True
    min_cloud_version: str = "1.0.0"
    failure_reason: str = ""
    created_at: str = ""
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "gateway_id": self.gateway_id,
            "hostname": self.hostname,
            "broker": self.broker,
            "region": self.region,
            "version": self.version,
            "status": self.status.value,
            "latency_ms": self.latency_ms,
            "heartbeat": self.last_heartbeat_at,
            "last_seen": self.last_seen_at,
            "capabilities": self.capabilities.to_dict(),
            "metrics": self.metrics.to_dict(),
            "base_url": self.base_url,
            "ip_allowlist": list(self.ip_allowlist),
            "token_version": self.token_version,
            "compatible": self.compatible,
            "min_cloud_version": self.min_cloud_version,
            "failure_reason": self.failure_reason,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


def new_gateway_id() -> str:
    return f"gw-{uuid4().hex[:12]}"


def utc_now() -> str:
    return datetime.now(UTC).isoformat()
