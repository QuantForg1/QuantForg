"""Market-universe research application service.

Observes broker catalogue + last live scan. Never sends orders. Never
expands the gold-only autonomous execution universe.
"""

from __future__ import annotations

import threading
import time
from datetime import UTC, datetime
from typing import Any

from app.domain.market_universe.asset_profiles import ASSET_PROFILES
from app.domain.market_universe.broker_catalogue import (
    _is_mock_adapter,
    connection_trace,
    discover_live_catalogue,
    probe_quotes,
    probe_timeframe_history,
)
from app.domain.market_universe.classification import classify_or_unknown
from app.domain.market_universe.config_audit import build_configuration_audit
from app.domain.market_universe.constants import (
    ADVISORY_ONLY,
    ALLOW_LIVE_PROMOTION,
    CATALOGUE_ERROR,
    CATALOGUE_INJECTED,
    CATALOGUE_LIVE_BROKER,
    CATALOGUE_MOCK,
    CATALOGUE_TTL_S,
    CATALOGUE_UNAVAILABLE,
    COVERAGE_OBSERVATION_HINTS,
    FROZEN_DIRECTIONAL_EDGE,
    FROZEN_OPPORTUNITY_THRESHOLD,
    MAX_HISTORY_PROBE_SYMBOLS,
    RESEARCH_UNIVERSE_IS_NOT_EXECUTION_UNIVERSE,
    UNKNOWN,
)
from app.domain.market_universe.correlation_research import (
    analyze_portfolio_exposure,
)
from app.domain.market_universe.data_quality import evaluate_timeframe_quality
from app.domain.market_universe.expansion_architecture import describe_layers
from app.domain.market_universe.identity import canonical_desk
from app.domain.market_universe.observations import (
    current_research_stage,
    list_observations,
    record_observations,
)
from app.domain.market_universe.opportunity_board import (
    build_opportunity_board,
    global_opportunity_now,
)
from app.domain.market_universe.position_candidates import build_position_candidates
from app.domain.market_universe.promotion import research_sample_gate
from app.domain.market_universe.readiness import instrument_scorecard
from app.domain.market_universe.registry import build_registry
from app.domain.market_universe.report import build_market_universe_report
from app.domain.market_universe.research_signals import build_research_signals
from app.domain.market_universe.scheduler import (
    DEFAULT_RESEARCH_BATCH,
    MAX_RESEARCH_BATCH,
    research_scan_order,
)
from app.domain.market_universe.shadow_virtual import record_from_candidates
from app.domain.market_universe.shadow_wall import scan_package_isolation
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.RLock()
_LAST_SNAPSHOT: dict[str, Any] | None = None


def _store(payload: dict[str, Any]) -> dict[str, Any]:
    global _LAST_SNAPSHOT
    with _LOCK:
        _LAST_SNAPSHOT = dict(payload)
        return dict(_LAST_SNAPSHOT)


def get_last_market_universe_snapshot() -> dict[str, Any] | None:
    with _LOCK:
        return dict(_LAST_SNAPSHOT) if isinstance(_LAST_SNAPSHOT, dict) else None


def reset_market_universe_cache_for_tests() -> None:
    global _LAST_SNAPSHOT
    with _LOCK:
        _LAST_SNAPSHOT = None


def reset_runtime_adapter_fallback_for_tests() -> None:
    """No-op retained for tests. Research never constructs a second gateway."""
    return None


def _credential_flags() -> dict[str, Any]:
    """Booleans only. Never returns token, URL, or Authorization values."""
    flags: dict[str, Any] = {
        "gateway_url_configured": False,
        "gateway_token_configured": False,
        "token_exposed": False,
    }
    try:
        from core.config.settings import get_settings

        settings = get_settings()
    except Exception:
        return flags
    url = str(getattr(settings, "mt5_gateway_base_url", "") or "").strip()
    token = str(getattr(settings, "mt5_gateway_caller_token", "") or "").strip()
    flags["gateway_url_configured"] = bool(url)
    flags["gateway_token_configured"] = bool(token)
    return flags


def _client_of(mt5_adapter: Any) -> Any | None:
    if mt5_adapter is None:
        return None
    return getattr(mt5_adapter, "client", None) or getattr(
        mt5_adapter, "_client", None
    )


def ensure_gateway_session_for_research(mt5_adapter: Any) -> dict[str, Any]:
    """Adopt a live Windows gateway session for catalogue/market reads.

    Never constructs a second gateway. Never logs in with broker password.
    Never authorizes OMS. Returns diagnostic only.
    """
    diag: dict[str, Any] = {
        "adopted": False,
        "already_connected": False,
        "error": None,
        "authorizes_trade": False,
    }
    client = _client_of(mt5_adapter)
    if client is None:
        diag["error"] = "no_gateway_client"
        return diag
    if bool(getattr(client, "is_connected", False)):
        diag["adopted"] = True
        diag["already_connected"] = True
        return diag
    adopt = getattr(client, "adopt_existing_session", None)
    if not callable(adopt):
        diag["error"] = "adopt_unavailable"
        return diag
    try:
        ok = bool(adopt())
        diag["adopted"] = ok
        if not ok:
            diag["error"] = "MT5 gateway session not connected"
    except Exception as exc:
        diag["error"] = f"{type(exc).__name__}:{exc}"[:200]
        logger.warning("research_gateway_adopt_failed", error=diag["error"])
    return diag


