"""One-shot local verification: Postgres SELECT 1 + redis_configured flag.

Requires DATABASE_URL or SUPABASE_DB_PASSWORD in the environment.
"""

from __future__ import annotations

import asyncio
import os
from urllib.parse import quote


async def main() -> None:
    from core.config.settings import get_settings
    from core.database.session import DatabaseManager

    ref = os.environ.get("SUPABASE_PROJECT_REF", "").strip()
    dsn = os.environ.get("DATABASE_URL", "").strip()
    password = os.environ.get("SUPABASE_DB_PASSWORD", "").strip()
    if not dsn:
        if not ref or not password:
            raise SystemExit(
                "Set DATABASE_URL or SUPABASE_PROJECT_REF + SUPABASE_DB_PASSWORD"
            )
        dsn = (
            f"postgresql://postgres.{ref}:{quote(password, safe='')}"
            f"@aws-0-eu-central-1.pooler.supabase.com:5432/postgres"
        )
        os.environ["DATABASE_URL"] = dsn

    os.environ.setdefault("APP_ENV", "production")
    os.environ.setdefault(
        "SECRET_KEY",
        "a-real-production-secret-key-with-enough-entropy-here-xx",
    )
    os.environ.setdefault("DURABLE_PERSISTENCE", "true")
    os.environ.setdefault("EXECUTION_ENABLED", "false")
    os.environ.setdefault("ALLOWED_HOSTS", "localhost,127.0.0.1,testserver")

    get_settings.cache_clear()
    settings = get_settings()
    print("redis_configured", settings.redis_configured)
    print("ssl_enabled", bool(settings.asyncpg_connect_args))
    host = settings.database_url.split("@", 1)[1].split("/", 1)[0]
    print("dsn_host", host)

    db = DatabaseManager(settings)
    await db.start()
    ok = await db.health_check()
    print("pg_health", ok)
    await db.stop()
    if not ok:
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main())
