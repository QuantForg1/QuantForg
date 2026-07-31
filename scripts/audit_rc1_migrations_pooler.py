#!/usr/bin/env python3
"""Read-only RC1 migration audit via DATABASE_URL (pooler-safe).

Never applies migrations. Never prints credentials.
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


def _redact(url: str) -> str:
    try:
        parsed = urlparse(url)
        host = parsed.hostname or ""
        port = parsed.port or ""
        db = (parsed.path or "").lstrip("/")
        return f"{parsed.scheme}://***@{host}:{port}/{db}"
    except Exception:
        return "[REDACTED_DSN]"


def _ver_of(name: str) -> str:
    match = re.match(r"^(\d+)", name)
    return match.group(1) if match else name


def _render_md(report: dict[str, Any]) -> str:
    pending = report.get("pending_relative_to_remote") or []
    extra = report.get("extra_on_remote_not_in_repo") or []
    notes = report.get("notes") or []
    remote = report.get("remote") or {}
    lines = [
        "# RC1 Migration Audit (Infra Recovery)",
        "",
        f"Generated: `{report.get('generated_at')}`",
        "",
        "## Policy",
        "",
        "- Migrations were **NOT** applied.",
        "- Production apply remains blocked.",
        "- No automatic migrations.",
        "",
        "## Connectivity",
        "",
        f"- DSN present: `{report.get('database_dsn_present')}`",
        f"- DSN (redacted): `{report.get('database_dsn_redacted')}`",
        f"- Remote source: `{remote.get('source')}`",
        f"- Remote version count: `{remote.get('version_count')}`",
        f"- Public/supabase tables: `{remote.get('table_count_sample')}`",
        "",
        "## Repo",
        "",
        f"- Supabase up migrations: `{report.get('repo_supabase_migrations_count')}`",
        f"- Alembic: `{report.get('repo_alembic_revisions')}`",
        "",
        "## Pending vs remote (repo not on remote)",
        "",
    ]
    if pending:
        lines.extend([f"- `{p}`" for p in pending])
    else:
        lines.append("- None")
    lines.extend(["", "## Extra on remote (not in repo filenames)", ""])
    if extra:
        lines.extend([f"- `{e}`" for e in extra])
    else:
        lines.append("- None")
    lines.extend(["", "## Notes", ""])
    lines.extend([f"- {n}" for n in notes] or ["- None"])
    lines.append("")
    return "\n".join(lines)


async def _audit(dsn: str, repo_sql: list[str]) -> dict[str, Any]:
    import asyncpg

    conn = await asyncpg.connect(dsn=dsn, timeout=20)
    try:
        rows = await conn.fetch(
            "select version, name, created_by "
            "from supabase_migrations.schema_migrations order by version"
        )
        remote_versions = [r["version"] for r in rows]
        remote_names = {r["version"]: (r["name"] or "") for r in rows}
        tables = await conn.fetch(
            """
            select table_schema, table_name
            from information_schema.tables
            where table_schema in ('public', 'supabase_migrations')
              and table_type = 'BASE TABLE'
            order by 1, 2
            """
        )
        repo_vers = {_ver_of(n): n for n in repo_sql}
        remote_set = set(remote_versions)
        pending = [repo_vers[v] for v in sorted(repo_vers) if v not in remote_set]
        extra = [v for v in remote_versions if v not in repo_vers]
        return {
            "remote": {
                "source": "supabase_migrations.schema_migrations via DATABASE_URL",
                "version_count": len(remote_versions),
                "versions": remote_versions,
                "names_by_version": remote_names,
                "table_count_sample": len(tables),
                "tables": [f"{t['table_schema']}.{t['table_name']}" for t in tables],
            },
            "pending_relative_to_remote": pending,
            "extra_on_remote_not_in_repo": extra,
        }
    finally:
        await conn.close()


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    out_dir = root / "docs" / "production" / "infra_recovery_evidence"
    out_dir.mkdir(parents=True, exist_ok=True)
    pre_live = root / "docs" / "production" / "pre_live_evidence"
    pre_live.mkdir(parents=True, exist_ok=True)

    repo_sql = sorted(
        p.name
        for p in (root / "supabase" / "migrations").glob("*.sql")
        if p.is_file()
    )
    alembic_revs = sorted(
        p.name for p in (root / "alembic" / "versions").glob("*.py")
    )
    dsn = (
        os.environ.get("DATABASE_URL") or os.environ.get("ALEMBIC_DATABASE_URL") or ""
    ).strip()

    report: dict[str, Any] = {
        "generated_at": _now(),
        "mission": "INFRASTRUCTURE_RECOVERY_RC1",
        "applied_migrations": False,
        "production_apply_blocked": True,
        "staging_verified": False,
        "database_dsn_present": bool(dsn),
        "database_dsn_redacted": _redact(dsn) if dsn else None,
        "repo_supabase_migrations_count": len(repo_sql),
        "repo_supabase_migrations": repo_sql,
        "repo_alembic_revisions": alembic_revs,
        "remote": {},
        "pending_relative_to_remote": [],
        "extra_on_remote_not_in_repo": [],
        "notes": [],
    }

    if not dsn:
        report["notes"].append("no DATABASE_URL")
    else:
        try:
            audited = asyncio.run(_audit(dsn, repo_sql))
            report.update(audited)
            pending = report["pending_relative_to_remote"]
            extra = report["extra_on_remote_not_in_repo"]
            if pending:
                report["notes"].append(
                    f"{len(pending)} repo migrations not present on remote "
                    "(do NOT auto-apply to production)"
                )
            else:
                report["notes"].append(
                    "all repo supabase migration versions appear present on remote"
                )
            if extra:
                report["notes"].append(
                    f"{len(extra)} remote versions not found as repo filenames"
                )
            report["notes"].append("migrations NOT applied by this audit")
        except Exception as exc:  # noqa: BLE001 — evidence collector
            report["notes"].append(f"db_connect_failed:{type(exc).__name__}")

    md = _render_md(report)
    (out_dir / "migration_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (out_dir / "RC1_MIGRATION_AUDIT.md").write_text(md, encoding="utf-8")
    (pre_live / "migration_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (root / "docs" / "production" / "RC1_MIGRATION_REPORT.md").write_text(
        md, encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "written": str(out_dir / "migration_audit.json"),
                "remote_count": (report.get("remote") or {}).get("version_count"),
                "pending": report.get("pending_relative_to_remote"),
                "applied": False,
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