def resolve_runtime_mt5_adapter() -> tuple[Any | None, dict[str, Any]]:
    """Resolve the existing DI MT5Adapter only.

    Never constructs GatewayMT5Client or MockMT5Client. Never enables
    execution. If FastAPI DI is not running, report UNAVAILABLE.
    """
    diag: dict[str, Any] = {
        "di_initialised": False,
        "mt5_adapter_found": False,
        "gateway_found": False,
        "is_mock": False,
        "client_type": UNKNOWN,
        "error": None,
        "reason": None,
        "token_exposed": False,
        "second_gateway_created": False,
        "execution_enabled": False,
        "symbol_discovery_function": UNKNOWN,
        "adapter_source": "existing_di_container",
        **_credential_flags(),
    }
    try:
        from core.di.container import get_container

        container = get_container()
    except Exception:
        diag["error"] = "di_unavailable"
        creds = bool(
            diag.get("gateway_url_configured") and diag.get("gateway_token_configured")
        )
        diag["reason"] = (
            "di_not_initialised" if creds else "gateway_credentials_unavailable"
        )
        return None, diag
    diag["di_initialised"] = True
    adapter = getattr(container, "mt5_adapter", None)
    if adapter is None:
        diag["error"] = "mt5_adapter_missing"
        diag["reason"] = "mt5_adapter_missing"
        return None, diag
    if _is_mock_adapter(adapter):
        diag["error"] = "mock_mt5_client_not_live_broker"
        diag["reason"] = "mock_mt5_client_not_live_broker"
        diag["is_mock"] = True
        diag["client_type"] = "MockMT5Client"
        return None, diag
    trace = connection_trace(adapter)
    diag["mt5_adapter_found"] = True
    diag["gateway_found"] = bool(trace.get("gateway_found"))
    diag["is_mock"] = bool(trace.get("is_mock"))
    diag["client_type"] = trace.get("client_type") or UNKNOWN
    diag["symbol_discovery_function"] = (
        trace.get("symbol_discovery_function") or "MT5Adapter.symbols"
    )
    diag["execution_enabled"] = bool(getattr(adapter, "execution_enabled", False))
    diag["gateway_available"] = bool(trace.get("gateway_found")) and not bool(
        trace.get("is_mock")
    )
    return adapter, diag


def _catalogue_reason(
    *,
    source: str,
    catalogue: dict[str, Any],
    adapter_resolution: dict[str, Any] | None,
) -> str | None:
    """Operational reason only. Never LIVE_BROKER. Never secrets."""
    if source == CATALOGUE_LIVE_BROKER:
        return None
    if adapter_resolution:
        for key in ("reason", "error"):
            val = adapter_resolution.get(key)
            if val:
                return str(val)
    err = catalogue.get("error")
    if err:
        return str(err)
    return "broker_discovery_failed"


def _cache_age_s(cached: dict[str, Any]) -> float | None:
    raw = cached.get("as_of") or cached.get("catalogue_refresh_timestamp")
    if not raw:
        return None
    try:
        ts = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=UTC)
    return max(0.0, (datetime.now(UTC) - ts).total_seconds())


def _cache_reusable(
    cached: dict[str, Any] | None,
    *,
    refresh: bool,
    mt5_adapter: Any,
    broker_rows: Any,
) -> bool:
    if refresh or broker_rows is not None or not cached:
        return False
    source = str(cached.get("catalogue_source") or "")
    live_adapter = mt5_adapter is not None and not _is_mock_adapter(mt5_adapter)
    if live_adapter and source in {
        CATALOGUE_UNAVAILABLE,
        CATALOGUE_ERROR,
        CATALOGUE_MOCK,
    }:
        return False
    if source == CATALOGUE_LIVE_BROKER:
        age = _cache_age_s(cached)
        if age is None:
            return True
        return age < CATALOGUE_TTL_S
    return True


def _news_protection() -> dict[str, Any]:
    try:
        from app.application.services.strategy_settings_audit import (
            audit_news_protection,
        )

        return audit_news_protection()
    except Exception:
        return {"STATUS": "UNWIRED", "error": True}


def _scored_rows_from_live_scan() -> list[dict[str, Any]]:
    try:
        from app.application.services.institutional_multi_asset_scanner import (
            get_last_multi_asset_scan,
        )

        payload = get_last_multi_asset_scan() or {}
    except Exception:
        payload = {}
    rows: list[dict[str, Any]] = []
    for key in ("opportunity_ranked", "ranked", "noc_rows", "rows"):
        block = payload.get(key)
        if isinstance(block, list):
            rows.extend(
                [r for r in block if isinstance(r, dict) and r.get("symbol")]
            )
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for row in rows:
        sym = str(row.get("symbol") or "").upper()
        if not sym or sym in seen:
            continue
        seen.add(sym)
        unique.append(row)
    return unique


def _row_has_numeric_opportunity(row: dict[str, Any]) -> bool:
    """True only when research produced a real opportunity number (not UNKNOWN)."""
    opp = row.get("opportunity_score")
    if isinstance(opp, bool):
        return False
    return isinstance(opp, (int, float))


def _desk_key(row: dict[str, Any]) -> str:
    return canonical_desk(
        str(row.get("canonical_symbol") or row.get("broker_symbol") or row.get("symbol") or "")
    )


def _prior_numeric_research_scores() -> list[dict[str, Any]]:
    """Carry forward numeric research scores from the last snapshot.

    Research-only persistence. Never invents scores. Rows for desks that
    are no longer in the catalogue are dropped by the merge step.
    """
    prior = get_last_market_universe_snapshot()
    if not isinstance(prior, dict):
        return []
    board = prior.get("opportunity_board") if isinstance(prior.get("opportunity_board"), dict) else {}
    candidates: list[Any] = []
    for key in ("live_ranked", "rows", "ranked"):
        block = board.get(key) if isinstance(board, dict) else None
        if isinstance(block, list):
            candidates.extend(block)
    scored_block = prior.get("scored_rows")
    if isinstance(scored_block, list):
        candidates.extend(scored_block)
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in candidates:
        if not isinstance(row, dict):
            continue
        if not _row_has_numeric_opportunity(row):
            continue
        desk = _desk_key(row)
        if not desk or desk in seen:
            continue
        seen.add(desk)
        out.append(dict(row))
    return out


