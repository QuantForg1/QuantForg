"""Live Trade Evidence Repository — real executed trades only."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.domain.live_trading_evidence.models import TRADE_EVIDENCE_FIELDS
from app.domain.live_trading_evidence.persistence import (
    JsonDocumentStore,
    new_id,
    utc_iso,
)

_archive = JsonDocumentStore("trade_evidence_archive.json", "trades")


def _execution_history_path() -> Path:
    from app.domain.institutional_trading.execution_evidence.export import (
        EXECUTION_DIR,
        HISTORY_JSONL,
    )

    cwd = Path.cwd() / EXECUTION_DIR / HISTORY_JSONL
    if cwd.exists() or (Path.cwd() / "docs" / "production").exists():
        return Path.cwd() / EXECUTION_DIR / HISTORY_JSONL
    return Path("/workspace") / EXECUTION_DIR / HISTORY_JSONL


def _read_execution_history(*, limit: int = 200) -> list[dict[str, Any]]:
    path = _execution_history_path()
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            if isinstance(obj, dict):
                rows.append(obj)
    except Exception:
        return []
    return rows[-limit:]


def _pick(*values: Any) -> Any:
    for v in values:
        if v is not None and v != "" and v != "—":
            return v
    return None


def normalize_evidence_package(pkg: dict[str, Any]) -> dict[str, Any]:
    """Map an execution-evidence package into canonical trade evidence fields.

    Missing fields stay null — never fabricated.
    """
    ai = pkg.get("ai") if isinstance(pkg.get("ai"), dict) else {}
    risk = pkg.get("risk") if isinstance(pkg.get("risk"), dict) else {}
    mt5 = pkg.get("mt5") if isinstance(pkg.get("mt5"), dict) else {}
    broker = pkg.get("broker") if isinstance(pkg.get("broker"), dict) else {}
    trade = pkg.get("trade") if isinstance(pkg.get("trade"), dict) else {}
    gw = pkg.get("gateway") if isinstance(pkg.get("gateway"), dict) else {}
    oms = pkg.get("oms") if isinstance(pkg.get("oms"), dict) else {}

    ticket = _pick(mt5.get("ticket"), pkg.get("mt5_ticket"), pkg.get("ticket"))
    validation_id = _pick(pkg.get("validation_id"))
    trade_id = str(ticket or validation_id or new_id("trade"))

    latency = _pick(
        gw.get("order_send_latency_ms"),
        oms.get("latency_ms"),
        pkg.get("execution_latency_ms"),
    )

    evidence = {
        "id": f"ev_{trade_id}",
        "trade_id": trade_id,
        "decision_id": _pick(pkg.get("signal_id"), validation_id),
        "validation_id": validation_id,
        "mt5_ticket": ticket,
        "symbol": _pick(ai.get("symbol"), pkg.get("symbol"), trade.get("symbol")),
        "direction": _pick(ai.get("decision"), pkg.get("decision")),
        "entry": _pick(
            trade.get("entry"), mt5.get("fill_price"), broker.get("final_fill")
        ),
        "exit": _pick(trade.get("exit")),
        "lot": _pick(mt5.get("volume"), risk.get("position_size")),
        "risk_pct": _pick(risk.get("risk_pct"), risk.get("risk_score")),
        "quality": _pick(ai.get("quality_score"), pkg.get("quality_score")),
        "confidence": _pick(ai.get("confidence"), pkg.get("confidence")),
        "mtf": _pick(pkg.get("mtf"), ai.get("mtf")),
        "liquidity": _pick(pkg.get("liquidity"), ai.get("liquidity")),
        "volatility": _pick(pkg.get("volatility"), ai.get("volatility")),
        "execution_score": _pick(
            pkg.get("execution_score"), broker.get("execution_status")
        ),
        "slippage": _pick(broker.get("slippage"), pkg.get("slippage")),
        "latency": latency,
        "session": _pick(ai.get("session"), pkg.get("session")),
        "market_regime": _pick(pkg.get("market_regime"), ai.get("regime")),
        "management_events": pkg.get("management_events")
        if isinstance(pkg.get("management_events"), list)
        else [],
        "close_reason": _pick(trade.get("close_reason"), pkg.get("close_reason")),
        "pnl": _pick(trade.get("net_pnl"), trade.get("gross_pnl")),
        "duration": _pick(trade.get("duration")),
        "timeline": pkg.get("timeline")
        if isinstance(pkg.get("timeline"), list)
        else [],
        "oms": oms,
        "gateway": gw,
        "mt5": mt5,
        "broker": broker,
        "ai": ai,
        "risk": risk,
        "final_result": pkg.get("final_result"),
        "accepted": pkg.get("accepted"),
        "timestamp": _pick(pkg.get("timestamp"), utc_iso()),
        "source": "execution_evidence",
        "fabricated": False,
        "observe_only": True,
        "archived_at": utc_iso(),
    }
    # Ensure every canonical field is present
    for field in TRADE_EVIDENCE_FIELDS:
        evidence.setdefault(field, None)
    return evidence


def _archive_trade(evidence: dict[str, Any]) -> dict[str, Any]:
    doc_id = str(evidence.get("id") or evidence.get("trade_id"))
    existing = _archive.get(doc_id)
    if existing is None:
        # try ticket / validation match
        for key in (
            str(evidence.get("trade_id") or ""),
            str(evidence.get("mt5_ticket") or ""),
            str(evidence.get("validation_id") or ""),
        ):
            if key:
                existing = _archive.get(key)
                if existing:
                    break
    if existing is None:
        return _archive.append(evidence)

    def mutator(_row: dict[str, Any]) -> dict[str, Any]:
        merged = dict(evidence)
        merged["id"] = existing.get("id") or doc_id
        return merged

    updated = _archive.upsert(str(existing.get("id") or doc_id), mutator)
    return updated or evidence


def sync_and_list_trades(*, limit: int = 100) -> dict[str, Any]:
    """Pull latest execution evidence packages into archive; list trades."""
    history = _read_execution_history(limit=limit)
    # Also try latest package
    try:
        from app.domain.institutional_trading.execution_evidence.export import (
            load_latest_evidence,
        )

        latest = load_latest_evidence()
        pkg = latest.get("latest") if isinstance(latest, dict) else None
        if isinstance(pkg, dict) and pkg.get("validation_id"):
            # Prefer packages with real ticket when present
            history = [*history, pkg]
    except Exception:  # noqa: S110
        pass

    seen: set[str] = set()
    synced = 0
    for pkg in history:
        if not isinstance(pkg, dict):
            continue
        # Only archive real executions (ticket or accepted)
        mt5 = pkg.get("mt5") if isinstance(pkg.get("mt5"), dict) else {}
        ticket = mt5.get("ticket") or pkg.get("mt5_ticket")
        accepted = bool(pkg.get("accepted") or pkg.get("certificate_eligible"))
        if ticket is None and not accepted:
            continue
        evidence = normalize_evidence_package(pkg)
        key = str(evidence.get("trade_id"))
        if key in seen:
            continue
        seen.add(key)
        _archive_trade(evidence)
        synced += 1

    rows = list(reversed(_archive.list(limit=limit)))
    return {
        "as_of": utc_iso(),
        "trades": rows,
        "count": len(rows),
        "synced_from_execution_evidence": synced,
        "archive_count": _archive.count(),
        "fabricated": False,
        "observe_only": True,
        "note": (
            "Empty archive means no eligible production execution packages yet "
            "— never fabricated"
        ),
    }


def get_trade(trade_id: str) -> dict[str, Any] | None:
    sync_and_list_trades(limit=50)
    return _archive.get(trade_id)


def list_archived_trades(*, limit: int = 100) -> list[dict[str, Any]]:
    return list(reversed(_archive.list(limit=limit)))
