"""Symbol Management — operator trading-universe preferences (UI/API/Settings).

Persists enable/disable, favorites, and scan priority. Syncs the enabled
priority-ordered list into the existing ops plane ``allowed_symbols`` so
execution continues to use the selected symbols via established control-plane
paths. Does not modify Scanner, OMS, Gateway, MT5, Risk, PME, or Strategy.
"""

from __future__ import annotations

from datetime import UTC, datetime
from threading import Lock
from typing import Any
from uuid import UUID

import httpx

from app.application.services.ops_state_persistence import (
    load_ops_state,
    save_ops_state,
)
from app.domain.institutional_trading.ai_scalping.universe_discovery import (
    classify_broker_symbol,
)
from app.domain.institutional_trading.session_filter import classify_session_utc
from core.logging import get_logger

logger = get_logger(__name__)

_TABLE = "symbol_management"
_LOCK = Lock()
_CACHE: dict[str, dict[str, Any]] = {}


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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _normalize_symbol(symbol: str) -> str:
    return (symbol or "").strip().upper()


def _default_pref(symbol: str, *, asset_class: str | None = None) -> dict[str, Any]:
    code = _normalize_symbol(symbol)
    cls = asset_class or classify_broker_symbol(code, "")
    return {
        "symbol": code,
        "enabled": True,
        "favorite": False,
        "priority": 1000,
        "asset_class": cls,
        "notes": None,
        "updated_at": _now_iso(),
        "updated_by": None,
    }


def _load_postgres_rows() -> dict[str, dict[str, Any]]:
    cfg = _supabase_rest_config()
    if cfg is None:
        return {}
    base, key = cfg
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Accept": "application/json",
    }
    try:
        with httpx.Client(timeout=8.0) as client:
            resp = client.get(
                f"{base}/{_TABLE}",
                params={"select": "*"},
                headers=headers,
            )
            if resp.status_code == 404:
                return {}
            resp.raise_for_status()
            rows = resp.json()
    except Exception as exc:
        logger.warning("symbol_management_postgres_load_failed", error=str(exc))
        return {}
    out: dict[str, dict[str, Any]] = {}
    if not isinstance(rows, list):
        return out
    for row in rows:
        if not isinstance(row, dict):
            continue
        sym = _normalize_symbol(str(row.get("symbol") or ""))
        if not sym:
            continue
        out[sym] = {
            "symbol": sym,
            "enabled": bool(row.get("enabled", True)),
            "favorite": bool(row.get("favorite", False)),
            "priority": int(row.get("priority") or 1000),
            "asset_class": str(row.get("asset_class") or "other"),
            "notes": row.get("notes"),
            "updated_at": str(row.get("updated_at") or _now_iso()),
            "updated_by": str(row["updated_by"]) if row.get("updated_by") else None,
        }
    return out


def _upsert_postgres_rows(rows: list[dict[str, Any]]) -> bool:
    cfg = _supabase_rest_config()
    if cfg is None or not rows:
        return False
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
                "symbol": r["symbol"],
                "enabled": bool(r.get("enabled", True)),
                "favorite": bool(r.get("favorite", False)),
                "priority": int(r.get("priority") or 1000),
                "asset_class": str(r.get("asset_class") or "other"),
                "notes": r.get("notes"),
                "updated_at": r.get("updated_at") or _now_iso(),
                "updated_by": r.get("updated_by"),
            }
        )
    try:
        with httpx.Client(timeout=12.0) as client:
            resp = client.post(
                f"{base}/{_TABLE}",
                headers=headers,
                json=payload,
                params={"on_conflict": "symbol"},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "symbol_management_postgres_upsert_failed",
                    status=resp.status_code,
                    body=resp.text[:300],
                )
                return False
            return True
    except Exception as exc:
        logger.warning("symbol_management_postgres_upsert_error", error=str(exc))
        return False