def _merge_scored_seed(
    live_rows: list[dict[str, Any]],
    prior_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Prefer live numeric scores; fill gaps from prior research snapshot.

    Live stubs without a numeric opportunity do not block prior scores.
    """
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in live_rows:
        if not isinstance(row, dict):
            continue
        if not _row_has_numeric_opportunity(row):
            continue
        desk = _desk_key(row)
        if not desk or desk in seen:
            continue
        seen.add(desk)
        merged.append(row)
    for row in prior_rows:
        if not isinstance(row, dict):
            continue
        desk = _desk_key(row)
        if not desk or desk in seen:
            continue
        if not _row_has_numeric_opportunity(row):
            continue
        seen.add(desk)
        merged.append(row)
    return merged


def _last_opportunity_map(scored: list[dict[str, Any]]) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in scored:
        if not isinstance(row, dict) or not _row_has_numeric_opportunity(row):
            continue
        desk = _desk_key(row)
        if not desk:
            continue
        opp = row.get("opportunity_score")
        try:
            out[desk] = int(opp)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
    return out


def _last_analyzed_map(scored: list[dict[str, Any]]) -> dict[str, str]:
    """Map desk → last research analysis timestamp for stale-first scheduling."""
    out: dict[str, str] = {}
    for row in scored:
        if not isinstance(row, dict) or not _row_has_numeric_opportunity(row):
            continue
        desk = _desk_key(row)
        if not desk:
            continue
        stamp = (
            row.get("features_as_of")
            or row.get("analysis_timestamp")
            or row.get("as_of")
            or row.get("timestamp")
        )
        if stamp in (None, "", UNKNOWN):
            continue
        out[desk] = str(stamp)
    return out


_LAST_RESEARCH_BATCH_DIAG: dict[str, Any] = {
    "requested": [],
    "returned": 0,
    "errors": [],
    "exception": None,
    "symbols_with_numeric": 0,
    "symbols_attempted": 0,
}


def get_last_research_batch_diag() -> dict[str, Any]:
    return dict(_LAST_RESEARCH_BATCH_DIAG)


def _merge_research_batch_scores(
    scored: list[dict[str, Any]],
    *,
    mt5_adapter: Any,
    catalogue_source: str,
    schedule: dict[str, Any],
) -> list[dict[str, Any]]:
    """Extend scored rows with research batch using existing scorer.

    Does not create a second scanner. Gold-only live execution clamp stays
    intact — this path is research-only and never calls OMS.

    Rows without a numeric opportunity_score are NOT treated as already
    scored (WAIT/UNKNOWN stubs must be re-analyzed).
    """
    global _LAST_RESEARCH_BATCH_DIAG
    _LAST_RESEARCH_BATCH_DIAG = {
        "requested": [],
        "returned": 0,
        "errors": [],
        "exception": None,
        "symbols_with_numeric": 0,
        "symbols_attempted": 0,
    }
    if catalogue_source != CATALOGUE_LIVE_BROKER or mt5_adapter is None:
        return scored
    queue = schedule.get("queue") if isinstance(schedule, dict) else None
    if not isinstance(queue, list) or not queue:
        return scored
    already = {
        str(r.get("symbol") or r.get("broker_symbol") or "").upper()
        for r in scored
        if isinstance(r, dict) and _row_has_numeric_opportunity(r)
    }
    already |= {canonical_desk(s) for s in already if s}
    want: list[str] = []
    want_desks: set[str] = set()
    for item in queue:
        if not isinstance(item, dict):
            continue
        code = str(item.get("broker_symbol") or item.get("canonical_symbol") or "")
        desk = canonical_desk(code)
        if not code:
            continue
        if code.upper() in already or desk in already:
            continue
        want.append(code)
        want_desks.add(code.upper())
        if desk:
            want_desks.add(desk)
    _LAST_RESEARCH_BATCH_DIAG["requested"] = list(want)
    _LAST_RESEARCH_BATCH_DIAG["symbols_attempted"] = len(want)
    if not want:
        return scored
    try:
        from app.application.services.research_universe_scanner import (
            score_symbols_for_research,
        )

        batch = score_symbols_for_research(mt5_adapter, want)
    except Exception as exc:
        _LAST_RESEARCH_BATCH_DIAG["exception"] = f"{type(exc).__name__}:{exc}"[:200]
        logger.exception("research_batch_score_failed")
        return scored

    batch_rows = [r for r in (batch.get("rows") or ()) if isinstance(r, dict)]
    _LAST_RESEARCH_BATCH_DIAG["returned"] = len(batch_rows)
    _LAST_RESEARCH_BATCH_DIAG["errors"] = list(batch.get("errors") or [])[:20]
    _LAST_RESEARCH_BATCH_DIAG["symbols_with_numeric"] = sum(
        1 for r in batch_rows if _row_has_numeric_opportunity(r)
    )

    # Keep prior numeric scores; drop UNKNOWN stubs for desks in this batch.
    merged: list[dict[str, Any]] = []
    for row in scored:
        if not isinstance(row, dict):
            continue
        sym = str(row.get("symbol") or row.get("broker_symbol") or "").upper()
        desk = canonical_desk(sym)
        in_batch = sym in want_desks or desk in want_desks
        if in_batch and not _row_has_numeric_opportunity(row):
            continue
        merged.append(row)

    seen = {
        str(r.get("symbol") or r.get("broker_symbol") or "").upper()
        for r in merged
        if isinstance(r, dict)
    }
    seen |= {canonical_desk(s) for s in seen if s}
    for row in batch_rows:
        sym = str(row.get("symbol") or row.get("broker_symbol") or "").upper()
        desk = canonical_desk(sym)
        if not sym:
            continue
        if sym in seen or desk in seen:
            continue
        seen.add(sym)
        if desk:
            seen.add(desk)
        merged.append(row)
    return merged


def _shadow_candidates() -> list[dict[str, Any]]:
    try:
        from app.application.services.shadow_observation_pipeline import (
            shadow_dataset_snapshot,
        )

        snap = shadow_dataset_snapshot() or {}
        rows = snap.get("candidates") or snap.get("observations") or []
        return (
            [r for r in rows if isinstance(r, dict)] if isinstance(rows, list) else []
        )
    except Exception:
        return []


def _shadow_snapshot() -> dict[str, Any]:
    try:
        from app.application.services.shadow_observation_pipeline import (
            shadow_dataset_snapshot,
        )

        snap = shadow_dataset_snapshot() or {}
    except Exception:
        snap = {}
    if not isinstance(snap, dict):
        snap = {}
    snap.setdefault("advisory_only", True)
    snap.setdefault("SHADOW_ONLY", True)
    snap.setdefault("would_submit_order", False)
    snap.setdefault("ALLOW_LIVE_PROMOTION", False)
    snap.setdefault("authorizes_trade", False)
    return snap


def _matched_trades() -> list[dict[str, Any]]:
    try:
        from app.application.services.strategy_forensic_ledger import (
            STRATEGY_MATCHED,
            classify_closed_deal,
            list_closes,
        )

        closes = list_closes()
    except Exception:
        return []
    matched: list[dict[str, Any]] = []
    for row in closes or ():
        if not isinstance(row, dict):
            continue
        try:
            kind = classify_closed_deal(row)
        except Exception:
            kind = {"classification": str(row.get("match_class") or "")}
        label = (
            str(kind.get("classification") or "")
            if isinstance(kind, dict)
            else str(kind)
        )
        if label != STRATEGY_MATCHED:
            continue
        row = dict(row)
        row["match_class"] = STRATEGY_MATCHED
        matched.append(row)
    return matched


def _resolve_catalogue(
    *,
    mt5_adapter: Any,
    broker_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None,
) -> dict[str, Any]:
    """Injected rows stay INJECTED. Live adapter rows are LIVE_BROKER."""
    if broker_rows is not None:
        rows = tuple(r for r in broker_rows if isinstance(r, dict))
        return {
            "catalogue_source": CATALOGUE_INJECTED,
            "rows": rows,
            "count": len(rows),
            "error": None,
            "invented": False,
            "quotes_fetched": False,
        }
    return discover_live_catalogue(mt5_adapter)


def _probe_codes_from_rows(rows: tuple[dict[str, Any], ...]) -> list[str]:
    """Fair class-rotated probe set — never invent symbols outside the catalogue."""
    by_code: dict[str, str] = {}
    by_desk: dict[str, str] = {}
    class_buckets: dict[str, list[str]] = {
        "FOREX": [],
        "METALS": [],
        "CRYPTO": [],
        "INDICES": [],
        "ENERGY": [],
        "STOCKS": [],
        "COMMODITIES": [],
        "OTHER": [],
        "UNKNOWN": [],
    }
    for row in rows:
        code = str(row.get("code") or row.get("symbol") or "")
        if not code:
            continue
        by_code[code.upper()] = code
        desk = canonical_desk(code)
        by_desk[desk] = code
        asset = str(row.get("asset_class") or classify_or_unknown(code) or "OTHER").upper()
        if asset not in class_buckets:
            asset = "OTHER"
        if code not in class_buckets[asset]:
            class_buckets[asset].append(code)
    out: list[str] = []
    for hint in ("XAUUSD", *COVERAGE_OBSERVATION_HINTS):
        code = by_desk.get(hint) or by_code.get(hint)
        if code and code not in out:
            out.append(code)
        if len(out) >= MAX_HISTORY_PROBE_SYMBOLS:
            return out
    rotation = (
        "FOREX",
        "METALS",
        "CRYPTO",
        "INDICES",
        "ENERGY",
        "STOCKS",
        "COMMODITIES",
        "OTHER",
        "UNKNOWN",
    )
    progressed = True
    while len(out) < MAX_HISTORY_PROBE_SYMBOLS and progressed:
        progressed = False
        for asset in rotation:
            bucket = class_buckets.get(asset) or []
            while bucket and bucket[0] in out:
                bucket.pop(0)
            if not bucket:
                continue
            code = bucket.pop(0)
            if code not in out:
                out.append(code)
                progressed = True
            if len(out) >= MAX_HISTORY_PROBE_SYMBOLS:
                return out
    return out


def _unavailable_counts(counts: dict[str, Any] | None) -> dict[str, Any]:
    """Do not present empty-scan zeros as a live broker universe."""
    keys = [
        "universe",
        "FOREX",
        "CRYPTO",
        "METALS",
        "INDICES",
        "ENERGY",
        "OTHER",
        "UNKNOWN_CLASS",
        "tradable",
        "live",
        "stale",
        "no_data",
        "market_closed",
        "disabled",
        "insufficient_history",
        "unsupported",
        "error",
        "unknown",
        "data_ready",
    ]
    out = dict(counts or {})
    for key in keys:
        out[key] = CATALOGUE_UNAVAILABLE
    out["broker_counts_unavailable"] = True
    return out


def _probe_codes(instruments: list[dict[str, Any]]) -> list[str]:
    """Round-robin probe across asset classes up to MAX_HISTORY_PROBE_SYMBOLS."""
    out: list[str] = []
    gold = next(
        (i for i in instruments if i.get("canonical_symbol") == "XAUUSD"),
        None,
    )
    if gold:
        code = str(gold.get("broker_symbol") or gold.get("canonical_symbol") or "")
        if code:
            out.append(code)
    buckets: dict[str, list[str]] = {
        "FOREX": [],
        "METALS": [],
        "CRYPTO": [],
        "INDICES": [],
        "ENERGY": [],
        "STOCKS": [],
        "COMMODITIES": [],
        "OTHER": [],
        "UNKNOWN": [],
    }
    for item in instruments:
        code = str(item.get("broker_symbol") or item.get("canonical_symbol") or "")
        if not code or code in out:
            continue
        asset = str(item.get("asset_class") or "OTHER").upper()
        if asset not in buckets:
            asset = "OTHER"
        buckets[asset].append(code)
    rotation = (
        "FOREX",
        "METALS",
        "CRYPTO",
        "INDICES",
        "ENERGY",
        "STOCKS",
        "COMMODITIES",
        "OTHER",
        "UNKNOWN",
    )
    progressed = True
    while len(out) < MAX_HISTORY_PROBE_SYMBOLS and progressed:
        progressed = False
        for asset in rotation:
            bucket = buckets[asset]
            if not bucket:
                continue
            code = bucket.pop(0)
            if code not in out:
                out.append(code)
                progressed = True
            if len(out) >= MAX_HISTORY_PROBE_SYMBOLS:
                return out
    return out


def _attach_timeframes(
    instruments: list[dict[str, Any]],
    *,
    mt5_adapter: Any,
    catalogue_source: str,
) -> None:
    if catalogue_source != CATALOGUE_LIVE_BROKER or mt5_adapter is None:
        return
    try:
        frames = probe_timeframe_history(mt5_adapter, _probe_codes(instruments))
    except Exception:
        logger.exception("market_universe_history_probe_failed")
        return
    for item in instruments:
        key = str(item.get("broker_symbol") or "")
        desk = str(item.get("canonical_symbol") or "")
        raw = frames.get(key) or frames.get(desk)
        if not raw:
            continue
        quality = evaluate_timeframe_quality(raw)
        item["timeframe_quality"] = quality


def _attach_scorecards(
    instruments: list[dict[str, Any]],
    *,
    scored: list[dict[str, Any]],
    shadow_n: int,
    matched_n: int,
    queued_desks: set[str] | None = None,
) -> None:
    by_desk: dict[str, dict[str, Any]] = {}
    for row in scored:
        desk = canonical_desk(
            str(row.get("symbol") or row.get("canonical_symbol") or "")
        )
        if desk and desk not in by_desk:
            by_desk[desk] = row
    queued = queued_desks or set()
    for item in instruments:
        desk = str(item.get("canonical_symbol") or "")
        card = instrument_scorecard(
            item,
            scored=by_desk.get(desk),
            shadow_n=shadow_n,
            matched_n=matched_n,
            in_queue=desk in queued,
        )
        item["scorecard"] = card
        item["research_lifecycle"] = card.get("RESEARCH_LIFECYCLE")


def _count_dist(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    out: dict[str, int] = {}
    for row in rows:
        label = str(row.get(key) or UNKNOWN)
        out[label] = out.get(label, 0) + 1
    return out


def _open_positions(
    mt5_adapter: Any, catalogue_source: str
) -> list[dict[str, Any]] | None:
    if catalogue_source != CATALOGUE_LIVE_BROKER or mt5_adapter is None:
        return None
    if not hasattr(mt5_adapter, "list_positions"):
        return None
    try:
        raw = list(mt5_adapter.list_positions() or [])
    except Exception:
        logger.exception("market_universe_positions_observe_failed")
        return None
    out: list[dict[str, Any]] = []
    for item in raw:
        if isinstance(item, dict):
            out.append(item)
            continue
        code = str(getattr(item, "symbol", None) or getattr(item, "code", "") or "")
        if code:
            out.append({"symbol": code})
    return out


def find_instrument(
    snapshot: dict[str, Any], symbol: str
) -> dict[str, Any] | None:
    want = str(symbol or "").strip()
    if not want:
        return None
    desk = canonical_desk(want)
    upper = want.upper()
    for item in snapshot.get("instruments") or ():
        if not isinstance(item, dict):
            continue
        if str(item.get("canonical_symbol") or "") == desk:
            return item
        if str(item.get("broker_symbol") or "").upper() == upper:
            return item
        forms = {str(f).upper() for f in (item.get("broker_forms") or ())}
        if upper in forms:
            return item
    return None


def build_snapshot(
    *,
    mt5_adapter: Any = None,
    broker_rows: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
    quotes: dict[str, dict[str, Any]] | None = None,
    filters: dict[str, Any] | None = None,
    adapter_resolution: dict[str, Any] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    gateway_session = ensure_gateway_session_for_research(mt5_adapter)
    catalogue = _resolve_catalogue(mt5_adapter=mt5_adapter, broker_rows=broker_rows)
    if adapter_resolution and adapter_resolution.get("error"):
        src = str(catalogue.get("catalogue_source") or "")
        if src not in {CATALOGUE_LIVE_BROKER, CATALOGUE_INJECTED}:
            catalogue = dict(catalogue)
            catalogue["error"] = adapter_resolution.get("error")
            catalogue["invented"] = False
    if (
        gateway_session.get("error")
        and not catalogue.get("error")
        and str(catalogue.get("catalogue_source") or "")
        in {CATALOGUE_UNAVAILABLE, CATALOGUE_ERROR, ""}
    ):
        catalogue = dict(catalogue)
        catalogue["error"] = gateway_session.get("error")
    rows = tuple(catalogue.get("rows") or ())
    source = str(catalogue.get("catalogue_source") or CATALOGUE_UNAVAILABLE)
    if source == CATALOGUE_MOCK:
        source = CATALOGUE_UNAVAILABLE
        catalogue = dict(catalogue)
        catalogue["catalogue_source"] = CATALOGUE_UNAVAILABLE
        catalogue["invented"] = False
    scored = _merge_scored_seed(
        _scored_rows_from_live_scan(),
        _prior_numeric_research_scores(),
    )
    shadows = _shadow_candidates()
    matched = _matched_trades()
    news = _news_protection()
    quotes_in = dict(quotes or {})
    if source == CATALOGUE_LIVE_BROKER and mt5_adapter is not None:
        try:
            probed = probe_quotes(mt5_adapter, _probe_codes_from_rows(rows))
            for code, tick in probed.items():
                quotes_in[code] = {**quotes_in.get(code, {}), **tick}
        except Exception:
            logger.exception("market_universe_quote_probe_failed")
    registry = build_registry(rows, quotes=quotes_in)
    instruments = list(registry.get("instruments") or [])
    _attach_timeframes(
        instruments, mt5_adapter=mt5_adapter, catalogue_source=source
    )
    # Score up to MAX_RESEARCH_BATCH eligible desks per cycle; prefer
    # never-analyzed then stale-analyzed. Persistence + rotation fills coverage.
    schedule = research_scan_order(
        instruments,
        last_opportunity=_last_opportunity_map(scored),
        last_analyzed=_last_analyzed_map(scored),
        max_batch=MAX_RESEARCH_BATCH,
    )
    skipped_desks = {
        canonical_desk(str(item.get("symbol") or ""))
        for item in (schedule.get("skipped") or [])
        if isinstance(item, dict)
    }
    skipped_desks.discard("")
    if skipped_desks:
        scored = [
            row
            for row in scored
            if _desk_key(row) not in skipped_desks
        ]
    scored = _merge_research_batch_scores(
        scored,
        mt5_adapter=mt5_adapter,
        catalogue_source=source,
        schedule=schedule,
    )
    queued_desks = {
        canonical_desk(str(item.get("canonical_symbol") or ""))
        for item in (schedule.get("queue") or [])
        if isinstance(item, dict)
    }
    queued_desks.discard("")
    _attach_scorecards(
        instruments,
        scored=scored,
        shadow_n=len(shadows),
        matched_n=len(matched),
        queued_desks=queued_desks,
    )
    by_desk = {str(i.get("canonical_symbol")): i for i in instruments}
    board = build_opportunity_board(scored, registry_by_desk=by_desk, filters=filters)
    board_rows = [r for r in (board.get("rows") or []) if isinstance(r, dict)]
    live_ranked = [r for r in (board.get("live_ranked") or []) if isinstance(r, dict)]
    portfolio = analyze_portfolio_exposure(
        [str(r.get("canonical_symbol")) for r in board_rows],
        directions=[str(r.get("direction") or "") for r in board_rows],
        open_positions=_open_positions(mt5_adapter, source),
    )
    promotion_summary = _count_dist(
        [
            {"status": (i.get("scorecard") or {}).get("PROMOTION_STATUS")}
            for i in instruments
        ],
        "status",
    )
    report = build_market_universe_report(
        broker_rows=rows,
        quotes=quotes_in,
        scored_rows=scored,
        matched_trades=matched,
        shadow_candidates=shadows,
        catalogue_source=source,
        news_protection=news,
    )
    counts = registry.get("counts") or {}
    by_class = registry.get("by_class") or {}
    by_state = registry.get("by_state") or {}
    if source in {CATALOGUE_UNAVAILABLE, CATALOGUE_ERROR, CATALOGUE_MOCK}:
        counts = _unavailable_counts(counts)
        overlay = CATALOGUE_UNAVAILABLE
        by_class = dict.fromkeys(
            (
                "FOREX",
                "CRYPTO",
                "METALS",
                "INDICES",
                "ENERGY",
                "OTHER",
                "UNKNOWN",
            ),
            overlay,
        )
        by_state = dict.fromkeys(by_state or ("UNKNOWN",), overlay)
    trace = connection_trace(mt5_adapter)
    trace["gateway_session"] = gateway_session
    if gateway_session.get("error") and not catalogue.get("error"):
        # Prefer adopt failure text when catalogue already unavailable.
        if source in {CATALOGUE_UNAVAILABLE, CATALOGUE_ERROR, CATALOGUE_MOCK}:
            catalogue = dict(catalogue)
            catalogue["error"] = gateway_session.get("error")
    if source == CATALOGUE_LIVE_BROKER:
        trace["catalogue_source"] = CATALOGUE_LIVE_BROKER
        trace["broker_connection_available"] = True
    elif source in {CATALOGUE_UNAVAILABLE, CATALOGUE_ERROR, CATALOGUE_MOCK}:
        trace["catalogue_source"] = source
    if adapter_resolution:
        trace["di_initialised"] = adapter_resolution.get("di_initialised")
        trace["adapter_error"] = adapter_resolution.get("error")
        trace["adapter_reason"] = adapter_resolution.get("reason")
        trace["gateway_url_configured"] = adapter_resolution.get(
            "gateway_url_configured"
        )
        trace["gateway_token_configured"] = adapter_resolution.get(
            "gateway_token_configured"
        )
        trace["gateway_available"] = bool(
            adapter_resolution.get("gateway_available")
        )
        trace["second_gateway_created"] = False
        trace["token_exposed"] = False
        trace["adapter_source"] = adapter_resolution.get("adapter_source")
    signals = build_research_signals(live_ranked)
    candidates = build_position_candidates(live_ranked)
    record_observations(live_ranked)
    virtual = record_from_candidates(candidates)
    catalogue_down = source in {
        CATALOGUE_UNAVAILABLE,
        CATALOGUE_ERROR,
        CATALOGUE_MOCK,
    }
    if catalogue_down:
        signals = {
            **signals,
            "n": CATALOGUE_UNAVAILABLE,
            "signals": [],
            "catalogue_source": CATALOGUE_UNAVAILABLE,
        }
    global_opp = global_opportunity_now(
        catalogue_source=source, live_ranked=live_ranked
    )
    raw_signal_n = signals.get("n")
    signal_n = raw_signal_n if isinstance(raw_signal_n, int) else 0
    stage = current_research_stage(
        catalogue_source=source,
        analyzed_n=len(live_ranked),
        signal_n=signal_n,
        shadow_n=len(shadows),
        matched_n=len(matched),
    )
    elapsed_ms = int((time.perf_counter() - started) * 1000)
    failed_symbols = [
        str(i.get("broker_symbol") or i.get("canonical_symbol") or "")
        for i in instruments
        if str((i.get("data_quality") or {}).get("state") or "") == "ERROR"
    ]
    symbols_scored_n = (
        sum(
            1
            for r in scored
            if isinstance(r, dict)
            and isinstance(r.get("opportunity_score"), (int, float))
            and not isinstance(r.get("opportunity_score"), bool)
        )
        if source == CATALOGUE_LIVE_BROKER
        else None
    )
    universe_n = counts.get("universe")
    eligible_n = (
        schedule.get("eligible_n")
        if source == CATALOGUE_LIVE_BROKER and isinstance(schedule.get("eligible_n"), int)
        else None
    )
    skipped_n = (
        schedule.get("skipped_n")
        if source == CATALOGUE_LIVE_BROKER and isinstance(schedule.get("skipped_n"), int)
        else None
    )
    coverage_pct: float | str | None
    coverage_pct_catalogue: float | str | None
    if source != CATALOGUE_LIVE_BROKER:
        coverage_pct = CATALOGUE_UNAVAILABLE
        coverage_pct_catalogue = CATALOGUE_UNAVAILABLE
    else:
        # Primary coverage = analyzed / eligible (honest research readiness).
        if (
            isinstance(eligible_n, int)
            and eligible_n > 0
            and isinstance(symbols_scored_n, int)
        ):
            coverage_pct = round(
                min(100.0, max(0.0, (symbols_scored_n / float(eligible_n)) * 100.0)),
                1,
            )
        else:
            coverage_pct = None
        if (
            isinstance(universe_n, int)
            and universe_n > 0
            and isinstance(symbols_scored_n, int)
        ):
            coverage_pct_catalogue = round(
                min(100.0, max(0.0, (symbols_scored_n / float(universe_n)) * 100.0)),
                1,
            )
        else:
            coverage_pct_catalogue = None
    as_of = datetime.now(UTC).isoformat()
    payload = {
        "advisory_only": ADVISORY_ONLY,
        "authorizes_trade": False,
        "ALLOW_LIVE_PROMOTION": ALLOW_LIVE_PROMOTION,
        "research_universe_is_not_execution_universe": (
            RESEARCH_UNIVERSE_IS_NOT_EXECUTION_UNIVERSE
        ),
        "live_order_sent": False,
        "would_submit_order": False,
        "frozen_opportunity_threshold": FROZEN_OPPORTUNITY_THRESHOLD,
        "frozen_directional_edge": FROZEN_DIRECTIONAL_EDGE,
        "as_of": as_of,
        "catalogue_source": source,
        "catalogue_error": catalogue.get("error"),
        "reason": _catalogue_reason(
            source=source,
            catalogue=catalogue,
            adapter_resolution=adapter_resolution,
        ),
        "connection": trace,
        "fixture_presented_as_live": False,
        "invented_symbols": False,
        "invented": False,
        "global_market_status": counts,
        "by_class": by_class,
        "by_state": by_state,
        "instruments": instruments,
        "asset_profiles": ASSET_PROFILES,
        "opportunity_board": board,
        "research_signals": signals,
        "position_candidates": candidates,
        "shadow_virtual": virtual,
        "global_opportunity": global_opp,
        "research_observations": list_observations(limit=20),
        "research_stage": stage,
        "ranking_formula": (
            "quality + directional_edge + min(RR,5) - min(spread,20) "
            "- data_penalty(known non-LIVE only); missing terms omitted, never 0"
        ),
        "opportunity_is_not_profitability": True,
        "research_schedule": schedule,
        "session_intelligence": {
            "advisory_only": True,
            "filters_activated": False,
            "by_session": _count_dist(board_rows, "session"),
        },
        "regime_intelligence": {
            "advisory_only": True,
            "filters_activated": False,
            "by_regime": _count_dist(
                [
                    {
                        "regime": (r.get("evidence") or {}).get("REGIME")
                        or r.get("regime")
                    }
                    for r in board_rows
                ],
                "regime",
            ),
        },
        "correlation": portfolio,
        "portfolio": portfolio,
        "opportunity_distribution": _count_dist(live_ranked, "opportunity_score"),
        "edge_distribution": _count_dist(live_ranked, "directional_edge"),
        "promotion_summary": promotion_summary,
        "promotion_sample_gate": research_sample_gate(len(matched)),
        "opportunity_tier_distribution": _count_dist(
            [{"tier": r.get("opportunity_tier")} for r in live_ranked],
            "tier",
        ),
        "layers": describe_layers(),
        "scanner_health": {
            "advisory_only": True,
            "catalogue_source": source,
            "batch_size": schedule.get("batch_size"),
            "max_batch": schedule.get("max_batch"),
            "retry_backoff_s": schedule.get("retry_backoff_s"),
            "uncontrolled_polling": False,
            "second_trading_engine": False,
            "second_scanner": False,
            "collection_mode": "refresh_driven",
            "interferes_with_gold_live_scanner": False,
            "scored_from_live_scan_n": len(scored),
            "ALLOW_LIVE_PROMOTION": False,
            "isolated": scan_package_isolation().get("isolated"),
        },
        "broker_health": {
            **trace,
            "secrets_redacted": True,
            "token_exposed": False,
        },
        "news_protection": news,
        "NEWS_PROTECTION": news.get("STATUS", UNKNOWN),
        "NEWS_CONTEXT": UNKNOWN,
        "shadow": {
            "advisory_only": True,
            "SHADOW_ONLY": True,
            "n": (
                CATALOGUE_UNAVAILABLE
                if catalogue_down
                else (
                    virtual.get("n") if isinstance(virtual, dict) else len(shadows)
                )
            ),
            "completed_n": (
                CATALOGUE_UNAVAILABLE
                if catalogue_down
                else (
                    virtual.get("completed_n") if isinstance(virtual, dict) else 0
                )
            ),
            "family_n": len(shadows),
            "would_submit_order": False,
            "ALLOW_LIVE_PROMOTION": False,
            "ledger": "RESEARCH_SHADOW_ONLY",
        },
        "config_audit": build_configuration_audit(),
        "isolation": scan_package_isolation(),
        "report": report,
        "xauusd_reference": registry.get("xauusd_reference"),
        "catalogue_empty": not rows,
        "scored_from_live_scan_n": len(scored),
        "scored_rows": [
            r
            for r in scored
            if isinstance(r, dict) and _row_has_numeric_opportunity(r)
        ],
        "catalogue_refresh_timestamp": as_of,
        "observability": {
            "catalogue_refresh_timestamp": as_of,
            "refresh_timestamp": as_of,
            "catalogue_source": source,
            "catalogue_count": counts.get("universe"),
            "live_broker_count": (
                counts.get("universe")
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "asset_class_counts": by_class,
            "data_quality_counts": by_state,
            "symbol_count": counts.get("universe"),
            "symbols_discovered": counts.get("universe"),
            "symbols_eligible": (
                eligible_n
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "symbols_skipped": (
                skipped_n
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "symbols_scored": (
                symbols_scored_n
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "coverage_pct": coverage_pct,
            "coverage_pct_catalogue": coverage_pct_catalogue,
            "coverage_basis": (
                "eligible"
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "research_batch": (
                get_last_research_batch_diag()
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "symbols_research_attempted": (
                get_last_research_batch_diag().get("symbols_attempted")
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "symbols_research_returned": (
                get_last_research_batch_diag().get("returned")
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "symbols_live_ranked": (
                len(live_ranked)
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "research_batch_size": (
                schedule.get("batch_size")
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "symbols_failed": (
                len(failed_symbols)
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "research_signals": signals.get("n"),
            "shadow_candidates": (
                CATALOGUE_UNAVAILABLE
                if catalogue_down
                else (virtual.get("n") if isinstance(virtual, dict) else len(shadows))
            ),
            "shadow_virtual_trades": (
                CATALOGUE_UNAVAILABLE
                if catalogue_down
                else (
                    virtual.get("completed_n") if isinstance(virtual, dict) else 0
                )
            ),
            "gateway_available": bool(trace.get("gateway_available"))
            or bool(trace.get("gateway_found") and not trace.get("is_mock")),
            "gateway_error": catalogue.get("error")
            or (adapter_resolution or {}).get("error"),
            "reason": _catalogue_reason(
                source=source,
                catalogue=catalogue,
                adapter_resolution=adapter_resolution,
            ),
            "scan_duration_ms": elapsed_ms,
            "failed_symbols": failed_symbols if source == CATALOGUE_LIVE_BROKER else [],
            "failed_n": (
                len(failed_symbols)
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "rate_limit_events": 0,
            "last_successful_refresh": as_of
            if source == CATALOGUE_LIVE_BROKER
            else UNKNOWN,
            "last_error": catalogue.get("error"),
            "analysis_count": (
                len(live_ranked)
                if source == CATALOGUE_LIVE_BROKER
                else CATALOGUE_UNAVAILABLE
            ),
            "research_signal_count": signals.get("n"),
            "shadow_signal_count": (
                CATALOGUE_UNAVAILABLE if catalogue_down else len(shadows)
            ),
            "second_gateway": False,
            "second_scanner": False,
            "invented": False,
            "token_exposed": False,
            "catalogue_ttl_s": CATALOGUE_TTL_S,
            "discovery_uncapped": True,
            "research_score_persistence": True,
            "max_research_batch": MAX_RESEARCH_BATCH,
            "default_research_batch": DEFAULT_RESEARCH_BATCH,
        },
        "note": (
            "LIVE autonomous execution remains gold-only XAUUSD_i. "
            "This snapshot is research/intelligence. Ranked opportunities "
            "are not trade authorizations. Missing data is UNKNOWN, not 0."
        ),
    }
    return _store(payload)


def get_shadow_research_payload() -> dict[str, Any]:
    return _shadow_snapshot()


class MarketUniverseService:
    def snapshot(self, **kwargs: Any) -> dict[str, Any]:
        cached = get_last_market_universe_snapshot()
        adapter = kwargs.get("mt5_adapter")
        if _cache_reusable(
            cached,
            refresh=bool(kwargs.get("refresh")),
            mt5_adapter=adapter,
            broker_rows=kwargs.get("broker_rows"),
        ):
            return cached  # type: ignore[return-value]
        return build_snapshot(
            mt5_adapter=adapter,
            broker_rows=kwargs.get("broker_rows"),
            quotes=kwargs.get("quotes"),
            filters=kwargs.get("filters"),
            adapter_resolution=kwargs.get("adapter_resolution"),
        )

    def refresh(self, **kwargs: Any) -> dict[str, Any]:
        snap = build_snapshot(
            mt5_adapter=kwargs.get("mt5_adapter"),
            broker_rows=kwargs.get("broker_rows"),
            quotes=kwargs.get("quotes"),
            filters=kwargs.get("filters"),
            adapter_resolution=kwargs.get("adapter_resolution"),
        )
        obs = snap.get("observability") or {}
        logger.info(
            "market_universe_refresh",
            catalogue_source=snap.get("catalogue_source"),
            catalogue_count=obs.get("catalogue_count"),
            live_broker_count=obs.get("live_broker_count"),
            gateway_available=obs.get("gateway_available"),
            gateway_error=obs.get("gateway_error"),
            symbols_discovered=obs.get("symbols_discovered"),
            symbols_scored=obs.get("symbols_scored"),
            symbols_failed=obs.get("symbols_failed"),
            research_signals=obs.get("research_signals"),
            shadow_candidates=obs.get("shadow_candidates"),
            invented=False,
            token_exposed=False,
            second_gateway=False,
        )
        return snap
