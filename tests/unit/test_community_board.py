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


@pytest.mark.asyncio
async def test_moderation_queue_is_moderator_only_and_remove_deletes_content() -> None:
    store = MemoryCommunityStore()
    board = CommunityBoard(store)
    created = await board.write_post(
        author_id="author", body="spam", visibility="public"
    )
    post_id = created["post_id"]
    await board.report(
        reporter_id="r1", target_type="post", target_id=post_id, reason="spam"
    )
    await board.report(
        reporter_id="r2", target_type="post", target_id=post_id, reason="spam"
    )

    denied = await board.moderation_queue(actor_role="trader")
    assert denied["reason"] == "forbidden"

    queue = await board.moderation_queue(actor_role="moderator")
    assert len(queue["reports"]) == 2
    assert queue["reports"][0]["content"] == "spam"
    assert queue["reports"][0]["reports_on_target"] == 2

    customer = await board.resolve_report(
        actor_id="author",
        actor_role="trader",
        report_id=queue["reports"][0]["report_id"],
        action="remove",
    )
    assert customer["reason"] == "forbidden"
    assert await store.post(post_id) is not None

    done = await board.resolve_report(
        actor_id="mod",
        actor_role="moderator",
        report_id=queue["reports"][0]["report_id"],
        action="remove",
    )
    assert done == {"status": "resolved", "action": "remove"}
    assert await store.post(post_id) is None
    # both reports on the same post are closed
    assert (await board.moderation_queue(actor_role="moderator"))["reports"] == []


@pytest.mark.asyncio
async def test_dismiss_keeps_content_and_bad_input_is_rejected() -> None:
    store = MemoryCommunityStore()
    board = CommunityBoard(store)
    post_id = (await board.write_post(author_id="a", body="fine", visibility="public"))[
        "post_id"
    ]
    await board.report(
        reporter_id="r", target_type="post", target_id=post_id, reason="x"
    )
    rid = (await board.moderation_queue(actor_role="moderator"))["reports"][0][
        "report_id"
    ]
    assert (
        await board.resolve_report(
            actor_id="m", actor_role="moderator", report_id=rid, action="ban"
        )
    )["reason"] == "invalid_action"
    assert (
        await board.resolve_report(
            actor_id="m", actor_role="moderator", report_id=rid, action="dismiss"
        )
    )["status"] == "resolved"
    assert await store.post(post_id) is not None
    assert (
        await board.resolve_report(
            actor_id="m", actor_role="moderator", report_id=rid, action="dismiss"
        )
    )["status"] == "already_resolved"
