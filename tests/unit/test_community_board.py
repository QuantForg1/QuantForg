"""Community board — ownership, blocks, and empty feeds."""

from __future__ import annotations

import pytest

from app.application.services.community_board import (
    CommunityBoard,
    MemoryCommunityStore,
)

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_customer_cannot_edit_another_customers_post() -> None:
    board = CommunityBoard(MemoryCommunityStore())
    created = await board.write_post(
        author_id="user-a", body="Hello", visibility="public"
    )
    denied = await board.change_post(
        actor_id="user-b",
        actor_role="trader",
        post_id=created["post_id"],
        body="Changed",
        delete=False,
    )
    assert denied["reason"] == "forbidden"
    removed = await board.change_post(
        actor_id="user-b",
        actor_role="owner",
        post_id=created["post_id"],
        body=None,
        delete=True,
    )
    assert removed["reason"] == "forbidden"
    allowed = await board.change_post(
        actor_id="mod",
        actor_role="moderator",
        post_id=created["post_id"],
        body=None,
        delete=True,
    )
    assert allowed["status"] == "deleted"


@pytest.mark.asyncio
async def test_private_posts_and_blocks_are_hidden() -> None:
    board = CommunityBoard(MemoryCommunityStore())
    await board.write_post(author_id="user-a", body="Secret", visibility="private")
    public = await board.write_post(
        author_id="user-a", body="Open", visibility="public"
    )
    hidden = await board.feed(viewer_id="user-b", page=1, page_size=20)
    assert [item["body"] for item in hidden["posts"]] == ["Open"]
    await board.set_block(blocker_id="user-b", blocked_id="user-a", blocked=True)
    blocked = await board.feed(viewer_id="user-b", page=1, page_size=20)
    assert blocked["posts"] == []
    profile = await board.read_profile(viewer_id="user-b", owner_id="user-a")
    assert profile["visible"] is False
    comment = await board.write_comment(
        author_id="user-b", post_id=public["post_id"], body="No"
    )
    assert comment["reason"] == "not_found"


@pytest.mark.asyncio
async def test_invalid_report_and_rate_limit() -> None:
    board = CommunityBoard(MemoryCommunityStore())
    bad = await board.report(
        reporter_id="user-a",
        target_type="post",
        target_id="not-a-uuid",
        reason="spam",
    )
    assert bad["reason"] == "invalid_report"
    for _ in range(5):
        created = await board.write_post(
            author_id="user-a", body="Again", visibility="public"
        )
        assert created["status"] == "created"
    limited = await board.write_post(
        author_id="user-a", body="Too many", visibility="public"
    )
    assert limited["reason"] == "rate_limited"
