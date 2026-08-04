"""Signal Intelligence v2 — LIVE observation analytics (no Trading Core).

Reads multi-asset scan snapshots, persists observed signals, joins outcomes
to real closed MT5 deals, and surfaces heat map / probability / per-symbol
KPIs. Never fabricates statistics. Never mutates execution paths.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

from app.application.services.institutional_multi_asset_scanner import (
    get_last_multi_asset_scan,
)
from app.application.services.ops_state_persistence import load_ops_state, save_ops_state
from app.application.services.signal_center_service import (
    _row_from_score,
    _scores_from_scan,
    list_live_signals,
)
from app.application.services.strategy_intelligence_center import (
    _load_history_deals,
    pair_deals_into_closed_trades,
)
from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
    get_symbol_stats_book,
)
from core.logging import get_logger

logger = get_logger(__name__)

_TABLE = "signal_history"
_JOIN_WINDOW_SEC = 900


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _supabase_rest_config() -> tuple[str, str] | None:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception:
        return None
    url = (settings.supabase_url or "").strip().rstrip("/")
    if not url:
        return None
    key = ""
    if settings.supabase_service_role_key is not None:
        key = settings.supabase_service_role_key.get_secret_value().strip()
    if not key:
        api = settings.supabase_api_key
        if api is not None:
            key = api if isinstance(api, str) else str(api)
    if not key:
        return None
    return f"{url}/rest/v1", key


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        n = float(value)
        if n > 1e12:
            n /= 1000.0
        try:
            return datetime.fromtimestamp(n, tz=UTC)
        except Exception:
            return None
    s = str(value).strip()
    if not s:
        return None
    try:
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        return datetime.fromisoformat(s)
    except Exception:
        return None


def pair_all_symbol_closed_trades(deals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Pair closed trades for every symbol present in LIVE deals."""
    symbols = sorted(
        {
            str(d.get("symbol") or "").upper()
            for d in deals
            if isinstance(d, dict) and str(d.get("symbol") or "").strip()
        }
    )
    closed: list[dict[str, Any]] = []
    for sym in symbols:
        closed.extend(pair_deals_into_closed_trades(deals, symbol=sym))
    closed.sort(key=lambda t: str(t.get("exit_time") or ""), reverse=True)
    return closed


def _kpis_from_closed(trades: list[dict[str, Any]]) -> dict[str, Any]:
    wins = [t for t in trades if float(t.get("profit_loss") or 0) > 0]
    losses = [t for t in trades if float(t.get("profit_loss") or 0) < 0]
    flats = [t for t in trades if float(t.get("profit_loss") or 0) == 0]
    gp = sum(float(t.get("profit_loss") or 0) for t in wins)
    gl = abs(sum(float(t.get("profit_loss") or 0) for t in losses))
    holds = [
        float(t["holding_time_sec"])
        for t in trades
        if t.get("holding_time_sec") is not None
    ]
    n = len(wins) + len(losses)
    wr = round(100.0 * len(wins) / n, 2) if n else None
    pf = round(gp / gl, 3) if gl > 0 else (None if gp <= 0 else None)
    # Infinite PF represented as null with flag — never invent a number.
    pf_infinite = bool(gp > 0 and gl == 0)
    avg_hold_sec = round(sum(holds) / len(holds), 1) if holds else None
    return {
        "closed_trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "flats": len(flats),
        "win_rate": wr,
        "profit_factor": pf,
        "profit_factor_infinite": pf_infinite,
        "gross_profit": round(gp, 2),
        "gross_loss": round(gl, 2),
        "net_pnl": round(gp - gl, 2),
        "average_hold_sec": avg_hold_sec,
        "average_hold_minutes": round(avg_hold_sec / 60.0, 2) if avg_hold_sec else None,
        "source": "live_mt5_closed_deals",
        "fabricated": False,
    }