def _load_ops_fallback() -> dict[str, dict[str, Any]]:
    state = load_ops_state()
    raw = state.get("symbol_management")
    if not isinstance(raw, dict):
        return {}
    items = raw.get("items")
    if not isinstance(items, list):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        sym = _normalize_symbol(str(item.get("symbol") or ""))
        if not sym:
            continue
        out[sym] = {
            "symbol": sym,
            "enabled": bool(item.get("enabled", True)),
            "favorite": bool(item.get("favorite", False)),
            "priority": int(item.get("priority") or 1000),
            "asset_class": str(item.get("asset_class") or "other"),
            "notes": item.get("notes"),
            "updated_at": str(item.get("updated_at") or _now_iso()),
            "updated_by": item.get("updated_by"),
        }
    return out


def _save_ops_fallback(prefs: dict[str, dict[str, Any]]) -> None:
    items = sorted(
        prefs.values(),
        key=lambda r: (int(r.get("priority") or 1000), str(r.get("symbol") or "")),
    )
    save_ops_state(
        {
            "symbol_management": {
                "version": 1,
                "updated_at": _now_iso(),
                "items": items,
            }
        }
    )


def load_preferences(*, force: bool = False) -> dict[str, dict[str, Any]]:
    global _CACHE
    with _LOCK:
        if _CACHE and not force:
            return {k: dict(v) for k, v in _CACHE.items()}
        rows = _load_postgres_rows()
        if not rows:
            rows = _load_ops_fallback()
        _CACHE = {k: dict(v) for k, v in rows.items()}
        return {k: dict(v) for k, v in _CACHE.items()}


def _persist(prefs: dict[str, dict[str, Any]]) -> None:
    global _CACHE
    with _LOCK:
        _CACHE = {k: dict(v) for k, v in prefs.items()}
    ok = _upsert_postgres_rows(list(prefs.values()))
    _save_ops_fallback(prefs)
    if not ok:
        logger.info("symbol_management_persisted_ops_fallback_only")


def enabled_symbols_ordered(prefs: dict[str, dict[str, Any]] | None = None) -> list[str]:
    data = prefs if prefs is not None else load_preferences()
    enabled = [r for r in data.values() if bool(r.get("enabled", True))]
    enabled.sort(
        key=lambda r: (int(r.get("priority") or 1000), str(r.get("symbol") or ""))
    )
    return [str(r["symbol"]) for r in enabled]


def sync_allowed_symbols_to_plane(
    *,
    operator: Any | None = None,
    reason: str = "symbol_management_sync",
) -> list[str]:
    """Push enabled+priority list into existing ops plane allowed_symbols."""
    ordered = enabled_symbols_ordered()
    if not ordered:
        return []
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        plane = get_control_plane()
        if operator is not None:
            plane.update_auto_trade_controls(
                operator,
                allowed_symbols=tuple(ordered),
                reason=reason,
                confirmed=True,
            )
        else:
            plane.allowed_symbols = tuple(ordered)
            save_ops_state({"allowed_symbols": list(ordered)})
        logger.warning(
            "symbol_management_synced_allowed_symbols",
            count=len(ordered),
            symbols=ordered[:24],
        )
    except Exception:
        logger.exception("symbol_management_plane_sync_failed")
    return ordered


def _broker_catalogue_rows() -> list[dict[str, Any]]:
    try:
        from app.application.services.institutional_ite_runtime import get_ite_runtime

        runtime = get_ite_runtime()
        adapter = getattr(runtime, "mt5", None) or getattr(runtime, "mt5_adapter", None)
        if adapter is None:
            return []
        from app.domain.institutional_trading.ai_scalping.universe_discovery import (
            fetch_broker_symbol_rows,
        )

        return list(fetch_broker_symbol_rows(adapter) or ())
    except Exception:
        logger.exception("symbol_management_broker_catalogue_failed")
        return []


def _trade_mode_label(mode: Any) -> str:
    try:
        m = int(mode)
    except Exception:
        raw = str(mode or "").strip().lower()
        if raw in {"full", "4"}:
            return "FULL"
        if raw:
            return raw.upper()
        return "UNKNOWN"
    return {
        0: "DISABLED",
        1: "LONGONLY",
        2: "SHORTONLY",
        3: "CLOSEONLY",
        4: "FULL",
    }.get(m, str(m))


