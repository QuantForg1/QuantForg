"""Market Universe research API — observe/refresh catalogue. Never order_send."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Query
from pydantic import BaseModel, Field

from app.application.services.market_universe_service import (
    MarketUniverseService,
    find_instrument,
    resolve_runtime_mt5_adapter,
)
from app.presentation.dependencies.auth import CurrentUser

router = APIRouter(
    prefix="/market-universe",
    tags=["market-universe"],
)

_service = MarketUniverseService()


class UniverseFilters(BaseModel):
    asset_class: str | None = None
    symbol: str | None = None
    direction: str | None = None
    session: str | None = None
    regime: str | None = None
    min_opportunity: int | None = Field(default=None, ge=0, le=100)
    min_edge: int | None = Field(default=None, ge=0, le=100)
    min_rr: float | None = Field(default=None, ge=0)
    data_freshness: str | None = None
    setup: str | None = None


def _snap_call(**extra: Any) -> dict[str, Any]:
    adapter, diag = resolve_runtime_mt5_adapter()
    return _research_envelope(
        _service.snapshot(
            mt5_adapter=adapter, adapter_resolution=diag, **extra
        )
    )


def _research_envelope(payload: dict[str, Any]) -> dict[str, Any]:
    out = dict(payload)
    out.setdefault("advisory_only", True)
    out.setdefault("authorizes_trade", False)
    out.setdefault("would_submit_order", False)
    out.setdefault("ALLOW_LIVE_PROMOTION", False)
    return out


@router.get("")
@router.get("/snapshot")
async def market_universe_snapshot(
    user: CurrentUser,
    refresh: bool = Query(default=False),
) -> dict[str, Any]:
    _ = user
    return _snap_call(refresh=refresh)


@router.get("/registry")
async def market_universe_registry(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "catalogue_source": snap.get("catalogue_source"),
        "counts": snap.get("global_market_status"),
        "by_class": snap.get("by_class"),
        "by_state": snap.get("by_state"),
        "instruments": snap.get("instruments") or [],
        "xauusd_reference": snap.get("xauusd_reference"),
        "catalogue_empty": snap.get("catalogue_empty"),
        "NEWS_PROTECTION": snap.get("NEWS_PROTECTION"),
    }


@router.get("/opportunities")
async def market_universe_opportunities(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    board = snap.get("opportunity_board") or {}
    return {
        "advisory_only": True,
        "authorizes_trade": False,
        "ranking_is_research_only": True,
        "catalogue_source": snap.get("catalogue_source"),
        **board,
    }


@router.post("/opportunities/filter")
async def market_universe_filter(
    body: UniverseFilters, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    adapter, diag = resolve_runtime_mt5_adapter()
    return _research_envelope(
        _service.refresh(
            filters=body.model_dump(),
            mt5_adapter=adapter,
            adapter_resolution=diag,
        )
    )


@router.get("/report")
async def market_universe_report(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    return snap.get("report") or {"advisory_only": True, "empty": True}


@router.get("/config-audit")
async def market_universe_config_audit(user: CurrentUser) -> dict[str, Any]:
    _ = user
    from app.domain.market_universe.config_audit import build_configuration_audit

    return build_configuration_audit()


@router.get("/shadow")
async def market_universe_shadow(user: CurrentUser) -> dict[str, Any]:
    _ = user
    from app.application.services.market_universe_service import (
        get_shadow_research_payload,
    )

    snap = _snap_call()
    payload = get_shadow_research_payload()
    return _research_envelope(
        {
            "SHADOW_ONLY": True,
            "n": payload.get("virtual_completed")
            or payload.get("observations")
            or snap.get("shadow", {}).get("n")
            or 0,
            "catalogue_source": snap.get("catalogue_source"),
            **payload,
        }
    )


@router.get("/performance")
async def market_universe_performance(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    report = snap.get("report") or {}
    return _research_envelope(
        {
            "STRATEGY_MATCHED_SAMPLE": report.get("19_STRATEGY_MATCHED_SAMPLE"),
            "by_asset_class": report.get("20_PERFORMANCE_BY_ASSET_CLASS"),
            "by_symbol": report.get("21_PERFORMANCE_BY_SYMBOL"),
            "by_session": report.get("22_PERFORMANCE_BY_SESSION"),
            "by_regime": report.get("23_PERFORMANCE_BY_REGIME"),
            "by_setup": report.get("24_PERFORMANCE_BY_SETUP"),
            "by_opportunity_band": report.get("31_BY_OPPORTUNITY_BAND"),
            "by_edge_band": report.get("32_BY_EDGE_BAND"),
            "by_rr_band": report.get("33_BY_RR_BAND"),
            "by_volatility": report.get("34_BY_VOLATILITY"),
            "by_spread_band": report.get("35_BY_SPREAD_BAND"),
            "oos": report.get("25_OOS"),
            "walk_forward": report.get("26_WALK_FORWARD"),
            "shadow_sample_size": report.get("18_SHADOW_SAMPLE_SIZE"),
            "unmatched_broker_activity_is_not_strategy_pnl": True,
        }
    )


@router.get("/by-class")
async def market_universe_by_class(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    board = snap.get("opportunity_board") or {}
    return _research_envelope(
        {
            "catalogue_source": snap.get("catalogue_source"),
            "by_class": snap.get("by_class"),
            "counts": snap.get("global_market_status"),
            "top_by_asset_class": board.get("top_by_asset_class") or {},
        }
    )


@router.get("/by-session")
async def market_universe_by_session(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    board = snap.get("opportunity_board") or {}
    return _research_envelope(
        {
            "catalogue_source": snap.get("catalogue_source"),
            "session_intelligence": snap.get("session_intelligence"),
            "top_by_session": board.get("top_by_session") or {},
            "filters_activated": False,
        }
    )


@router.get("/by-regime")
async def market_universe_by_regime(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    board = snap.get("opportunity_board") or {}
    return _research_envelope(
        {
            "catalogue_source": snap.get("catalogue_source"),
            "regime_intelligence": snap.get("regime_intelligence"),
            "top_by_regime": board.get("top_by_regime") or {},
            "filters_activated": False,
        }
    )


@router.get("/correlation")
async def market_universe_correlation(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    return _research_envelope(
        {
            "catalogue_source": snap.get("catalogue_source"),
            "correlation": snap.get("correlation"),
            "portfolio": snap.get("portfolio"),
            "bypasses_risk": False,
        }
    )


@router.get("/health")
async def market_universe_health(user: CurrentUser) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    return _research_envelope(
        {
            "catalogue_source": snap.get("catalogue_source"),
            "broker_health": snap.get("broker_health"),
            "scanner_health": snap.get("scanner_health"),
            "isolation": snap.get("isolation"),
            "layers": snap.get("layers"),
            "observability": snap.get("observability"),
            "token_exposed": False,
        }
    )


@router.get("/instrument/{symbol}")
@router.get("/{symbol}")
async def market_universe_instrument(
    symbol: str, user: CurrentUser
) -> dict[str, Any]:
    _ = user
    snap = _snap_call()
    item = find_instrument(snap, symbol)
    board = snap.get("opportunity_board") or {}
    scored = None
    for row in board.get("rows") or ():
        if isinstance(row, dict) and str(row.get("canonical_symbol")) == (
            item or {}
        ).get("canonical_symbol"):
            scored = row
            break
    return _research_envelope(
        {
            "found": item is not None,
            "catalogue_source": snap.get("catalogue_source"),
            "instrument": item,
            "opportunity": scored,
            "NEWS_PROTECTION": snap.get("NEWS_PROTECTION"),
        }
    )


@router.post("/refresh")
async def market_universe_refresh(user: CurrentUser) -> dict[str, Any]:
    """Re-read broker catalogue if an adapter is available. Never places orders."""
    _ = user
    adapter, diag = resolve_runtime_mt5_adapter()
    return _research_envelope(
        _service.refresh(mt5_adapter=adapter, adapter_resolution=diag)
    )