def _score_to_history_row(score: dict[str, Any], *, scan_as_of: str) -> dict[str, Any]:
    projected = _row_from_score(score)
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    return {
        "id": str(uuid4()),
        "observed_at": _now_iso(),
        "scan_as_of": scan_as_of,
        "symbol": projected["symbol"],
        "direction": projected["direction"],
        "badge": projected["badge"],
        "quality": projected["quality"],
        "confidence": projected["confidence"],
        "probability": projected["probability"],
        "momentum": projected["momentum"],
        "structure": projected["structure"],
        "strategy_id": projected.get("strategy"),
        "session": projected.get("session"),
        "reject": bool(projected.get("reject")),
        "blocking_gate": score.get("blocking_gate") or score.get("reject_reason"),
        "rr": projected.get("rr"),
        "expected_hold": projected.get("expected_hold"),
        "factors": factors,
        "raw_score": {
            k: score.get(k)
            for k in (
                "symbol",
                "direction",
                "trade_quality",
                "quality",
                "ai_confidence",
                "confidence",
                "reject",
                "estimated_probability",
                "opportunity_score",
            )
            if k in score
        },
        "source": "live_multi_asset_scan",
    }


def _upsert_history_postgres(rows: list[dict[str, Any]]) -> int:
    cfg = _supabase_rest_config()
    if cfg is None or not rows:
        return 0
    base, key = cfg
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "resolution=merge-duplicates,return=minimal",
    }
    payload = []
    for r in rows:
        payload.append(
            {
                "id": r.get("id") or str(uuid4()),
                "observed_at": r.get("observed_at") or _now_iso(),
                "scan_as_of": r["scan_as_of"],
                "symbol": r["symbol"],
                "direction": r.get("direction") or "NONE",
                "badge": r.get("badge"),
                "quality": r.get("quality"),
                "confidence": r.get("confidence"),
                "probability": r.get("probability"),
                "momentum": r.get("momentum"),
                "structure": r.get("structure"),
                "strategy_id": r.get("strategy_id"),
                "session": r.get("session"),
                "reject": bool(r.get("reject")),
                "blocking_gate": r.get("blocking_gate"),
                "rr": r.get("rr"),
                "expected_hold": str(r["expected_hold"])
                if r.get("expected_hold") is not None
                else None,
                "factors": r.get("factors") or {},
                "raw_score": r.get("raw_score") or {},
                "source": r.get("source") or "live_multi_asset_scan",
            }
        )
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(
                f"{base}/{_TABLE}",
                headers=headers,
                json=payload,
                params={"on_conflict": "scan_as_of,symbol"},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "signal_history_upsert_failed",
                    status=resp.status_code,
                    body=resp.text[:300],
                )
                return 0
            return len(payload)
    except Exception as exc:
        logger.warning("signal_history_upsert_error", error=str(exc))
        return 0


def _save_history_ops_fallback(rows: list[dict[str, Any]]) -> None:
    state = load_ops_state()
    existing = state.get("signal_history")
    items: list[dict[str, Any]] = []
    if isinstance(existing, dict) and isinstance(existing.get("items"), list):
        items = [x for x in existing["items"] if isinstance(x, dict)]
    by_key = {
        (str(x.get("scan_as_of")), str(x.get("symbol")).upper()): x for x in items
    }
    for r in rows:
        by_key[(str(r.get("scan_as_of")), str(r.get("symbol")).upper())] = r
    merged = sorted(
        by_key.values(),
        key=lambda x: str(x.get("observed_at") or ""),
        reverse=True,
    )[:2000]
    save_ops_state(
        {
            "signal_history": {
                "version": 1,
                "updated_at": _now_iso(),
                "items": merged,
            }
        }
    )


