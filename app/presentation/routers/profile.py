"""Profile & activity REST API."""

from __future__ import annotations

from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, File, Request, UploadFile, status

from app.application.dto.platform import ProfileDTO, UpdateProfileCommand
from app.domain.enums.platform import ProfileRiskLevel, TradingExperience
from app.domain.exceptions.base import ValidationError
from app.presentation.dependencies.auth import CurrentUser, get_client_meta
from app.presentation.dependencies.platform import PlatformSvc
from app.presentation.schemas.platform import (
    ActivityResponse,
    AvatarUploadResponse,
    ProfileResponse,
    UpdateProfileRequest,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def _profile(dto: ProfileDTO) -> ProfileResponse:
    return ProfileResponse(
        user_id=dto.user_id,
        avatar_url=dto.avatar_url,
        full_name=dto.full_name,
        username=dto.username,
        bio=dto.bio,
        country_code=dto.country_code,
        timezone=dto.timezone,
        preferred_language=dto.preferred_language,
        trading_experience=dto.trading_experience,
        risk_level=dto.risk_level,
    )


@router.get("", response_model=ProfileResponse)
async def get_profile(user: CurrentUser, platform: PlatformSvc) -> ProfileResponse:
    dto = await platform.get_profile.execute(
        user_id=user.id, display_name=user.display_name
    )
    return _profile(dto)


@router.patch("", response_model=ProfileResponse)
async def update_profile(
    body: UpdateProfileRequest,
    request: Request,
    user: CurrentUser,
    platform: PlatformSvc,
) -> ProfileResponse:
    ip, ua = get_client_meta(request)
    experience = (
        TradingExperience(body.trading_experience) if body.trading_experience else None
    )
    risk = ProfileRiskLevel(body.risk_level) if body.risk_level else None
    dto = await platform.update_profile.execute(
        UpdateProfileCommand(
            user_id=user.id,
            full_name=body.full_name,
            username=body.username,
            bio=body.bio,
            country_code=body.country_code.upper() if body.country_code else None,
            timezone=body.timezone,
            preferred_language=body.preferred_language,
            trading_experience=experience,
            risk_level=risk,
            ip_address=ip,
            user_agent=ua,
        )
    )
    return _profile(dto)


@router.get("/activity", response_model=list[ActivityResponse])
async def list_activity(
    user: CurrentUser, platform: PlatformSvc
) -> list[ActivityResponse]:
    items = await platform.list_activity.execute(user_id=user.id)
    return [
        ActivityResponse(
            id=i.id,
            category=i.category,
            action=i.action,
            message=i.message,
            created_at=i.created_at,
            metadata=i.metadata,
        )
        for i in items
    ]


@router.post(
    "/avatar",
    response_model=AvatarUploadResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_avatar(
    user: CurrentUser,
    platform: PlatformSvc,
    file: Annotated[UploadFile, File()],
) -> AvatarUploadResponse:
    allowed_types = {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/gif": "gif",
    }
    content_type = (file.content_type or "").split(";", 1)[0].strip().lower()
    if content_type not in allowed_types:
        raise ValidationError(
            "Avatar must be jpeg, png, webp, or gif",
            code="invalid_avatar_type",
        )
    # Reject SVG / HTML disguised as images; enforce size while streaming.
    max_bytes = 5 * 1024 * 1024
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(64 * 1024)
        if not chunk:
            break
        total += len(chunk)
        if total > max_bytes:
            raise ValidationError(
                "Avatar exceeds 5MB limit",
                code="avatar_too_large",
            )
        chunks.append(chunk)
    content = b"".join(chunks)
    if not content:
        raise ValidationError("Empty upload", code="empty_upload")
    # Magic-byte sniff (first bytes) — reject obvious non-images / SVG.
    head = content[:256].lstrip()
    if head.startswith(b"<") or b"<svg" in content[:1024].lower():
        raise ValidationError(
            "SVG and markup uploads are not allowed",
            code="invalid_avatar_type",
        )
    if content_type == "image/png" and not content.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValidationError("PNG content does not match type", code="invalid_avatar")
    if content_type == "image/jpeg" and not (content.startswith(b"\xff\xd8\xff")):
        raise ValidationError("JPEG content does not match type", code="invalid_avatar")
    ext = allowed_types[content_type]
    auth_folder = str(user.auth_user_id or user.id)
    object_path = f"{auth_folder}/{uuid4()}.{ext}"
    # Metadata persistence; binary upload to Supabase Storage is handled by
    # the storage adapter when configured (service role / user JWT).
    public_url = f"supabase://avatars/{object_path}"
    dto = await platform.set_avatar.execute(
        user_id=user.id,
        object_path=object_path,
        public_url=public_url,
        content_type=content_type,
        size_bytes=len(content),
    )
    return AvatarUploadResponse(avatar_url=dto.avatar_url, object_path=object_path)
