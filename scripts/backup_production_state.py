#!/usr/bin/env python3
"""Backup production state artifacts (research archives, peak equity, ops audit).

Does not invent data. Copies local durable artifacts into a timestamped directory.
Postgres dumps remain operator-driven via BACKUP_RECOVERY.md / pg_dump.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _copy_if_exists(src: Path, dest: Path) -> bool:
    if not src.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    if src.is_dir():
        shutil.copytree(src, dest, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest)
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="QuantForg production state backup")
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Backup root directory",
    )
    args = parser.parse_args()

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = args.out or (ROOT / "backups" / f"qf_state_{stamp}")
    out.mkdir(parents=True, exist_ok=True)

    namespaces = [
        "research",
        "trade_history",
        "risk_state",
        "peak_equity",
        "llp",
        "ivp",
        "prc",
        "rmip",
        "audit",
    ]
    manifest: dict[str, object] = {
        "generated_at": datetime.now(UTC).isoformat(),
        "items": {},
        "postgres": "Use pg_dump / Supabase PITR — see BACKUP_RECOVERY.md",
        "namespaces": namespaces,
    }

    candidates = {
        "peak_equity": ROOT / ".quantforg_state" / "live_account_risk.json",
        "risk_state": ROOT / ".quantforg_state",
        "openapi": ROOT / "openapi" / "openapi.v1.0.0.json",
    }
    items: dict[str, object] = {}
    for name, path in candidates.items():
        dest = out / name
        if path.is_file():
            dest = out / f"{name}{path.suffix}"
        ok = _copy_if_exists(path, dest)
        items[name] = {"source": str(path), "copied": ok}

    try:
        sys.path.insert(0, str(ROOT))
        from app.domain.integration_sprint_v1.durable_store import (
            NAMESPACES,
            DurableResearchStore,
        )

        store = DurableResearchStore()
        dump = {ns: store.list(ns, limit=10_000) for ns in NAMESPACES}
        path = out / "durable_store_snapshot.json"
        path.write_text(json.dumps(dump, indent=2, default=str), encoding="utf-8")
        items["durable_store_snapshot"] = {
            "source": "DurableResearchStore (process-local)",
            "copied": True,
            "namespaces": list(NAMESPACES),
            "note": (
                "For live archive, export from running API "
                "process memory or Postgres audits"
            ),
        }
    except Exception as exc:
        items["durable_store_snapshot"] = {
            "copied": False,
            "error": str(exc)[:200],
        }

    manifest["items"] = items
    (out / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "backup": str(out)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
