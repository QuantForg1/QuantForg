"""Community access rules. Content is not created here."""

from __future__ import annotations

MODERATION_ROLES = frozenset({"moderator"})
_VISIBILITY = frozenset({"private", "public"})


def can_modify_content(*, actor_id: str, owner_id: str, actor_role: str) -> bool:
    """The owner can edit their own content. A moderator can moderate it."""
    actor = actor_id.strip()
    owner = owner_id.strip()
    if not actor or not owner:
        return False
    if actor == owner:
        return True
    return actor_role.strip().lower() in MODERATION_ROLES


def can_view_profile(
    *,
    visibility: str,
    is_owner: bool,
    blocked: bool,
) -> bool:
    if blocked:
        return False
    if is_owner:
        return True
    return visibility.strip().lower() == "public"


def normalize_visibility(value: str) -> str:
    cleaned = value.strip().lower()
    if cleaned in _VISIBILITY:
        return cleaned
    return "private"


def page_bounds(
    page: int, page_size: int, *, max_page_size: int = 20
) -> tuple[int, int]:
    safe_page = page if page > 0 else 1
    if page_size < 1:
        safe_size = 1
    elif page_size > max_page_size:
        safe_size = max_page_size
    else:
        safe_size = page_size
    return safe_page, safe_size


def allow_write(*, recent_writes: int, limit: int) -> bool:
    if limit < 1:
        return False
    return recent_writes < limit
