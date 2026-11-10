"""Enable staging-only Realtime publication for live_market_chat_messages."""

from __future__ import annotations

from pathlib import Path

import psycopg

SEC = Path.home() / "AppData" / "Local" / "QuantForg" / "secrets" / "staging"
DSN = (SEC / "database_url_pooler.txt").read_text(encoding="ascii").strip()
STAGING = "saxsyobktmlyjghumxfz"
PROD = "otqyhlmwaifokrczryrc"


def main() -> int:
    if STAGING not in DSN or PROD in DSN:
        print("REFUSE: not staging DSN")
        return 2
    with psycopg.connect(DSN) as conn:
        pub = conn.execute(
            "select pubname from pg_publication where pubname='supabase_realtime'"
        ).fetchone()
        print("publication", bool(pub))
        row = conn.execute(
            """
            select 1 from pg_publication_tables
            where pubname='supabase_realtime'
              and schemaname='public'
              and tablename='live_market_chat_messages'
            """
        ).fetchone()
        if row:
            print("already_in_realtime")
            return 0
        conn.execute(
            "alter publication supabase_realtime add table public.live_market_chat_messages"
        )
        conn.commit()
        print("added_to_realtime_publication")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
