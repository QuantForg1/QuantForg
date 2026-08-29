"""Live execution-universe policy.

GOLD_ONLY keeps the existing XAUUSD_i autonomous lock.
BROKER_DISCOVERED uses the existing DI MT5Adapter.symbols() → GET /symbols
catalogue. Only LIVE_BROKER rows may enter the live universe.

Does not change Risk, Safety, OMS, or order_send. Does not invent symbols.
Unavailable / Mock / injected catalogues fail closed (empty universe).
"""

from __future__ import annotations

from collections.abc import Iterable
from threading import Lock
from typing import Any

from app.domain.trading.gold_only import GOLD_SYMBOL

MODE_GOLD_ONLY = "GOLD_ONLY"
MODE_BROKER_DISCOVERED = "BROKER_DISCOVERED"
MODE_FAIL_CLOSED = "FAIL_CLOSED"
CATALOGUE_LIVE_BROKER = "LIVE_BROKER"
CATALOGUE_UNAVAILABLE = "UNAVAILABLE"
CATALOGUE_INJECTED = "INJECTED"
CATALOGUE_MOCK = "MOCK"
CATALOGUE_FIXTURE = "FIXTURE"

_VALID_MODES = frozenset({MODE_GOLD_ONLY, MODE_BROKER_DISCOVERED})

_SNAP_LOCK = Lock()
_SNAPSHOT: dict[str, Any] | None = None


def reset_broker_execution_universe_for_tests() -> None:
    """Drop cached LIVE_BROKER snapshot (tests only)."""
    global _SNAPSHOT
    with _SNAP_LOCK:
        _SNAPSHOT = None


def normalize_execution_universe_mode(raw: Any) -> str:
    text = str(raw or "").strip().upper().replace("-", "_")
    if text in _VALID_MODES:
        return text
    if not text:
        return MODE_GOLD_ONLY
    return MODE_FAIL_CLOSED


def execution_universe_mode() -> str:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
        stored = str(getattr(settings, "execution_universe_mode", "") or "")
        if stored.strip().upper().replace("-", "_") == MODE_FAIL_CLOSED:
            return MODE_FAIL_CLOSED
        return normalize_execution_universe_mode(stored)
    except Exception:
        return MODE_GOLD_ONLY


def broker_discovered_enabled() -> bool:
    return execution_universe_mode() == MODE_BROKER_DISCOVERED


def execution_universe_fail_closed() -> bool:
    return execution_universe_mode() == MODE_FAIL_CLOSED


def _di_mt5_adapter() -> Any | None:
    try:
        from core.di.container import get_container

        container = get_container()
    except Exception:
        return None
    return getattr(container, "mt5_adapter", None)


def _adapter_type_names(adapter: Any) -> set[str]:
    names: set[str] = {type(adapter).__name__}
    client = getattr(adapter, "client", None) or getattr(adapter, "_client", None)
    if client is not None:
        names.add(type(client).__name__)
    return names


def classify_execution_catalogue_source(adapter: Any | None) -> str:
    """LIVE_BROKER only when the existing GatewayMT5Client chain is present."""
    if adapter is None:
        return CATALOGUE_UNAVAILABLE
    names = _adapter_type_names(adapter)
    joined = " ".join(names)
    if names & {"MockMT5Client", "MockMT5Adapter"}:
        return CATALOGUE_MOCK
    if "FIXTURE" in joined.upper() or "Fixture" in joined:
        return CATALOGUE_FIXTURE
    if "GatewayMT5Client" not in names:
        return CATALOGUE_INJECTED
    return CATALOGUE_LIVE_BROKER


def _gateway_credentials_configured() -> bool:
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception:
        return False
    url = str(getattr(settings, "mt5_gateway_base_url", "") or "").strip()
    token = str(getattr(settings, "mt5_gateway_caller_token", "") or "").strip()
    return bool(url) and bool(token)


def _unavailable_reason_without_adapter() -> str:
    if _gateway_credentials_configured():
        return "di_unavailable"
    return "gateway_credentials_unavailable"


def _row_is_disabled(row: dict[str, Any]) -> bool:
    if row.get("visible") is False or row.get("selected") is False:
        return True
    if row.get("trade_allowed") is False:
        return True
    trade_mode = row.get("trade_mode")
    try:
        mode_int = int(trade_mode) if trade_mode is not None else None
    except (TypeError, ValueError):
        mode_int = None
        text = str(trade_mode or "").strip().lower()
        if text in {"disabled", "0", "closeonly", "close_only"}:
            return True
    return mode_int == 0


def _row_is_unknown_or_unsupported(row: dict[str, Any], code: str) -> bool:
    try:
        from app.domain.market_universe.classification import classify_instrument

        classified = classify_instrument(code, broker_row=row)
        asset = str(getattr(classified, "asset_class", "") or "").upper()
        if asset == "UNKNOWN":
            return True
    except Exception:  # noqa: S110  # classifier is best-effort
        pass
    data_state = str(row.get("data_state") or row.get("status") or "").upper()
    return data_state in {"UNSUPPORTED", "DISABLED"}


