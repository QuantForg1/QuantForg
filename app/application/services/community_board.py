"""Customer community board. One customer cannot change another's content."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from app.domain.community.access import (
    allow_write,
    can_modify_content,
    can_view_profile,
    normalize_visibility,
    page_bounds,
)


class StoreUnavailable(Exception):
    """The community tables are not available."""


@dataclass(frozen=True, slots=True)
class Post:
    post_id: str
    author_id: str
    body: str
    visibility: str
    created_at: str


@dataclass(frozen=True, slots=True)
class Comment:
    comment_id: str
    post_id: str
    author_id: str
    body: str
    created_at: str


class CommunityStore(Protocol):
    async def profile(self, user_id: str) -> dict[str, Any] | None: ...

    async def save_profile(self, user_id: str, visibility: str) -> None: ...

    async def recent_writes(self, user_id: str, kind: str) -> int: ...

    async def save_post(self, post: Post) -> None: ...

    async def save_comment(self, comment: Comment) -> None: ...

    async def post(self, post_id: str) -> Post | None: ...

    async def comment(self, comment_id: str) -> Comment | None: ...

    async def replace_post(self, post: Post) -> None: ...

    async def delete_post(self, post_id: str) -> None: ...

    async def delete_comment(self, comment_id: str) -> None: ...

    async def visible_posts(
        self, *, viewer_id: str, page: int, page_size: int
    ) -> list[Post]: ...

    async def comments_for(self, post_id: str) -> list[Comment]: ...

    async def save_report(
        self, *, reporter_id: str, target_type: str, target_id: str, reason: str
    ) -> None: ...

    async def block(self, blocker_id: str, blocked_id: str) -> None: ...

    async def unblock(self, blocker_id: str, blocked_id: str) -> None: ...

    async def blocked(self, left_id: str, right_id: str) -> bool: ...


class MemoryCommunityStore:
    def __init__(self) -> None:
        self.profiles: dict[str, str] = {}
        self.posts: dict[str, Post] = {}
        self.comments: dict[str, Comment] = {}
        self.reports: list[dict[str, str]] = []
        self.blocks: set[tuple[str, str]] = set()
        self.writes: dict[tuple[str, str], int] = {}

    async def profile(self, user_id: str) -> dict[str, Any] | None:
        visibility = self.profiles.get(user_id)
        if visibility is None:
            return None
        return {"user_id": user_id, "visibility": visibility}

    async def save_profile(self, user_id: str, visibility: str) -> None:
        self.profiles[user_id] = visibility

    async def recent_writes(self, user_id: str, kind: str) -> int:
        return self.writes.get((user_id, kind), 0)

    async def save_post(self, post: Post) -> None:
        self.posts[post.post_id] = post
        key = (post.author_id, "post")
        self.writes[key] = self.writes.get(key, 0) + 1

    async def save_comment(self, comment: Comment) -> None:
        self.comments[comment.comment_id] = comment
        key = (comment.author_id, "comment")
        self.writes[key] = self.writes.get(key, 0) + 1

    async def post(self, post_id: str) -> Post | None:
        return self.posts.get(post_id)

    async def comment(self, comment_id: str) -> Comment | None:
        return self.comments.get(comment_id)

    async def replace_post(self, post: Post) -> None:
        self.posts[post.post_id] = post

    async def delete_post(self, post_id: str) -> None:
        self.posts.pop(post_id, None)

    async def delete_comment(self, comment_id: str) -> None:
        self.comments.pop(comment_id, None)

    async def visible_posts(
        self, *, viewer_id: str, page: int, page_size: int
    ) -> list[Post]:
        rows = [
            post
            for post in self.posts.values()
            if not await self.blocked(viewer_id, post.author_id)
            and (post.visibility == "public" or post.author_id == viewer_id)
        ]
        start = (page - 1) * page_size
        return rows[start : start + page_size]

    async def comments_for(self, post_id: str) -> list[Comment]:
        return [item for item in self.comments.values() if item.post_id == post_id]

    async def save_report(
        self, *, reporter_id: str, target_type: str, target_id: str, reason: str
    ) -> None:
        self.reports.append(
            {
                "reporter_id": reporter_id,
                "target_type": target_type,
                "target_id": target_id,
                "reason": reason,
            }
        )
        key = (reporter_id, "report")
        self.writes[key] = self.writes.get(key, 0) + 1

    async def block(self, blocker_id: str, blocked_id: str) -> None:
        self.blocks.add((blocker_id, blocked_id))

    async def unblock(self, blocker_id: str, blocked_id: str) -> None:
        self.blocks.discard((blocker_id, blocked_id))

    async def blocked(self, left_id: str, right_id: str) -> bool:
        return (left_id, right_id) in self.blocks or (right_id, left_id) in self.blocks


class CommunityBoard:
    def __init__(self, store: CommunityStore) -> None:
        self._store = store

    async def read_profile(self, *, viewer_id: str, owner_id: str) -> dict[str, Any]:
        profile = await self._store.profile(owner_id)
        visibility = "private" if profile is None else str(profile["visibility"])
        blocked = await self._store.blocked(viewer_id, owner_id)
        if not can_view_profile(
            visibility=visibility,
            is_owner=viewer_id == owner_id,
            blocked=blocked,
        ):
            return {"visible": False, "visibility": "private"}
        return {
            "visible": True,
            "user_id": owner_id,
            "visibility": visibility,
        }

    async def update_profile(self, *, user_id: str, visibility: str) -> dict[str, Any]:
        cleaned = normalize_visibility(visibility)
        await self._store.save_profile(user_id, cleaned)
        return {"visible": True, "user_id": user_id, "visibility": cleaned}

    async def write_post(
        self, *, author_id: str, body: str, visibility: str
    ) -> dict[str, Any]:
        cleaned = body.strip()
        if not cleaned or len(cleaned) > 2000:
            return {"status": "rejected", "reason": "invalid_post"}
        if not await self._allowed(author_id, "post", 5):
            return {"status": "rejected", "reason": "rate_limited"}
        post = Post(
            post_id=str(uuid4()),
            author_id=author_id,
            body=cleaned,
            visibility=normalize_visibility(visibility),
            created_at="",
        )
        await self._store.save_post(post)
        return {"status": "created", "post_id": post.post_id}

    async def write_comment(
        self, *, author_id: str, post_id: str, body: str
    ) -> dict[str, Any]:
        cleaned = body.strip()
        post = await self._store.post(post_id)
        if post is None or await self._store.blocked(author_id, post.author_id):
            return {"status": "rejected", "reason": "not_found"}
        if not cleaned or len(cleaned) > 1000:
            return {"status": "rejected", "reason": "invalid_comment"}
        if not await self._allowed(author_id, "comment", 20):
            return {"status": "rejected", "reason": "rate_limited"}
        comment = Comment(
            comment_id=str(uuid4()),
            post_id=post_id,
            author_id=author_id,
            body=cleaned,
            created_at="",
        )
        await self._store.save_comment(comment)
        return {"status": "created", "comment_id": comment.comment_id}

    async def change_post(
        self,
        *,
        actor_id: str,
        actor_role: str,
        post_id: str,
        body: str | None,
        delete: bool,
    ) -> dict[str, Any]:
        post = await self._store.post(post_id)
        if post is None:
            return {"status": "rejected", "reason": "not_found"}
        if not can_modify_content(
            actor_id=actor_id, owner_id=post.author_id, actor_role=actor_role
        ):
            return {"status": "rejected", "reason": "forbidden"}
        if delete:
            await self._store.delete_post(post_id)
            return {"status": "deleted"}
        cleaned = (body or "").strip()
        if not cleaned or len(cleaned) > 2000:
            return {"status": "rejected", "reason": "invalid_post"}
        await self._store.replace_post(
            Post(
                post_id=post.post_id,
                author_id=post.author_id,
                body=cleaned,
                visibility=post.visibility,
                created_at=post.created_at,
            )
        )
        return {"status": "updated"}

    async def change_comment(
        self,
        *,
        actor_id: str,
        actor_role: str,
        comment_id: str,
        delete: bool,
    ) -> dict[str, Any]:
        comment = await self._store.comment(comment_id)
        if comment is None:
            return {"status": "rejected", "reason": "not_found"}
        if not can_modify_content(
            actor_id=actor_id,
            owner_id=comment.author_id,
            actor_role=actor_role,
        ):
            return {"status": "rejected", "reason": "forbidden"}
        if delete:
            await self._store.delete_comment(comment_id)
            return {"status": "deleted"}
        return {"status": "rejected", "reason": "invalid_comment"}

    async def feed(
        self, *, viewer_id: str, page: int, page_size: int
    ) -> dict[str, Any]:
        safe_page, safe_size = page_bounds(page, page_size)
        posts = await self._store.visible_posts(
            viewer_id=viewer_id, page=safe_page, page_size=safe_size
        )
        return {
            "page": safe_page,
            "page_size": safe_size,
            "posts": [
                {
                    "post_id": post.post_id,
                    "author_id": post.author_id,
                    "body": post.body,
                    "visibility": post.visibility,
                    "created_at": post.created_at or None,
                }
                for post in posts
            ],
        }

    async def report(
        self, *, reporter_id: str, target_type: str, target_id: str, reason: str
    ) -> dict[str, Any]:
        cleaned = reason.strip()
        if (
            target_type not in {"post", "comment", "profile"}
            or not cleaned
            or len(cleaned) > 500
            or not _uuid(target_id)
        ):
            return {"status": "rejected", "reason": "invalid_report"}
        if not await self._allowed(reporter_id, "report", 10):
            return {"status": "rejected", "reason": "rate_limited"}
        await self._store.save_report(
            reporter_id=reporter_id,
            target_type=target_type,
            target_id=target_id,
            reason=cleaned,
        )
        return {"status": "reported"}

    async def set_block(
        self, *, blocker_id: str, blocked_id: str, blocked: bool
    ) -> dict[str, Any]:
        if blocker_id == blocked_id or not blocked_id.strip():
            return {"status": "rejected", "reason": "invalid_block"}
        if blocked:
            await self._store.block(blocker_id, blocked_id)
        else:
            await self._store.unblock(blocker_id, blocked_id)
        return {"status": "updated", "blocked": blocked}

    async def _allowed(self, user_id: str, kind: str, limit: int) -> bool:
        recent = await self._store.recent_writes(user_id, kind)
        return allow_write(recent_writes=recent, limit=limit)


def _uuid(value: str) -> bool:
    try:
        UUID(value)
    except ValueError:
        return False
    return True
