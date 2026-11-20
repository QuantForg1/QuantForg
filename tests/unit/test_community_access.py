"""Community rules keep one customer out of another customer's content."""

from __future__ import annotations

import pytest

from app.domain.community.access import (
    allow_write,
    can_modify_content,
    can_view_profile,
    normalize_visibility,
    page_bounds,
)

pytestmark = pytest.mark.unit


def test_only_the_owner_or_a_moderator_can_change_content() -> None:
    assert can_modify_content(actor_id="a", owner_id="a", actor_role="trader")
    assert not can_modify_content(actor_id="b", owner_id="a", actor_role="trader")
    assert not can_modify_content(actor_id="b", owner_id="a", actor_role="owner")
    assert can_modify_content(actor_id="b", owner_id="a", actor_role="moderator")


def test_private_profiles_and_blocks_stay_hidden() -> None:
    assert normalize_visibility("PUBLIC") == "public"
    assert normalize_visibility("friends") == "private"
    hidden = can_view_profile(
        visibility="private", is_owner=False, blocked=False
    )
    assert hidden is False
    assert can_view_profile(visibility="public", is_owner=False, blocked=True) is False
    assert can_view_profile(visibility="public", is_owner=False, blocked=False) is True
    assert page_bounds(0, 100) == (1, 20)
    assert allow_write(recent_writes=5, limit=5) is False
    assert allow_write(recent_writes=4, limit=5) is True
