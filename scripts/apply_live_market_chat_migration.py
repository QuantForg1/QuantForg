"""Apply Live Market Chat SQL migrations using DATABASE_URL (additive only).

Never prints connection strings or secrets.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import asyncpg


ROOT = Path(__file__).resolve().parents[1]
FILES = [
    ROOT / "supabase/migrations/20261110180000_live_market_chat.sql",
    ROOT / "supabase/migrations/20261110180100_live_market_chat_rls.sql",
]


async def main() -> int:
    raw = (os.environ.get("DATABASE_URL") or "").strip()
    if not raw:
        print("DATABASE_URL missing")
        return 2
    url = raw.replace("postgresql+asyncpg://", "postgresql://", 1)
    conn = await asyncpg.connect(url, timeout=30)
    try:
        for path in FILES:
            sql = path.read_text(encoding="utf-8")
            print(f"applying {path.name}")
            await conn.execute(sql)
            print(f"ok {path.name}")
        exists = await conn.fetchval(
            """
            SELECT EXISTS (
              SELECT 1 FROM information_schema.tables
              WHERE table_schema = 'public'
                AND table_name = 'live_market_chat_messages'
            )
            """
        )
        print(f"table_live_market_chat_messages={bool(exists)}")
    finally:
        await conn.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
