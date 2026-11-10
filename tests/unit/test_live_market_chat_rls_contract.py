"""Contract checks for Live Market Chat RLS migrations (static, no secrets)."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RLS = ROOT / "supabase" / "migrations" / "20261110180100_live_market_chat_rls.sql"
TABLE = ROOT / "supabase" / "migrations" / "20261110180000_live_market_chat.sql"


def test_rls_migration_enforces_ownership_and_public_read() -> None:
    sql = RLS.read_text(encoding="utf-8")
    assert "ENABLE ROW LEVEL SECURITY" in sql
    assert "FORCE ROW LEVEL SECURITY" in sql
    assert "live_market_chat_messages_select_public" in sql
    assert "status = 'visible'" in sql
    assert "live_market_chat_messages_insert_own" in sql
    assert "user_id = public.current_app_user_id()" in sql
    assert "live_market_chat_messages_update_own" in sql
    assert "REVOKE DELETE ON public.live_market_chat_messages" in sql
    assert "FROM anon, authenticated" in sql
    assert "live_market_chat_reports_insert_own" in sql
    assert "reporter_id = public.current_app_user_id()" in sql
    assert "GRANT SELECT ON public.live_market_chat_messages" in sql
    assert "TO anon, authenticated" in sql
    assert "GRANT INSERT, UPDATE ON public.live_market_chat_messages" in sql
    assert "TO authenticated" in sql


def test_table_migration_bounds_body_and_channel() -> None:
    sql = TABLE.read_text(encoding="utf-8")
    assert "CHECK (char_length(body) BETWEEN 1 AND 500)" in sql
    assert "CHECK (channel ~ '^[a-z0-9_-]{2,32}$')" in sql
    assert "REFERENCES public.users (id)" in sql
