"""Broker connection REST API — CRUD / lifecycle only, no live trading."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.application.dto.broker import (
    BrokerConnectionDTO,
    ConnectBrokerCommand,
    DisconnectBrokerCommand,
    ValidateBrokerCommand,
)
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.broker import BrokerSvc
from app.presentation.schemas.broker import (
    BrokerConnectionResponse,
    ConnectBrokerRequest,
    ValidateBrokerResponse,
)

router = APIRouter(prefix="/broker-connections", tags=["broker-connections"])


def _to_response(dto: BrokerConnectionDTO) -> BrokerConnectionResponse:
    return BrokerConnectionResponse(**dto.__dict__)


@router.get("", response_model=list[BrokerConnectionResponse])
async def list_broker_connections(
    user: CurrentUser,
    brokers: BrokerSvc,
) -> list[BrokerConnectionResponse]:
    items = await brokers.list_connections.execute(user_id=user.id)
    return [_to_response(i) for i in items]


@router.get("/{connection_id}", response_model=BrokerConnectionResponse)
async def get_broker_connection(
    connection_id: UUID,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerConnectionResponse:
    dto = await brokers.get_connection.execute(
        user_id=user.id, connection_id=connection_id
    )
    return _to_response(dto)


@router.post(
    "/connect",
    response_model=BrokerConnectionResponse,
    status_code=status.HTTP_200_OK,
)
async def connect_broker(
    body: ConnectBrokerRequest,
    request: Request,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerConnectionResponse:
    ip, ua = get_client_meta(request)
    dto = await brokers.connect_broker.execute(
        ConnectBrokerCommand(
            user_id=user.id,
            account_id=body.account_id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.post(
    "/disconnect",
    response_model=BrokerConnectionResponse,
    status_code=status.HTTP_200_OK,
)
async def disconnect_broker(
    body: ConnectBrokerRequest,
    request: Request,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerConnectionResponse:
    ip, ua = get_client_meta(request)
    dto = await brokers.disconnect_broker.execute(
        DisconnectBrokerCommand(
            user_id=user.id,
            account_id=body.account_id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.post("/validate", response_model=ValidateBrokerResponse)
async def validate_broker(
    body: ConnectBrokerRequest,
    request: Request,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> ValidateBrokerResponse:
    ip, ua = get_client_meta(request)
    dto = await brokers.validate_broker.execute(
        ValidateBrokerCommand(
            user_id=user.id,
            account_id=body.account_id,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return ValidateBrokerResponse(**dto.__dict__)
