"""Broker catalogue REST API — CRUD only, no live trading."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status

from app.application.dto.auth import AuthUserDTO
from app.application.dto.broker import (
    BrokerDTO,
    CreateBrokerCommand,
    DeleteBrokerCommand,
    UpdateBrokerCommand,
)
from app.domain.enums.broker import (
    BrokerCapabilityCode,
    BrokerPlatform,
    BrokerStatus,
    BrokerType,
)
from app.domain.enums.user import UserRole
from app.presentation.dependencies.auth import (
    CurrentUser,
    get_client_meta,
    require_roles,
)
from app.presentation.dependencies.broker import BrokerSvc
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.broker import (
    BrokerDiagnosticsResponse,
    BrokerHealthResponse,
    BrokerResponse,
    CreateBrokerRequest,
    UpdateBrokerRequest,
)

router = APIRouter(prefix="/brokers", tags=["brokers"])

AdminUser = Annotated[
    AuthUserDTO,
    Depends(require_roles(UserRole.OWNER, UserRole.ADMIN)),
]


def _to_response(dto: BrokerDTO) -> BrokerResponse:
    data = dto_to_dict(dto)
    data["capabilities"] = list(data.get("capabilities") or ())
    return BrokerResponse(**data)


@router.get("", response_model=list[BrokerResponse])
async def list_brokers(
    _user: CurrentUser,
    brokers: BrokerSvc,
) -> list[BrokerResponse]:
    items = await brokers.list_brokers.execute()
    return [_to_response(i) for i in items]


@router.get("/{broker_id}", response_model=BrokerResponse)
async def get_broker(
    broker_id: UUID,
    _user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerResponse:
    dto = await brokers.get_broker.execute(broker_id=broker_id)
    return _to_response(dto)


@router.get("/{broker_id}/health", response_model=BrokerHealthResponse)
async def get_broker_health(
    broker_id: UUID,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerHealthResponse:
    dto = await brokers.get_broker_health.execute(broker_id=broker_id, user_id=user.id)
    return BrokerHealthResponse(
        broker_id=dto.broker_id,
        status=dto.status,
        latency_ms=dto.latency_ms,
        uptime_seconds=dto.uptime_seconds,
        reconnect_count=dto.reconnect_count,
        last_error=dto.last_error,
        capabilities=list(dto.capabilities),
        last_heartbeat_at=dto.last_heartbeat_at,
        last_successful_connection_at=dto.last_successful_connection_at,
        connection_count=dto.connection_count,
    )


@router.get("/{broker_id}/diagnostics", response_model=BrokerDiagnosticsResponse)
async def get_broker_diagnostics(
    broker_id: UUID,
    _admin: AdminUser,
    brokers: BrokerSvc,
) -> BrokerDiagnosticsResponse:
    # Admin/owner only — connection_id / account UUIDs must not leak cross-tenant.
    dto = await brokers.get_broker_diagnostics.execute(broker_id=broker_id)
    return BrokerDiagnosticsResponse(
        broker_id=dto.broker_id,
        status=dto.status,
        latency_ms=dto.latency_ms,
        uptime_seconds=dto.uptime_seconds,
        reconnect_count=dto.reconnect_count,
        last_error=dto.last_error,
        capabilities=list(dto.capabilities),
        discovered_capabilities=list(dto.discovered_capabilities),
        connections=list(dto.connections),
        reconnect=list(dto.reconnect),
        platform_code=dto.platform_code,
        last_heartbeat_at=dto.last_heartbeat_at,
        last_successful_connection_at=dto.last_successful_connection_at,
    )


@router.post(
    "",
    response_model=BrokerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker(
    body: CreateBrokerRequest,
    request: Request,
    user: AdminUser,
    brokers: BrokerSvc,
) -> BrokerResponse:
    ip, ua = get_client_meta(request)
    codes = tuple(BrokerCapabilityCode(c) for c in body.capability_codes)
    dto = await brokers.create_broker.execute(
        CreateBrokerCommand(
            name=body.name,
            slug=body.slug,
            broker_type=BrokerType(body.broker_type),
            platform_code=BrokerPlatform(body.platform_code),
            country_code=body.country_code,
            website=body.website,
            description=body.description,
            activate=body.activate,
            capability_codes=codes,
            actor_user_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.patch("/{broker_id}", response_model=BrokerResponse)
async def update_broker(
    broker_id: UUID,
    body: UpdateBrokerRequest,
    request: Request,
    user: AdminUser,
    brokers: BrokerSvc,
) -> BrokerResponse:
    ip, ua = get_client_meta(request)
    dto = await brokers.update_broker.execute(
        UpdateBrokerCommand(
            broker_id=broker_id,
            name=body.name,
            broker_type=BrokerType(body.broker_type) if body.broker_type else None,
            platform_code=(
                BrokerPlatform(body.platform_code) if body.platform_code else None
            ),
            country_code=body.country_code,
            website=body.website,
            description=body.description,
            status=BrokerStatus(body.status) if body.status else None,
            actor_user_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.delete("/{broker_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_broker(
    broker_id: UUID,
    request: Request,
    user: AdminUser,
    brokers: BrokerSvc,
) -> None:
    ip, ua = get_client_meta(request)
    await brokers.delete_broker.execute(
        DeleteBrokerCommand(
            broker_id=broker_id,
            actor_user_id=user.id,
            ip_address=ip,
            user_agent=ua,
        )
    )