def live_execution_snapshot(*, mt5_adapter: Any | None = None) -> dict[str, Any]:
    """Resolve LIVE_BROKER execution symbols via the existing adapter chain."""
    mode = execution_universe_mode()
    base: dict[str, Any] = {
        "execution_universe_mode": mode,
        "catalogue_source": CATALOGUE_UNAVAILABLE,
        "symbols": (),
        "catalogue_symbol_count": 0,
        "execution_candidate_count": 0,
        "execution_rejected_count": 0,
        "execution_unavailable_reason": None,
        "invented": False,
        "second_gateway": False,
        "discovery_method": "MT5Adapter.symbols",
        "gateway_endpoint": "GET /symbols",
    }
    if mode == MODE_FAIL_CLOSED:
        base["execution_unavailable_reason"] = "invalid_execution_universe_mode"
        return base
    if mode == MODE_GOLD_ONLY:
        from app.domain.trading.gold_only import (
            CANONICAL_GOLD_BROKER_DISPLAY,
            GOLD_SYMBOL,
            is_bare_gold_symbol,
            is_gold_symbol,
        )

        resolved = ""
        try:
            from app.domain.institutional_trading.ai_scalping import (
                universe_discovery as _ud,
            )

            resolved = _ud.resolve_canonical_market_data_symbol(GOLD_SYMBOL)
        except Exception:
            resolved = ""
        gold = (CANONICAL_GOLD_BROKER_DISPLAY,)
        if (
            resolved
            and is_gold_symbol(resolved)
            and not is_bare_gold_symbol(resolved)
        ):
            gold = (resolved,)
        base["catalogue_source"] = "GOLD_ONLY"
        base["symbols"] = gold
        base["catalogue_symbol_count"] = len(gold)
        base["execution_candidate_count"] = len(gold)
        return base

    adapter = mt5_adapter if mt5_adapter is not None else _di_mt5_adapter()
    kind = classify_execution_catalogue_source(adapter)
    if kind != CATALOGUE_LIVE_BROKER:
        base["catalogue_source"] = kind
        if kind == CATALOGUE_UNAVAILABLE:
            base["execution_unavailable_reason"] = _unavailable_reason_without_adapter()
        elif kind == CATALOGUE_MOCK:
            base["execution_unavailable_reason"] = "mock_mt5_client_not_live_broker"
        elif kind == CATALOGUE_FIXTURE:
            base["execution_unavailable_reason"] = "fixture_catalogue_not_live_broker"
        else:
            base["execution_unavailable_reason"] = "injected_catalogue_not_live_broker"
        return base
    try:
        from app.domain.market_universe.broker_catalogue import discover_live_catalogue
    except Exception:
        base["execution_unavailable_reason"] = "broker_discovery_failed"
        return base
    result = discover_live_catalogue(adapter)
    source = str(result.get("catalogue_source") or CATALOGUE_UNAVAILABLE)
    if source != CATALOGUE_LIVE_BROKER:
        base["catalogue_source"] = (
            CATALOGUE_UNAVAILABLE if source != CATALOGUE_LIVE_BROKER else source
        )
        err = str(result.get("error") or "broker_discovery_failed")
        if "credential" in err.lower():
            err = "gateway_credentials_unavailable"
        elif "not connected" in err.lower() or "unreachable" in err.lower():
            err = "gateway_unavailable"
        base["execution_unavailable_reason"] = err
        return base
    rows = tuple(result.get("rows") or ())
    symbols: list[str] = []
    rejected = 0
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            rejected += 1
            continue
        code = str(
            row.get("code") or row.get("name") or row.get("symbol") or ""
        ).strip()
        if not code:
            rejected += 1
            continue
        if _row_is_disabled(row) or _row_is_unknown_or_unsupported(row, code):
            rejected += 1
            continue
        key = code.upper()
        if key in seen:
            continue
        seen.add(key)
        symbols.append(code)
    if not symbols:
        base["catalogue_source"] = CATALOGUE_LIVE_BROKER
        base["execution_unavailable_reason"] = "empty_catalogue"
        base["execution_rejected_count"] = rejected
        return base
    base["catalogue_source"] = CATALOGUE_LIVE_BROKER
    base["symbols"] = tuple(symbols)
    base["catalogue_symbol_count"] = len(symbols)
    base["execution_candidate_count"] = len(symbols)
    base["execution_rejected_count"] = rejected
    global _SNAPSHOT
    with _SNAP_LOCK:
        _SNAPSHOT = dict(base)
    return base


def live_execution_symbols(*, mt5_adapter: Any | None = None) -> tuple[str, ...]:
    snap = live_execution_snapshot(mt5_adapter=mt5_adapter)
    if snap.get("catalogue_source") != CATALOGUE_LIVE_BROKER:
        return ()
    return tuple(str(s) for s in (snap.get("symbols") or ()) if str(s).strip())