def _session_label() -> str:
    try:
        return classify_session_utc(datetime.now(UTC)).value
    except Exception:
        return "unknown"


def _ui_asset_class(code: str, cls: str) -> str:
    c = (cls or "other").lower()
    if code in {"XTIUSD", "XBRUSD"} or c == "commodities":
        return "energy" if code.startswith(("XTI", "XBR")) or "OIL" in code else c
    if c == "commodities":
        return "energy"
    return c


def list_managed_symbols(
    *,
    q: str = "",
    asset_class: str | None = None,
    enabled: bool | None = None,
    favorites_only: bool = False,
) -> dict[str, Any]:
    prefs = load_preferences()
    rows = _broker_catalogue_rows()
    session = _session_label()
    as_of = _now_iso()

    # Seed from last scan universe when broker catalogue empty (observe-only).
    if not rows:
        try:
            from app.application.services.institutional_multi_asset_scanner import (
                get_last_multi_asset_scan,
            )

            scan = get_last_multi_asset_scan() or {}
            for sym in scan.get("universe") or []:
                code = _normalize_symbol(str(sym))
                if code:
                    rows.append({"name": code, "symbol": code, "trade_mode": 4})
        except Exception:
            pass

    seen: set[str] = set()
    items: list[dict[str, Any]] = []
    for row in rows:
        code = _normalize_symbol(
            str(row.get("name") or row.get("symbol") or row.get("code") or "")
        )
        if not code or code in seen:
            continue
        seen.add(code)
        desc = str(row.get("description") or row.get("path") or "")
        cls = classify_broker_symbol(code, desc)
        ui_cls = _ui_asset_class(code, cls)
        pref = prefs.get(code) or _default_pref(code, asset_class=cls)
        trade_mode = _trade_mode_label(row.get("trade_mode"))
        tradable = trade_mode == "FULL"
        spread = row.get("spread")
        if spread is None and isinstance(row.get("raw"), dict):
            spread = row["raw"].get("spread")
        status = (
            "enabled"
            if bool(pref.get("enabled", True)) and tradable
            else ("disabled" if not pref.get("enabled", True) else "restricted")
        )
        items.append(
            {
                "symbol": code,
                "asset_class": ui_cls,
                "enabled": bool(pref.get("enabled", True)),
                "favorite": bool(pref.get("favorite", False)),
                "tradable": tradable,
                "trade_mode": trade_mode,
                "spread": spread,
                "status": status,
                "session": session,
                "last_update": pref.get("updated_at") or as_of,
                "priority": int(pref.get("priority") or 1000),
                "notes": pref.get("notes"),
            }
        )

    # Include prefs for symbols not currently in catalogue (operator history).
    for code, pref in prefs.items():
        if code in seen:
            continue
        ui_cls = _ui_asset_class(code, str(pref.get("asset_class") or "other"))
        items.append(
            {
                "symbol": code,
                "asset_class": ui_cls,
                "enabled": bool(pref.get("enabled", True)),
                "favorite": bool(pref.get("favorite", False)),
                "tradable": False,
                "trade_mode": "UNKNOWN",
                "spread": None,
                "status": "offline",
                "session": session,
                "last_update": pref.get("updated_at") or as_of,
                "priority": int(pref.get("priority") or 1000),
                "notes": pref.get("notes"),
            }
        )

    qn = (q or "").strip().upper()
    if qn:
        items = [i for i in items if qn in i["symbol"]]
    if asset_class:
        ac = asset_class.strip().lower()
        if ac == "favorites":
            favorites_only = True
        elif ac not in {"all", "*"}:
            items = [i for i in items if i["asset_class"] == ac]
    if enabled is not None:
        items = [i for i in items if bool(i["enabled"]) is enabled]
    if favorites_only:
        items = [i for i in items if bool(i["favorite"])]

    items.sort(key=lambda i: (int(i["priority"]), i["symbol"]))
    enabled_count = sum(1 for i in items if i["enabled"])
    return {
        "as_of": as_of,
        "session": session,
        "total": len(items),
        "enabled_count": enabled_count,
        "disabled_count": len(items) - enabled_count,
        "items": items,
        "enabled_symbols": enabled_symbols_ordered(prefs),
    }


