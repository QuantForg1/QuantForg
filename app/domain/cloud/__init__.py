"""Cloud package — Gateway Manager domain."""

from app.domain.cloud.registry import (
    GatewayRegistry,
    generate_gateway_token,
    hash_token,
)
from app.domain.cloud.routing import mark_stale_offline, route_gateway
from app.domain.cloud.types import (
    GatewayCapabilities,
    GatewayMetrics,
    GatewayStatus,
)

__all__ = [
    "GatewayCapabilities",
    "GatewayMetrics",
    "GatewayRegistry",
    "GatewayStatus",
    "generate_gateway_token",
    "hash_token",
    "mark_stale_offline",
    "route_gateway",
]
