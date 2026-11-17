from __future__ import annotations

from typing import Any

from app.application.services import customer_account_assignment as caa


def test_assignment_query_excludes_owner_and_admin_accounts() -> None:
    seen: list[str] = []

    def fetch(sql: str, *_a: Any) -> list[dict[str, Any]]:
        seen.append(sql)
        return []

    caa.next_unassigned_account(taken_account_ids=set(), fetch=fetch)
    assert seen, "query not executed"
    sql = " ".join(seen[0].split()).lower()
    assert "from public.users u" in sql
    assert "in ('owner', 'admin')" in sql
    assert "not exists" in sql
