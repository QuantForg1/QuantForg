"""Backup & Recovery — status, restore verification, DR checklist (non-destructive)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.domain.production_reliability.persistence import (
    JsonDocumentStore,
    data_path,
    new_id,
    utc_iso,
)

_evidence = JsonDocumentStore("recovery_evidence.json", "evidence")

# Observe-only DR checklist — no execution of destructive restore
DR_CHECKLIST: tuple[dict[str, str], ...] = (
    {"id": "dr1", "item": "Confirm backup artifact exists and checksum recorded"},
    {"id": "dr2", "item": "Verify restore dry-run evidence (non-destructive)"},
    {"id": "dr3", "item": "Validate database connectivity post-restore window"},
    {"id": "dr4", "item": "Validate Redis / cache connectivity"},
    {"id": "dr5", "item": "Validate API /health and /ready"},
    {"id": "dr6", "item": "Validate gateway reachability (observe-only)"},
    {"id": "dr7", "item": "Confirm MT5 session status without reconnect storms"},
    {"id": "dr8", "item": "Confirm frontend production URL serves"},
    {"id": "dr9", "item": "Record recovery evidence and operator sign-off"},
    {"id": "dr10", "item": "Never run destructive wipe / force-drop in this console"},
)


def _backup_dir() -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / "backups"


def build_backup_status() -> dict[str, Any]:
    """Inspect backup directory presence — never deletes or restores."""
    bdir = _backup_dir()
    artifacts: list[dict[str, Any]] = []
    if bdir.exists() and bdir.is_dir():
        entries = sorted(bdir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)[
            :25
        ]
        for p in entries:
            try:
                st = p.stat()
                artifacts.append(
                    {
                        "name": p.name,
                        "path": str(p),
                        "size_bytes": st.st_size,
                        "modified_at": utc_iso(),  # refreshed as_of; mtime below
                        "mtime_epoch": st.st_mtime,
                        "is_file": p.is_file(),
                    }
                )
            except Exception:  # noqa: S112  # best-effort optional path
                continue

    program_store = data_path(".")
    return {
        "as_of": utc_iso(),
        "backup_directory": str(bdir),
        "backup_directory_exists": bdir.exists(),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "program_data_dir": str(program_store.parent),
        "destructive_ops_forbidden": True,
        "restore_executed": False,
        "note": "Status only — this surface never runs destructive restore",
        "fabricated": False,
    }


def build_restore_verification() -> dict[str, Any]:
    """Non-destructive restore verification checklist results from evidence store."""
    evidence = list(reversed(_evidence.list(limit=50)))
    latest = evidence[0] if evidence else None
    return {
        "as_of": utc_iso(),
        "latest_verification": latest,
        "evidence_count": len(evidence),
        "evidence": evidence,
        "destructive_ops_forbidden": True,
        "fabricated": False,
    }


def record_recovery_evidence(
    *,
    checklist_id: str,
    result: str,
    notes: str = "",
    operator: str = "operator",
) -> dict[str, Any]:
    """Append recovery evidence — never performs restore."""
    doc = {
        "id": new_id("ev"),
        "checklist_id": (checklist_id or "")[:64],
        "result": (result or "observed")[:64],
        "notes": (notes or "")[:2000],
        "operator": operator,
        "at": utc_iso(),
        "destructive_ops_forbidden": True,
        "fabricated": False,
    }
    return _evidence.append(doc)


def build_disaster_recovery() -> dict[str, Any]:
    evidence = _evidence.list(limit=200)
    checked = {
        str(e.get("checklist_id")) for e in evidence if e.get("result") == "pass"
    }
    items = []
    for row in DR_CHECKLIST:
        items.append(
            {
                **row,
                "evidence_pass": row["id"] in checked,
            }
        )
    return {
        "as_of": utc_iso(),
        "checklist": items,
        "passed_count": sum(1 for i in items if i["evidence_pass"]),
        "total": len(items),
        "backup_status": build_backup_status(),
        "restore_verification": build_restore_verification(),
        "destructive_ops_forbidden": True,
        "fabricated": False,
    }
