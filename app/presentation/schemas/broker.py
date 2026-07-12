"""Pydantic schemas for Broker Foundation REST API."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class BrokerResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    broker_type: str
    status: str
    platform_code: str
    country_code: str
    website: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateBrokerRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=1, max_length=100)
    broker_type: str = "retail"
    platform_code: str = "other"
    country_code: str = Field(default="US", min_length=2, max_length=2)
    website: str = ""
    description: str = ""
    activate: bool = False
    capability_codes: list[str] = Field(default_factory=list)


class UpdateBrokerRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    broker_type: str | None = None
    platform_code: str | None = None
    country_code: str | None = Field(default=None, min_length=2, max_length=2)
    website: str | None = None
    description: str | None = None
    status: str | None = None


class BrokerAccountResponse(BaseModel):
    id: UUID
    user_id: UUID
    broker_id: UUID
    external_account_id: str
    label: str
    environment: str
    status: str
    server: str
    metadata: dict[str, str] = Field(default_factory=dict)
    connection_status: str | None = None
    credential_types: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class CreateBrokerAccountRequest(BaseModel):
    broker_id: UUID
    external_account_id: str = Field(min_length=1, max_length=128)
    label: str = ""
    environment: str = "demo"
    server: str = ""
    metadata: dict[str, str] = Field(default_factory=dict)
    # Secrets accepted on write only — never returned in responses.
    password: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    api_secret: str | None = Field(default=None, min_length=1, max_length=512)
    token: str | None = Field(default=None, min_length=1, max_length=2048)


class UpdateBrokerAccountRequest(BaseModel):
    label: str | None = None
    server: str | None = None
    environment: str | None = None
    metadata: dict[str, str] | None = None
    status: str | None = None
    password: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, max_length=512)
    api_secret: str | None = Field(default=None, min_length=1, max_length=512)
    token: str | None = Field(default=None, min_length=1, max_length=2048)


class BrokerConnectionResponse(BaseModel):
    id: UUID
    broker_account_id: UUID
    status: str
    last_connected_at: datetime | None = None
    last_error: str = ""
    adapter_session_ref: str = ""
    session_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class ConnectBrokerRequest(BaseModel):
    account_id: UUID


class ValidateBrokerResponse(BaseModel):
    account_id: UUID
    valid: bool
    platform_code: str
    message: str = ""


class BrokerHealthResponse(BaseModel):
    broker_id: UUID
    status: str
    latency_ms: float | None = None
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    last_error: str = ""
    capabilities: list[str] = Field(default_factory=list)
    last_heartbeat_at: datetime | None = None
    last_successful_connection_at: datetime | None = None
    connection_count: int = 0


class BrokerDiagnosticsResponse(BaseModel):
    broker_id: UUID
    status: str
    latency_ms: float | None = None
    uptime_seconds: float = 0.0
    reconnect_count: int = 0
    last_error: str = ""
    capabilities: list[str] = Field(default_factory=list)
    discovered_capabilities: list[str] = Field(default_factory=list)
    connections: list[dict[str, object]] = Field(default_factory=list)
    reconnect: list[dict[str, object]] = Field(default_factory=list)
    platform_code: str
    last_heartbeat_at: datetime | None = None
    last_successful_connection_at: datetime | None = None
