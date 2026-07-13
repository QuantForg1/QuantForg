"""Gateway Manager HTTP schemas (additive cloud API)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class RegisterGatewayRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    broker: str = Field(..., min_length=1, max_length=64)
    region: str = Field(default="unknown", max_length=64)
    version: str = Field(default="1.0.0", max_length=32)
    base_url: str = Field(default="", max_length=512)
    capabilities: dict[str, Any] = Field(default_factory=dict)
    ip_allowlist: list[str] = Field(default_factory=list)
    gateway_id: str | None = Field(default=None, max_length=64)


class GatewayHeartbeatRequest(BaseModel):
    gateway_id: str = Field(..., min_length=1, max_length=64)
    token: str = Field(..., min_length=8, max_length=256)
    nonce: str = Field(..., min_length=8, max_length=128)
    latency_ms: float | None = Field(default=None, ge=0)
    metrics: dict[str, Any] = Field(default_factory=dict)
    status: str | None = Field(default=None, max_length=32)


class RouteGatewayRequest(BaseModel):
    broker: str = Field(..., min_length=1, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    capability: str | None = Field(default=None, max_length=64)


class ReplaceGatewayRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    broker: str | None = Field(default=None, max_length=64)
    region: str | None = Field(default=None, max_length=64)
    version: str = Field(default="1.0.0", max_length=32)
    base_url: str = Field(default="", max_length=512)