def execution_universe_diagnostics(*, mt5_adapter: Any | None = None) -> dict[str, Any]:
    snap = live_execution_snapshot(mt5_adapter=mt5_adapter)
    return {
        "execution_universe_mode": snap.get("execution_universe_mode"),
        "catalogue_source": snap.get("catalogue_source"),
        "catalogue_symbol_count": snap.get("catalogue_symbol_count"),
        "execution_candidate_count": snap.get("execution_candidate_count"),
        "execution_rejected_count": snap.get("execution_rejected_count"),
        "execution_unavailable_reason": snap.get("execution_unavailable_reason"),
        "invented": False,
        "second_gateway": False,
        "second_scanner": False,
        "second_trading_engine": False,
    }


def canonical_execution_desks() -> frozenset[str]:
    """Live execution desks. GOLD_ONLY → gold. BROKER_DISCOVERED → LIVE_BROKER.

    DEFAULT_SCALPING_UNIVERSE is never a production live allowlist. It remains
    the testing/dev membership set only when gold-only is off and the mode is
    not BROKER_DISCOVERED / FAIL_CLOSED.
    """
    from app.domain.trading.gold_only import gold_only_enabled

    if execution_universe_fail_closed():
        return frozenset()
    if gold_only_enabled():
        return frozenset({GOLD_SYMBOL})
    if broker_discovered_enabled():
        symbols = live_execution_symbols()
        desks: set[str] = set()
        for raw in symbols:
            code = str(raw or "").strip().upper()
            if code:
                desks.add(code)
                desks.add(desk_code_for_execution(code) or code)
        return frozenset(desks)
    try:
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_SCALPING_UNIVERSE,
        )

        return frozenset(DEFAULT_SCALPING_UNIVERSE)
    except Exception:
        return frozenset()


def desk_code_for_execution(symbol: str | None) -> str:
    """Normalize broker catalogue codes to the canonical desk (USDCHF_I → USDCHF)."""
    try:
        from app.domain.institutional_trading.ai_scalping.asset_class import (
            desk_symbol_code,
        )

        return desk_symbol_code(symbol)
    except Exception:
        code = (symbol or "").strip().upper()
        if code.endswith("_I") and len(code) > 3:
            return code[:-2]
        return code


def with_broker_execution_forms(desks: Iterable[str]) -> frozenset[str]:
    """Desk codes plus known catalogue aliases. Never adds unapproved desks."""
    out: set[str] = set()
    alias_map: dict[str, tuple[str, ...]] = {}
    try:
        from app.domain.institutional_trading.ai_scalping.asset_class import (
            BROKER_SYMBOL_CANDIDATES,
        )

        alias_map = BROKER_SYMBOL_CANDIDATES
    except Exception:
        alias_map = {}
    for raw in desks:
        code = str(raw or "").strip().upper()
        if not code:
            continue
        desk = desk_code_for_execution(code) or code
        out.add(code)
        out.add(desk)
        if desk and not desk.endswith("_I"):
            out.add(f"{desk}_I")
        for alias in alias_map.get(desk, ()):
            a = str(alias or "").strip().upper()
            if a:
                out.add(a)
    return frozenset(out)


def canonical_execution_universe() -> frozenset[str]:
    """Canonical desks plus broker forms for policy membership checks."""
    if broker_discovered_enabled():
        # Exact LIVE_BROKER codes plus their canonical desks — no seed aliases.
        symbols = live_execution_symbols()
        out: set[str] = set()
        for raw in symbols:
            code = str(raw or "").strip().upper()
            if not code:
                continue
            out.add(code)
            desk = desk_code_for_execution(code)
            if desk:
                out.add(desk)
        return frozenset(out)
    return with_broker_execution_forms(canonical_execution_desks())


def execution_symbol_allowed(
    symbol: str,
    allowed: Iterable[str] | None = None,
) -> bool:
    """True when *symbol* is the same desk as an approved execution name.

    ``USDCHF`` allowlist authorizes ``USDCHF_I`` only when that form is in the
    LIVE_BROKER set (or GOLD_ONLY gold identity). Unapproved crosses stay blocked.
    """
    symbol_u = (symbol or "").strip().upper()
    if not symbol_u:
        return False
    if execution_universe_fail_closed():
        return False
    allowed_set = {
        str(s).strip().upper() for s in (allowed if allowed is not None else ()) if s
    }
    if not allowed_set:
        allowed_set = set(canonical_execution_universe())
    if not allowed_set:
        return False
    if symbol_u in allowed_set:
        return True
    desk = desk_code_for_execution(symbol_u)
    if desk and desk in allowed_set:
        return True
    return bool(desk) and any(
        desk_code_for_execution(a) == desk for a in allowed_set
    )
