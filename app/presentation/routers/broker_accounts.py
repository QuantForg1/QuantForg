"""Broker account REST API — CRUD only, no live trading."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.application.dto.broker import (
    BrokerAccountDTO,
    CreateBrokerAccountCommand,
    DeleteBrokerAccountCommand,
    UpdateBrokerAccountCommand,
)
from app.domain.enums.broker import BrokerAccountStatus, BrokerEnvironment
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.broker import BrokerSvc
from app.presentation.dto_mapping import dto_to_dict
from app.presentation.schemas.broker import (
    BrokerAccountResponse,
    CreateBrokerAccountRequest,
    UpdateBrokerAccountRequest,
)

router = APIRouter(prefix="/broker-accounts", tags=["broker-accounts"])


def _to_response(dto: BrokerAccountDTO) -> BrokerAccountResponse:
    data = dto_to_dict(dto)
    data["credential_types"] = list(data.get("credential_types") or ())
    return BrokerAccountResponse(**data)


@router.get("", response_model=list[BrokerAccountResponse])
async def list_broker_accounts(
    user: CurrentUser,
    brokers: BrokerSvc,
) -> list[BrokerAccountResponse]:
    items = await brokers.list_accounts.execute(user_id=user.id)
    return [_to_response(i) for i in items]


@router.get("/{account_id}", response_model=BrokerAccountResponse)
async def get_broker_account(
    account_id: UUID,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerAccountResponse:
    dto = await brokers.get_account.execute(user_id=user.id, account_id=account_id)
    return _to_response(dto)


@router.post(
    "",
    response_model=BrokerAccountResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_broker_account(
    body: CreateBrokerAccountRequest,
    request: Request,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerAccountResponse:
    ip, ua = get_client_meta(request)
    dto = await brokers.create_account.execute(
        CreateBrokerAccountCommand(
            user_id=user.id,
            broker_id=body.broker_id,
            external_account_id=body.external_account_id,
            label=body.label,
            environment=BrokerEnvironment(body.environment),
            server=body.server,
            metadata=body.metadata,
            password=body.password,
            api_key=body.api_key,
            api_secret=body.api_secret,
            token=body.token,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.patch("/{account_id}", response_model=BrokerAccountResponse)
async def update_broker_account(
    account_id: UUID,
    body: UpdateBrokerAccountRequest,
    request: Request,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> BrokerAccountResponse:
    ip, ua = get_client_meta(request)
    dto = await brokers.update_account.execute(
        UpdateBrokerAccountCommand(
            user_id=user.id,
            account_id=account_id,
            label=body.label,
            server=body.server,
            environment=(
                BrokerEnvironment(body.environment) if body.environment else None
            ),
            metadata=body.metadata,
            status=BrokerAccountStatus(body.status) if body.status else None,
            password=body.password,
            api_key=body.api_key,
            api_secret=body.api_secret,
            token=body.token,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _to_response(dto)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_broker_account(
    account_id: UUID,
    request: Request,
    user: CurrentUser,
    brokers: BrokerSvc,
) -> None:
    ip, ua = get_client_meta(request)
    await brokers.delete_account.execute(
        DeleteBrokerAccountCommand(
            user_id=user.id,
            account_id=account_id,
            ip_address=ip,
            user_agent=ua,
        )
    )
