"""Customer community API. Hidden until COMMUNITY_ENABLED is true."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.application.services.community_board import CommunityBoard, StoreUnavailable
from app.domain.identity.designated_owner import is_designated_owner_email
from app.infrastructure.persistence.community_store import PostgresCommunityStore
from app.presentation.dependencies.auth import CurrentUser
from core.config.settings import get_settings
from core.di.container import get_container

router = APIRouter(prefix="/community", tags=["community"])


class ProfileUpdate(BaseModel):
    visibility: str = Field(min_length=1, max_length=16)


class PostCreate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    visibility: str = "private"


class PostUpdate(BaseModel):
    body: str = Field(min_length=1, max_length=2000)


class CommentCreate(BaseModel):
    body: str = Field(min_length=1, max_length=1000)


class ReportCreate(BaseModel):
    target_type: str
    target_id: str
    reason: str = Field(min_length=1, max_length=500)


class BlockCreate(BaseModel):
    user_id: str


def _board() -> CommunityBoard:
    return CommunityBoard(PostgresCommunityStore(get_container().database))


def _enabled() -> None:
    if not get_settings().community_enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Community is not enabled",
        )


def _role(user: Any) -> str:
    role = str(getattr(user, "role", "") or "").strip().lower()
    if role == "support":
        return "moderator"
    if role in {"owner", "admin"} and is_designated_owner_email(
        str(getattr(user, "email", "") or "")
    ):
        return "moderator"
    return role


@router.get("/profile/{user_id}")
async def read_profile(user_id: str, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().read_profile(viewer_id=str(user.id), owner_id=user_id)
    except StoreUnavailable:
        return {"visible": False, "available": False}


@router.put("/profile")
async def update_profile(body: ProfileUpdate, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().update_profile(
            user_id=str(user.id), visibility=body.visibility
        )
    except StoreUnavailable:
        return {"visible": False, "available": False}


@router.get("/posts")
async def list_posts(
    user: CurrentUser,
    page: int = Query(default=1),
    page_size: int = Query(default=20),
) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().feed(
            viewer_id=str(user.id), page=page, page_size=page_size
        )
    except StoreUnavailable:
        return {"available": False, "page": 1, "page_size": 20, "posts": []}


@router.post("/posts")
async def create_post(body: PostCreate, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().write_post(
            author_id=str(user.id), body=body.body, visibility=body.visibility
        )
    except StoreUnavailable:
        return {"status": "unavailable"}


@router.patch("/posts/{post_id}")
async def update_post(
    post_id: str, body: PostUpdate, user: CurrentUser
) -> dict[str, Any]:
    _enabled()
    return await _change_post(user, post_id, body=body.body, delete=False)


@router.delete("/posts/{post_id}")
async def delete_post(post_id: str, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    return await _change_post(user, post_id, body=None, delete=True)


@router.post("/posts/{post_id}/comments")
async def create_comment(
    post_id: str, body: CommentCreate, user: CurrentUser
) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().write_comment(
            author_id=str(user.id), post_id=post_id, body=body.body
        )
    except StoreUnavailable:
        return {"status": "unavailable"}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().change_comment(
            actor_id=str(user.id),
            actor_role=_role(user),
            comment_id=comment_id,
            delete=True,
        )
    except StoreUnavailable:
        return {"status": "unavailable"}


@router.post("/reports")
async def report_content(body: ReportCreate, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().report(
            reporter_id=str(user.id),
            target_type=body.target_type,
            target_id=body.target_id,
            reason=body.reason,
        )
    except StoreUnavailable:
        return {"status": "unavailable"}


@router.post("/blocks")
async def block_user(body: BlockCreate, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().set_block(
            blocker_id=str(user.id), blocked_id=body.user_id, blocked=True
        )
    except StoreUnavailable:
        return {"status": "unavailable"}


@router.delete("/blocks/{user_id}")
async def unblock_user(user_id: str, user: CurrentUser) -> dict[str, Any]:
    _enabled()
    try:
        return await _board().set_block(
            blocker_id=str(user.id), blocked_id=user_id, blocked=False
        )
    except StoreUnavailable:
        return {"status": "unavailable"}


async def _change_post(
    user: Any, post_id: str, *, body: str | None, delete: bool
) -> dict[str, Any]:
    try:
        return await _board().change_post(
            actor_id=str(user.id),
            actor_role=_role(user),
            post_id=post_id,
            body=body,
            delete=delete,
        )
    except StoreUnavailable:
        return {"status": "unavailable"}
