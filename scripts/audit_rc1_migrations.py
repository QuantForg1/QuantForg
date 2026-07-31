#!/usr/bin/env python3
"""Read-only production schema / migration audit via asyncpg.

Never applies migrations. Never prints DSN passwords.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.parse import urlparse


def _now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _redact_url(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        db = (parsed.path or "").lstrip("/")
        return f"{parsed.scheme}://***@{host}:{parsed.port or ''}/{db}"
    except Exception:
        return "[REDACTED_DSN]"


def _render_md(report: dict[str, Any]) -> str:
    pending = report.get("pending_relative_to_remote") or []
    notes = report.get("notes") or []
    remote = report.get("remote") or {}
    lines = [
        "# RC1 Migration Report",
        "",
        f"Generated: `{report.get('generated_at')}`",
        "",
        "## Policy",
        "",
        "- Migrations were **NOT** applied by this run.",
        "- Production apply is blocked until staging verification.",
        "",
        "## Repository",
        "",
        f"- Supabase up migrations: `{report.get('repo_supabase_migrations_count')}`",
        f"- Alembic revisions: `{report.get('repo_alembic_revisions')}`",
        f"- DSN present: `{report.get('database_dsn_present')}`",
        f"- DSN (redacted): `{report.get('database_dsn_redacted')}`",
        "",
        "## Remote",
        "",
        f"- Source: `{remote.get('source')}`",
        f"- Version count: `{remote.get('version_count')}`",
        f"- Tables sampled: `{remote.get('table_count_sample_capped')}`",
        "",
        "## Pending (best-effort vs repo)",
        "",
    ]
    if pending:
        lines.extend([f"- `{p}`" for p in pending])
    else:
        lines.append("- None detected (or remote catalog unavailable).")
    lines.extend(["", "## Notes", ""])
    lines.extend([f"- {n}" for n in notes] or ["- None"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "docs" / "production" / "pre_live_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)

    repo_sql = sorted(
        p.name
        for p in (root / "supabase" / "migrations").glob("*.sql")
        if p.is_file()
    )
    alembic_revs = sorted(
        p.name for p in (root / "alembic" / "versions").glob("*.py")
    )
    dsn = (
        os.environ.get("ALEMBIC_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or ""
    ).strip()

    report: dict[str, Any] = {
        "generated_at": _now(),
        "applied_migrations": False,
        "staging_verified": False,
        "production_apply_blocked": True,
        "repo_supabase_migrations_count": len(repo_sql),
        "repo_supabase_migrations": repo_sql,
        "repo_alembic_revisions": alembic_revs,
        "database_dsn_present": bool(dsn),
        "database_dsn_redacted": _redact_url(dsn) if dsn else None,
        "remote": {},
        "pending_relative_to_remote": [],
        "notes": [],
    }

    if not dsn:
        report["notes"].append("No DATABASE_URL/ALEMBIC_DATABASE_URL in environment")
        path = out_dir / "migration_audit.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (root / "docs" / "production" / "RC1_MIGRATION_REPORT.md").write_text(
            _render_md(report), encoding="utf-8"
        )
        print(json.dumps({"written": str(path), "dsn_present": False}, indent=2))
        return 2

    try:
        import asyncpg
    except ImportError:
        report["notes"].append("asyncpg not installed")
        path = out_dir / "migration_audit.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (root / "docs" / "production" / "RC1_MIGRATION_REPORT.md").write_text(
            _render_md(report), encoding="utf-8"
        )
        print(json.dumps({"written": str(path), "error": "no_asyncpg"}, indent=2))
        return 2

    remote_versions: list[str] = []

    async def _audit() -> None:
        nonlocal remote_versions
        conn = await asyncpg.connect(dsn, timeout=20)
        try:
            has_sb = await conn.fetchval(
                """
                SELECT EXISTS (
                  SELECT 1 FROM information_schema.tables
                  WHERE table_schema='supabase_migrations'
                    AND table_name='schema_migrations'
                )
                """
            )
            if has_sb:
                rows = await conn.fetch(
                    "SELECT version FROM supabase_migrations.schema_migrations "
                    "ORDER BY version"
                )
                remote_versions = [str(r["version"]) for r in rows]
                report["remote"]["source"] = (
                    "supabase_migrations.schema_migrations"
                )
            else:
                has_al = await conn.fetchval(
                    """
                    SELECT EXISTS (
                      SELECT 1 FROM information_schema.tables
                      WHERE table_schema='public'
                        AND table_name='alembic_version'
                    )
                    """
                )
                if has_al:
                    rows = await conn.fetch(
                        "SELECT version_num FROM alembic_version"
                    )
                    remote_versions = [str(r["version_num"]) for r in rows]
                    report["remote"]["source"] = "public.alembic_version"
                else:
                    report["notes"].append(
                        "No supabase_migrations.schema_migrations or "
                        "alembic_version table found"
                    )
            rows = await conn.fetch(
                """
                SELECT table_schema, table_name
                FROM information_schema.tables
                WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                ORDER BY 1, 2
                LIMIT 500
                """
            )
            report["remote"]["tables_sample"] = [
                f"{r['table_schema']}.{r['table_name']}" for r in rows
            ]
            report["remote"]["table_count_sample_capped"] = len(
                report["remote"]["tables_sample"]
            )
        finally:
            await conn.close()

    try:
        asyncio.run(_audit())
    except Exception as exc:
        report["notes"].append(f"db_connect_failed:{type(exc).__name__}")
        path = out_dir / "migration_audit.json"
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        (root / "docs" / "production" / "RC1_MIGRATION_REPORT.md").write_text(
            _render_md(report), encoding="utf-8"
        )
        print(
            json.dumps(
                {"written": str(path), "error": type(exc).__name__},
                indent=2,
            )
        )
        return 2

    report["remote"]["versions"] = remote_versions
    report["remote"]["version_count"] = len(remote_versions)
    remote_set = set(remote_versions)
    pending: list[str] = []
    for name in repo_sql:
        m = re.match(r"^(\d+)_", name)
        if not m:
            continue
        ver = m.group(1)
        if ver not in remote_set and not any(ver in rv for rv in remote_set):
            pending.append(name)
    report["pending_relative_to_remote"] = pending
    report["notes"].append(
        "Migrations NOT applied by this script. "
        "Production apply blocked until staging verification."
    )

    path = out_dir / "migration_audit.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    (root / "docs" / "production" / "RC1_MIGRATION_REPORT.md").write_text(
        _render_md(report), encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "written": str(path),
                "remote_versions": len(remote_versions),
                "pending_count": len(pending),
                "applied": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
