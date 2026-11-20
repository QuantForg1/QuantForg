"""Community store SQL + migration against a real PostgreSQL (RUN_INTEGRATION=1)."""

from __future__ import annotations

import os
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import pytest

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("RUN_INTEGRATION") != "1",
        reason="Set RUN_INTEGRATION=1 to run integration tests",
    ),
]

MIGRATION = (
    Path(__file__).resolve().parents[2]
    / "supabase/migrations/20261120123100_community_foundation.sql"
)


_ROLES_SQL = """
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated;
  END IF;
END$$
"""


def _url() -> str:
    return (
        f"postgresql+asyncpg://{os.environ['POSTGRES_USER']}:"
        f"{os.environ.get('POSTGRES_PASSWORD', '')}@"
        f"{os.environ.get('POSTGRES_HOST', 'localhost')}:"
        f"{os.environ.get('POSTGRES_PORT', '5432')}/{os.environ['POSTGRES_DB']}"
    )


class _Db:
    def __init__(self, maker) -> None:
        self._maker = maker

    @asynccontextmanager
    async def session(self):
        async with self._maker.begin() as s:
            yield s


@pytest.fixture
async def env():
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    schema = f"qf_com_{uuid.uuid4().hex[:8]}"
    engine = create_async_engine(
        _url(), connect_args={"server_settings": {"search_path": schema}}
    )
    async with engine.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA {schema}"))
        await conn.execute(text(_ROLES_SQL))
        await conn.execute(text("CREATE TABLE users (id uuid PRIMARY KEY)"))
        raw = await conn.get_raw_connection()
        await raw.driver_connection.execute(
            MIGRATION.read_text().replace("public.", "")
        )
    maker = async_sessionmaker(engine, expire_on_commit=False)
    users = [str(uuid.uuid4()) for _ in range(3)]
    async with maker.begin() as s:
        for u in users:
            await s.execute(text("INSERT INTO users (id) VALUES (:id)"), {"id": u})
    yield _Db(maker), users
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
    await engine.dispose()


@pytest.mark.asyncio
async def test_report_queue_and_remove_on_real_postgres(env) -> None:
    from app.application.services.community_board import CommunityBoard
    from app.infrastructure.persistence.community_store import PostgresCommunityStore

    db, (author, reporter, moderator) = env
    store = PostgresCommunityStore(db)
    board = CommunityBoard(store)
    post = await board.write_post(
        author_id=author, body="buy my signals", visibility="public"
    )
    assert post["status"] == "created"
    assert (
        await board.report(
            reporter_id=reporter,
            target_type="post",
            target_id=post["post_id"],
            reason="spam",
        )
    )["status"] == "reported"

    assert (await board.moderation_queue(actor_role="trader"))["reason"] == "forbidden"
    queue = (await board.moderation_queue(actor_role="moderator"))["reports"]
    assert len(queue) == 1
    assert queue[0]["content"] == "buy my signals"
    assert queue[0]["author_id"] == author

    result = await board.resolve_report(
        actor_id=moderator,
        actor_role="moderator",
        report_id=queue[0]["report_id"],
        action="remove",
    )
    assert result["status"] == "resolved"
    assert await store.post(post["post_id"]) is None
    assert (await board.moderation_queue(actor_role="moderator"))["reports"] == []
    again = await board.resolve_report(
        actor_id=moderator,
        actor_role="moderator",
        report_id=queue[0]["report_id"],
        action="dismiss",
    )
    assert again["status"] == "already_resolved"


@pytest.mark.asyncio
async def test_customer_cannot_delete_someone_elses_post_on_real_postgres(env) -> None:
    from app.application.services.community_board import CommunityBoard
    from app.infrastructure.persistence.community_store import PostgresCommunityStore

    db, (author, other, _) = env
    board = CommunityBoard(PostgresCommunityStore(db))
    post = await board.write_post(author_id=author, body="hello", visibility="public")
    denied = await board.change_post(
        actor_id=other,
        actor_role="trader",
        post_id=post["post_id"],
        body=None,
        delete=True,
    )
    assert denied["reason"] == "forbidden"
    feed = await board.feed(viewer_id=other, page=1, page_size=20)
    assert [p["body"] for p in feed["posts"]] == ["hello"]
