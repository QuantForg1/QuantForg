"""Postgres community store. Missing tables stay unavailable."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from app.application.services.community_board import Comment, Post, StoreUnavailable


def _raise_unavailable(exc: ProgrammingError) -> None:
    if "does not exist" in str(exc).lower():
        raise StoreUnavailable from exc
    raise exc


class PostgresCommunityStore:
    def __init__(self, database: Any) -> None:
        self._database = database

    async def profile(self, user_id: str) -> dict[str, Any] | None:
        row = await self._one(
            "SELECT visibility FROM community_profiles WHERE user_id = :user_id",
            {"user_id": user_id},
        )
        if row is None:
            return None
        return {"user_id": user_id, "visibility": str(row[0])}

    async def save_profile(self, user_id: str, visibility: str) -> None:
        await self._write(
            "INSERT INTO community_profiles (user_id, visibility) "
            "VALUES (:user_id, :visibility) "
            "ON CONFLICT (user_id) DO UPDATE SET visibility = :visibility, "
            "updated_at = now()",
            {"user_id": user_id, "visibility": visibility},
        )

    async def recent_writes(self, user_id: str, kind: str) -> int:
        sql = {
            "post": (
                "SELECT count(*) FROM community_posts "
                "WHERE author_id = :user_id "
                "AND created_at > now() - interval '1 hour'"
            ),
            "comment": (
                "SELECT count(*) FROM community_comments "
                "WHERE author_id = :user_id "
                "AND created_at > now() - interval '1 hour'"
            ),
            "report": (
                "SELECT count(*) FROM community_reports "
                "WHERE reporter_id = :user_id "
                "AND created_at > now() - interval '1 hour'"
            ),
        }.get(kind)
        if sql is None:
            return 0
        row = await self._one(sql, {"user_id": user_id})
        return 0 if row is None else int(row[0])

    async def save_post(self, post: Post) -> None:
        await self._write(
            "INSERT INTO community_posts (id, author_id, body, visibility) "
            "VALUES (:id, :author_id, :body, :visibility)",
            {
                "id": post.post_id,
                "author_id": post.author_id,
                "body": post.body,
                "visibility": post.visibility,
            },
        )

    async def save_comment(self, comment: Comment) -> None:
        await self._write(
            "INSERT INTO community_comments (id, post_id, author_id, body) "
            "VALUES (:id, :post_id, :author_id, :body)",
            {
                "id": comment.comment_id,
                "post_id": comment.post_id,
                "author_id": comment.author_id,
                "body": comment.body,
            },
        )

    async def post(self, post_id: str) -> Post | None:
        row = await self._one(
            "SELECT id, author_id, body, visibility, created_at "
            "FROM community_posts WHERE id = :id",
            {"id": post_id},
        )
        return None if row is None else _post(row)

    async def comment(self, comment_id: str) -> Comment | None:
        row = await self._one(
            "SELECT id, post_id, author_id, body, created_at "
            "FROM community_comments WHERE id = :id",
            {"id": comment_id},
        )
        return None if row is None else _comment(row)

    async def replace_post(self, post: Post) -> None:
        await self._write(
            "UPDATE community_posts SET body = :body WHERE id = :id",
            {"id": post.post_id, "body": post.body},
        )

    async def delete_post(self, post_id: str) -> None:
        await self._write("DELETE FROM community_posts WHERE id = :id", {"id": post_id})

    async def delete_comment(self, comment_id: str) -> None:
        await self._write(
            "DELETE FROM community_comments WHERE id = :id",
            {"id": comment_id},
        )

    async def visible_posts(
        self, *, viewer_id: str, page: int, page_size: int
    ) -> list[Post]:
        rows = await self._all(
            "SELECT post.id, post.author_id, post.body, post.visibility, "
            "post.created_at FROM community_posts AS post "
            "WHERE (post.visibility = 'public' OR post.author_id = :viewer) "
            "AND NOT EXISTS ("
            "SELECT 1 FROM community_blocks AS block "
            "WHERE (block.blocker_id = :viewer AND block.blocked_id = post.author_id) "
            "OR (block.blocked_id = :viewer AND block.blocker_id = post.author_id)"
            ") ORDER BY post.created_at DESC LIMIT :limit OFFSET :offset",
            {
                "viewer": viewer_id,
                "limit": page_size,
                "offset": (page - 1) * page_size,
            },
        )
        return [_post(row) for row in rows]

    async def comments_for(self, post_id: str) -> list[Comment]:
        rows = await self._all(
            "SELECT id, post_id, author_id, body, created_at "
            "FROM community_comments WHERE post_id = :post_id "
            "ORDER BY created_at",
            {"post_id": post_id},
        )
        return [_comment(row) for row in rows]

    async def save_report(
        self, *, reporter_id: str, target_type: str, target_id: str, reason: str
    ) -> None:
        await self._write(
            "INSERT INTO community_reports "
            "(reporter_id, target_type, target_id, reason) "
            "VALUES (:reporter_id, :target_type, :target_id, :reason)",
            {
                "reporter_id": reporter_id,
                "target_type": target_type,
                "target_id": target_id,
                "reason": reason,
            },
        )

    async def block(self, blocker_id: str, blocked_id: str) -> None:
        await self._write(
            "INSERT INTO community_blocks (blocker_id, blocked_id) "
            "VALUES (:blocker, :blocked) ON CONFLICT DO NOTHING",
            {"blocker": blocker_id, "blocked": blocked_id},
        )

    async def unblock(self, blocker_id: str, blocked_id: str) -> None:
        await self._write(
            "DELETE FROM community_blocks "
            "WHERE blocker_id = :blocker AND blocked_id = :blocked",
            {"blocker": blocker_id, "blocked": blocked_id},
        )

    async def blocked(self, left_id: str, right_id: str) -> bool:
        row = await self._one(
            "SELECT 1 FROM community_blocks "
            "WHERE (blocker_id = :left AND blocked_id = :right) "
            "OR (blocker_id = :right AND blocked_id = :left)",
            {"left": left_id, "right": right_id},
        )
        return row is not None

    async def _one(self, sql: str, params: dict[str, Any]) -> Any:
        rows = await self._all(sql, params)
        return None if not rows else rows[0]

    async def _all(self, sql: str, params: dict[str, Any]) -> list[Any]:
        try:
            async with self._database.session() as session:
                result = await session.execute(text(sql), params)
                return list(result.all())
        except ProgrammingError as exc:
            _raise_unavailable(exc)
            return []

    async def _write(self, sql: str, params: dict[str, Any]) -> None:
        try:
            async with self._database.session() as session:
                await session.execute(text(sql), params)
        except ProgrammingError as exc:
            _raise_unavailable(exc)


def _post(row: Any) -> Post:
    return Post(str(row[0]), str(row[1]), str(row[2]), str(row[3]), _time(row[4]))


def _comment(row: Any) -> Comment:
    return Comment(str(row[0]), str(row[1]), str(row[2]), str(row[3]), _time(row[4]))


def _time(value: Any) -> str:
    if value is None:
        return ""
    iso = getattr(value, "isoformat", None)
    return iso() if callable(iso) else str(value)