def _load_history_ops_fallback(
    *,
    symbol: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    state = load_ops_state()
    raw = state.get("signal_history")
    if not isinstance(raw, dict):
        return []
    items = raw.get("items")
    if not isinstance(items, list):
        return []
    out = [x for x in items if isinstance(x, dict)]
    if symbol:
        su = symbol.upper()
        out = [x for x in out if str(x.get("symbol") or "").upper() == su]
    out.sort(key=lambda x: str(x.get("observed_at") or ""), reverse=True)
    return out[:limit]


def _load_history_postgres(
    *,
    symbol: str | None = None,
    limit: int = 200,
) -> list[dict[str, Any]]:
    cfg = _supabase_rest_config()
    if cfg is None:
        return []
    base, key = cfg
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    params: dict[str, str] = {
        "select": "*",
        "order": "observed_at.desc",
        "limit": str(max(1, min(limit, 1000))),
    }
    if symbol:
        params["symbol"] = f"eq.{symbol.upper()}"
    try:
        with httpx.Client(timeout=10.0) as client:
            resp = client.get(f"{base}/{_TABLE}", headers=headers, params=params)
            if resp.status_code >= 400:
                return []
            rows = resp.json()
            return [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
    except Exception as exc:
        logger.warning("signal_history_load_failed", error=str(exc))
        return []


def observe_live_scan() -> dict[str, Any]:
    """Persist current LIVE multi-asset scan rows into signal_history."""
    scan = get_last_multi_asset_scan() or {}
    as_of = str(scan.get("as_of") or _now_iso())
    scores = _scores_from_scan(scan)
    rows = [
        _score_to_history_row(s, scan_as_of=as_of)
        for s in scores
        if str(s.get("symbol") or "").strip()
    ]
    written = _upsert_history_postgres(rows)
    _save_history_ops_fallback(rows)
    return {
        "ok": True,
        "fabricated": False,
        "scan_as_of": as_of,
        "observed": len(rows),
        "postgres_written": written,
        "source": "live_multi_asset_scan",
    }


def list_signal_history(
    *,
    symbol: str | None = None,
    direction: str | None = None,
    limit: int = 200,
    observe: bool = True,
) -> dict[str, Any]:
    if observe:
        try:
            observe_live_scan()
        except Exception:
            logger.exception("signal_history_observe_failed")
    rows = _load_history_postgres(symbol=symbol, limit=limit)
    if not rows:
        rows = _load_history_ops_fallback(symbol=symbol, limit=limit)
    if direction:
        d = direction.strip().upper()
        rows = [r for r in rows if str(r.get("direction") or "").upper() == d]
    return {
        "fabricated": False,
        "source": "signal_history",
        "count": len(rows),
        "items": rows,
    }


def build_heatmap() -> dict[str, Any]:
    scan = get_last_multi_asset_scan() or {}
    scores = _scores_from_scan(scan)
    cells = []
    for s in scores:
        projected = _row_from_score(s)
        est = s.get("estimated_probability")
        prob = float(est) if isinstance(est, (int, float)) else projected["probability"]
        cells.append(
            {
                "symbol": projected["symbol"],
                "direction": projected["direction"],
                "badge": projected["badge"],
                "quality": projected["quality"],
                "confidence": projected["confidence"],
                "probability": prob,
                "momentum": projected["momentum"],
                "structure": projected["structure"],
                "opportunity_score": s.get("opportunity_score"),
                "reject": projected["reject"],
                "heat": round(
                    (float(projected["quality"]) * 0.5)
                    + (float(projected["confidence"]) * 0.5),
                    1,
                ),
            }
        )
    cells.sort(key=lambda c: float(c.get("heat") or 0), reverse=True)
    return {
        "fabricated": False,
        "as_of": scan.get("as_of"),
        "source": "live_multi_asset_scan",
        "count": len(cells),
        "cells": cells,
    }


def build_probabilities() -> dict[str, Any]:
    heat = build_heatmap()
    items = [
        {
            "symbol": c["symbol"],
            "direction": c["direction"],
            "probability": c["probability"],
            "quality": c["quality"],
            "confidence": c["confidence"],
            "badge": c["badge"],
        }
        for c in heat.get("cells") or []
    ]
    return {
        "fabricated": False,
        "as_of": heat.get("as_of"),
        "source": "live_multi_asset_scan",
        "count": len(items),
        "items": items,
    }


def build_symbol_analytics(*, days: int = 30) -> dict[str, Any]:
    """Per-symbol WR / PF / hold from LIVE closed deals + SymbolStatsBook RR."""
    deals, meta = _load_history_deals(days=days)
    closed = pair_all_symbol_closed_trades(deals) if meta.get("ok") else []
    by_sym: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in closed:
        by_sym[str(t.get("symbol") or "").upper()].append(t)

    book_snap = get_symbol_stats_book().snapshot()
    book_by = {
        str(r.get("symbol") or "").upper(): r
        for r in (book_snap.get("symbols") or [])
        if isinstance(r, dict)
    }

    symbols = sorted(set(by_sym.keys()) | set(book_by.keys()))
    rows = []
    for sym in symbols:
        trades = by_sym.get(sym) or []
        kpis = _kpis_from_closed(trades)
        book = book_by.get(sym) or {}
        # avg_rr only when LIVE production stats recorded it — never invent.
        avg_rr = None
        try:
            wins = int(book.get("wins") or 0)
            losses = int(book.get("losses") or 0)
            rr_sum = float(book.get("rr_sum") or 0)
            rr_count = int(book.get("rr_count") or 0)
            if rr_count > 0:
                avg_rr = round(rr_sum / rr_count, 3)
            # Prefer book hold when deal pairing empty but book has closes.
            if not trades and (wins + losses) > 0:
                n = wins + losses
                kpis = {
                    **kpis,
                    "closed_trades": n,
                    "wins": wins,
                    "losses": losses,
                    "win_rate": round(100.0 * wins / n, 2) if n else None,
                    "profit_factor": (
                        round(
                            float(book.get("gross_profit") or 0)
                            / float(book.get("gross_loss") or 0),
                            3,
                        )
                        if float(book.get("gross_loss") or 0) > 0
                        else None
                    ),
                    "profit_factor_infinite": bool(
                        float(book.get("gross_profit") or 0) > 0
                        and float(book.get("gross_loss") or 0) == 0
                    ),
                    "gross_profit": round(float(book.get("gross_profit") or 0), 2),
                    "gross_loss": round(float(book.get("gross_loss") or 0), 2),
                    "net_pnl": round(
                        float(book.get("gross_profit") or 0)
                        - float(book.get("gross_loss") or 0),
                        2,
                    ),
                    "average_hold_minutes": (
                        round(
                            float(book.get("hold_minutes_sum") or 0)
                            / float(book.get("hold_count") or 1),
                            2,
                        )
                        if int(book.get("hold_count") or 0)
                        else None
                    ),
                    "source": "live_symbol_production_stats",
                    "fabricated": False,
                }
        except Exception:
            avg_rr = None
        rows.append(
            {
                "symbol": sym,
                "win_rate": kpis.get("win_rate"),
                "profit_factor": kpis.get("profit_factor"),
                "profit_factor_infinite": kpis.get("profit_factor_infinite"),
                "average_rr": avg_rr,
                "average_hold_minutes": kpis.get("average_hold_minutes"),
                "closed_trades": kpis.get("closed_trades"),
                "wins": kpis.get("wins"),
                "losses": kpis.get("losses"),
                "net_pnl": kpis.get("net_pnl"),
                "scans": book.get("scans"),
                "eligible": book.get("eligible"),
                "accepted": book.get("accepted"),
                "kpi_source": kpis.get("source"),
                "fabricated": False,
            }
        )

    rows.sort(
        key=lambda r: (
            -(float(r["win_rate"]) if r.get("win_rate") is not None else -1),
            -(int(r.get("closed_trades") or 0)),
            r["symbol"],
        )
    )
    return {
        "fabricated": False,
        "days": days,
        "deals_meta": meta,
        "count": len(rows),
        "items": rows,
        "aggregate": _kpis_from_closed(closed),
    }


def build_outcomes(*, days: int = 14, limit: int = 100) -> dict[str, Any]:
    """Soft-join observed signals to subsequent LIVE closed trades."""
    hist = list_signal_history(limit=500, observe=True)
    deals, meta = _load_history_deals(days=days)
    closed = pair_all_symbol_closed_trades(deals) if meta.get("ok") else []
    outcomes = []
    for sig in hist.get("items") or []:
        sym = str(sig.get("symbol") or "").upper()
        sig_ts = _parse_ts(sig.get("observed_at") or sig.get("scan_as_of"))
        if not sym or sig_ts is None:
            continue
        direction = str(sig.get("direction") or "").upper()
        if direction not in {"BUY", "SELL"}:
            outcomes.append(
                {
                    "symbol": sym,
                    "signal_time": sig_ts.isoformat(),
                    "direction": direction,
                    "badge": sig.get("badge"),
                    "quality": sig.get("quality"),
                    "confidence": sig.get("confidence"),
                    "probability": sig.get("probability"),
                    "join_status": "no_directional_signal",
                    "outcome": None,
                    "fabricated": False,
                }
            )
            continue
        match = None
        for trade in closed:
            if str(trade.get("symbol") or "").upper() != sym:
                continue
            entry_ts = _parse_ts(trade.get("entry_time"))
            if entry_ts is None:
                continue
            delta = (entry_ts - sig_ts).total_seconds()
            if 0 <= delta <= _JOIN_WINDOW_SEC:
                match = trade
                break
        if match is None:
            outcomes.append(
                {
                    "symbol": sym,
                    "signal_time": sig_ts.isoformat(),
                    "direction": direction,
                    "badge": sig.get("badge"),
                    "quality": sig.get("quality"),
                    "confidence": sig.get("confidence"),
                    "probability": sig.get("probability"),
                    "join_status": "unmatched",
                    "outcome": None,
                    "fabricated": False,
                }
            )
            continue
        pnl = float(match.get("profit_loss") or 0)
        outcomes.append(
            {
                "symbol": sym,
                "signal_time": sig_ts.isoformat(),
                "direction": direction,
                "badge": sig.get("badge"),
                "quality": sig.get("quality"),
                "confidence": sig.get("confidence"),
                "probability": sig.get("probability"),
                "join_status": "matched_closed_deal",
                "outcome": {
                    "profit_loss": pnl,
                    "result": "win" if pnl > 0 else ("loss" if pnl < 0 else "flat"),
                    "holding_time_sec": match.get("holding_time_sec"),
                    "entry_time": match.get("entry_time"),
                    "exit_time": match.get("exit_time"),
                    "entry": match.get("entry"),
                    "exit": match.get("exit"),
                    "side": match.get("side"),
                    "position_id": match.get("position_id"),
                },
                "fabricated": False,
            }
        )
    outcomes.sort(key=lambda o: str(o.get("signal_time") or ""), reverse=True)
    matched = [o for o in outcomes if o.get("join_status") == "matched_closed_deal"]
    return {
        "fabricated": False,
        "days": days,
        "deals_meta": meta,
        "join_window_sec": _JOIN_WINDOW_SEC,
        "count": min(len(outcomes), limit),
        "matched_count": len(matched),
        "items": outcomes[:limit],
    }


def chart_markers(symbol: str, *, limit: int = 50) -> dict[str, Any]:
    code = (symbol or "").strip().upper()
    hist = list_signal_history(symbol=code, limit=limit, observe=True)
    markers = []
    for row in hist.get("items") or []:
        ts = _parse_ts(row.get("observed_at") or row.get("scan_as_of"))
        if ts is None:
            continue
        direction = str(row.get("direction") or "NONE").upper()
        color = (
            "#16a34a"
            if direction == "BUY"
            else ("#dc2626" if direction == "SELL" else "#64748b")
        )
        markers.append(
            {
                "time": int(ts.timestamp()),
                "position": "belowBar" if direction == "BUY" else "aboveBar",
                "color": color,
                "shape": "arrowUp" if direction == "BUY" else (
                    "arrowDown" if direction == "SELL" else "circle"
                ),
                "text": f"{direction} Q{row.get('quality')} C{row.get('confidence')}",
                "symbol": code,
                "badge": row.get("badge"),
                "probability": row.get("probability"),
            }
        )
    return {
        "fabricated": False,
        "symbol": code,
        "source": "signal_history",
        "count": len(markers),
        "markers": markers,
    }


def build_overview(*, days: int = 30) -> dict[str, Any]:
    try:
        observe_live_scan()
    except Exception:
        logger.exception("si_v2_observe_on_overview_failed")
    live = list_live_signals(enabled_only=False)
    heat = build_heatmap()
    analytics = build_symbol_analytics(days=days)
    outcomes = build_outcomes(days=min(days, 14), limit=40)
    probs = build_probabilities()
    return {
        "version": "signal_intelligence_v2",
        "fabricated": False,
        "as_of": _now_iso(),
        "live_signals": {
            "count": live.get("count"),
            "dashboard": live.get("dashboard"),
            "as_of": live.get("as_of"),
        },
        "heatmap_summary": {
            "count": heat.get("count"),
            "top": (heat.get("cells") or [])[:8],
        },
        "probability_summary": {
            "count": probs.get("count"),
            "top": (probs.get("items") or [])[:8],
        },
        "analytics": analytics,
        "outcomes_summary": {
            "matched_count": outcomes.get("matched_count"),
            "count": outcomes.get("count"),
            "recent": (outcomes.get("items") or [])[:10],
        },
    }