def update_symbol(
    symbol: str,
    *,
    enabled: bool | None = None,
    favorite: bool | None = None,
    priority: int | None = None,
    notes: str | None = None,
    asset_class: str | None = None,
    updated_by: UUID | str | None = None,
    operator: Any | None = None,
    sync_plane: bool = True,
) -> dict[str, Any]:
    code = _normalize_symbol(symbol)
    if not code:
        raise ValueError("symbol is required")
    prefs = load_preferences(force=True)
    row = prefs.get(code) or _default_pref(code)
    if enabled is not None:
        row["enabled"] = bool(enabled)
    if favorite is not None:
        row["favorite"] = bool(favorite)
    if priority is not None:
        row["priority"] = max(1, min(10_000, int(priority)))
    if notes is not None:
        row["notes"] = notes
    if asset_class is not None:
        row["asset_class"] = str(asset_class).strip().lower() or row["asset_class"]
    row["updated_at"] = _now_iso()
    row["updated_by"] = str(updated_by) if updated_by else row.get("updated_by")
    prefs[code] = row
    _persist(prefs)
    if sync_plane:
        sync_allowed_symbols_to_plane(operator=operator, reason=f"symbol_update:{code}")
    return row


def bulk_update(
    *,
    symbols: list[str] | None = None,
    enable: bool | None = None,
    favorite: bool | None = None,
    priorities: dict[str, int] | None = None,
    updated_by: UUID | str | None = None,
    operator: Any | None = None,
) -> dict[str, Any]:
    prefs = load_preferences(force=True)
    targets = [_normalize_symbol(s) for s in (symbols or []) if _normalize_symbol(s)]
    if priorities:
        for sym, prio in priorities.items():
            code = _normalize_symbol(sym)
            if not code:
                continue
            row = prefs.get(code) or _default_pref(code)
            row["priority"] = max(1, min(10_000, int(prio)))
            row["updated_at"] = _now_iso()
            row["updated_by"] = str(updated_by) if updated_by else row.get("updated_by")
            prefs[code] = row
            if code not in targets:
                targets.append(code)
    for code in targets:
        row = prefs.get(code) or _default_pref(code)
        if enable is not None:
            row["enabled"] = bool(enable)
        if favorite is not None:
            row["favorite"] = bool(favorite)
        row["updated_at"] = _now_iso()
        row["updated_by"] = str(updated_by) if updated_by else row.get("updated_by")
        prefs[code] = row
    _persist(prefs)
    ordered = sync_allowed_symbols_to_plane(
        operator=operator, reason="symbol_management_bulk"
    )
    return {
        "updated": len(targets),
        "enabled_symbols": ordered,
        "items": [prefs[s] for s in targets if s in prefs],
    }


def reorder_priorities(
    ordered_symbols: list[str],
    *,
    updated_by: UUID | str | None = None,
    operator: Any | None = None,
) -> dict[str, Any]:
    """Assign priority 1..N from an ordered symbol list (drag-and-drop)."""
    prefs = load_preferences(force=True)
    seen: set[str] = set()
    rank = 1
    for raw in ordered_symbols:
        code = _normalize_symbol(raw)
        if not code or code in seen:
            continue
        seen.add(code)
        row = prefs.get(code) or _default_pref(code)
        row["priority"] = rank
        row["updated_at"] = _now_iso()
        row["updated_by"] = str(updated_by) if updated_by else row.get("updated_by")
        prefs[code] = row
        rank += 1
    # Push remaining enabled symbols after the ordered set.
    remain = [
        r
        for r in prefs.values()
        if r["symbol"] not in seen and bool(r.get("enabled", True))
    ]
    remain.sort(key=lambda r: (int(r.get("priority") or 1000), r["symbol"]))
    for r in remain:
        r["priority"] = rank
        r["updated_at"] = _now_iso()
        prefs[r["symbol"]] = r
        rank += 1
    _persist(prefs)
    ordered = sync_allowed_symbols_to_plane(
        operator=operator, reason="symbol_management_reorder"
    )
    return {"enabled_symbols": ordered, "count": len(seen)}
