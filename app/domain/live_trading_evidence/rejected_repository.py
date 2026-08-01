"""Rejected Opportunity Repository — real rejection evidence only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.live_trading_evidence.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_store = JsonDocumentStore("rejected_opportunities.json", "rejections")


def _cycle_evidence_path() -> Path:
    try:
        from core.config.settings import get_settings

        base = Path(getattr(get_settings(), "data_dir", None) or "data")
    except Exception:
        base = Path("data")
    return base / "ite_cycle_evidence.jsonl"


def _read_cycle_rejections(*, limit: int = 200) -> list[dict[str, Any]]:
    path = _cycle_evidence_path()
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if not isinstance(obj, dict):
                continue
            if (
                obj.get("rejected")
                or obj.get("event") == "trade_rejected"
                or str(obj.get("decision_action") or "").upper()
                in {
                    "NO_TRADE",
                    "WATCH",
                }
            ):
                rows.append(obj)
    except Exception:
        return []
    return rows[-limit:]


def _normalize_rejection(row: dict[str, Any], *, source: str) -> dict[str, Any]:
    reasons = row.get("reasons") if isinstance(row.get("reasons"), list) else []
    primary = (
        row.get("primary_reason")
        or row.get("reason")
        or row.get("first_blocker")
        or (reasons[0] if reasons else None)
    )
    # Never invent a reason — leave null if absent
    ctx = (
        row.get("market_context") if isinstance(row.get("market_context"), dict) else {}
    )
    return {
        "id": str(
            row.get("trace_id")
            or row.get("validation_id")
            or row.get("id")
            or new_id("rej")
        ),
        "blocking_gate": row.get("first_blocker")
        or row.get("stage")
        or row.get("cycle_outcome"),
        "reason": primary,
        "reasons": reasons if reasons else ([primary] if primary else []),
        "quality": row.get("quality_score"),
        "confidence": row.get("confluence_score") or row.get("confidence"),
        "volatility": ctx.get("atr") or row.get("volatility"),
        "liquidity": row.get("liquidity") or ctx.get("spread"),
        "session": row.get("session") or ctx.get("trading_session"),
        "symbol": row.get("symbol"),
        "timestamp": row.get("recorded_at") or row.get("timestamp") or row.get("as_of"),
        "source": source,
        "fabricated": False,
        "observe_only": True,
        "archived_at": utc_iso(),
    }


def _read_pvm_rejections(*, limit: int = 100) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    try:
        from app.domain.institutional_trading.production_validation_mode import (
            recorder as pvm_recorder,
        )

        get_production_validation_recorder = (
            pvm_recorder.get_production_validation_recorder
        )

        recorder = get_production_validation_recorder()
        for row in recorder.recent(limit=limit):
            if not isinstance(row, dict):
                continue
            reasons = row.get("no_trade_reasons") or []
            blocker = row.get("first_blocker")
            if not reasons and not blocker:
                # Skip accepted / empty
                if str(row.get("final_result") or "").upper() in {
                    "ACCEPTED",
                    "PASS",
                }:
                    continue
                if row.get("accepted") is True:
                    continue
            out.append(
                {
                    "validation_id": row.get("validation_id"),
                    "first_blocker": blocker,
                    "reasons": reasons,
                    "primary_reason": (reasons[0] if reasons else blocker),
                    "timestamp": row.get("timestamp") or row.get("started_at"),
                    "symbol": row.get("symbol"),
                    "session": row.get("session"),
                    "quality_score": row.get("quality_score"),
                    "confidence": row.get("confidence"),
                    "final_result": row.get("final_result"),
                }
            )
    except Exception:
        return []
    return out


def sync_and_list_rejections(*, limit: int = 150) -> dict[str, Any]:
    cycle_rows = _read_cycle_rejections(limit=limit)
    pvm_rows = _read_pvm_rejections(limit=limit)
    synced = 0
    for row in cycle_rows:
        norm = _normalize_rejection(row, source="cycle_evidence")
        if _store.get(str(norm["id"])) is None:
            _store.append(norm)
            synced += 1
        else:

            def mutator(_r: dict[str, Any], n: dict[str, Any] = norm) -> dict[str, Any]:
                return {**n, "id": _r.get("id") or n["id"]}

            _store.upsert(str(norm["id"]), mutator)

    for row in pvm_rows:
        norm = _normalize_rejection(row, source="production_validation_mode")
        if _store.get(str(norm["id"])) is None:
            _store.append(norm)
            synced += 1

    rows = list(reversed(_store.list(limit=limit)))
    # Drop entries with fabricated-looking empty — keep null reasons visible
    return {
        "as_of": utc_iso(),
        "rejections": rows,
        "count": len(rows),
        "synced": synced,
        "fabricated": False,
        "observe_only": True,
        "note": "Reasons shown only when recorded by production evidence",
    }
