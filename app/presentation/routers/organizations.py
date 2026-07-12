"""Organization REST API."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request, status

from app.application.dto.platform import CreateTeamCommand, InviteMemberCommand
from app.domain.enums.platform import OrganizationMemberRole
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.platform import PlatformSvc
from app.presentation.schemas.platform import (
    CreateTeamRequest,
    InvitationResponse,
    InviteMemberRequest,
    OrganizationResponse,
)

router = APIRouter(prefix="/organizations", tags=["organizations"])


@router.get("", response_model=list[OrganizationResponse])
async def list_organizations(
    user: CurrentUser, platform: PlatformSvc
) -> list[OrganizationResponse]:
    items = await platform.list_organizations.execute(user_id=user.id)
    return [OrganizationResponse(**i.__dict__) for i in items]


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_team(
    body: CreateTeamRequest,
    request: Request,
    user: CurrentUser,
    platform: PlatformSvc,
) -> OrganizationResponse:
    ip, ua = get_client_meta(request)
    dto = await platform.create_team.execute(
        CreateTeamCommand(
            owner_user_id=user.id,
            name=body.name,
            slug=body.slug,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return OrganizationResponse(**dto.__dict__)


@router.post(
    "/{organization_id}/invitations",
    response_model=InvitationResponse,
    status_code=status.HTTP_201_CREATED,
)
async def invite_member(
    organization_id: UUID,
    body: InviteMemberRequest,
    request: Request,
    user: CurrentUser,
    platform: PlatformSvc,
) -> InvitationResponse:
    ip, ua = get_client_meta(request)
    dto = await platform.invite_member.execute(
        InviteMemberCommand(
            organization_id=organization_id,
            invited_by=user.id,
            email=str(body.email),
            role=OrganizationMemberRole(body.role),
            ip_address=ip,
            user_agent=ua,
        )
    )
    return InvitationResponse(**dto.__dict__)
