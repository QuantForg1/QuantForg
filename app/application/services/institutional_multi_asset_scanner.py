"""Institutional Multi-Asset Scanner — parallel AI score per symbol.

Fetches market data and runs the existing AI scalping score independently for
each watchlist symbol (bounded parallel). Ranks via the existing portfolio
scanner. Returns the full eligible ranked list for multi-symbol handoff while
preserving Risk → PRE → OMS → MT5 per entry.

Does not lower quality/confidence floors. Does not force BUY/SELL.
Does not bypass AI, Risk, PRE, OMS, or MT5.
"""

from __future__ import annotations

import asyncio
import threading
from datetime import UTC, datetime
from typing import Any

from app.application.services.ai_scalping_portfolio import run_multi_asset_scan
from app.application.services.ite_cycle_market_context import (
    build_ite_cycle_market_context,
)
from app.domain.institutional_trading.ai_scalping.config import (
    BROKER_UNAVAILABLE_SCALP_SYMBOLS,
    DEFAULT_AI_SCALPING_CONFIG,
    DEFAULT_SCALPING_UNIVERSE,
    AiScalpingConfig,
)
from app.domain.institutional_trading.ai_scalping.scoring import score_scalping_setup
from app.domain.institutional_trading.decision_models import AccountRiskState
from core.logging import get_logger

logger = get_logger(__name__)

_LOCK = threading.RLock()
_LAST_SCAN: dict[str, Any] | None = None


def get_last_multi_asset_scan() -> dict[str, Any] | None:
    """Observe-only snapshot of the most recent institutional multi-asset scan."""
    with _LOCK:
        return dict(_LAST_SCAN) if isinstance(_LAST_SCAN, dict) else None


def _store_last_scan(payload: dict[str, Any]) -> None:
    global _LAST_SCAN
    with _LOCK:
        _LAST_SCAN = dict(payload)


def _noc_row_from_score(score: dict[str, Any]) -> dict[str, Any]:
    """Normalize a score dict into NOC multi-asset table columns."""
    factors = score.get("factors") if isinstance(score.get("factors"), dict) else {}
    vol_dec = (
        score.get("volatility_decision")
        if isinstance(score.get("volatility_decision"), dict)
        else {}
    )
    quality = int(score.get("trade_quality") or score.get("quality") or 0)
    confidence = int(score.get("ai_confidence") or score.get("confidence") or 0)
    reject = bool(score.get("reject"))
    direction = str(score.get("direction") or "NONE").upper()
    decision = "NO_TRADE" if reject or direction in {"", "NONE"} else direction
    mtf = score.get("mtf_alignment")
    if mtf is None:
        mtf = factors.get("mtf") or factors.get("h1_bias")
    liquidity = score.get("liquidity")
    if liquidity is None:
        liquidity = factors.get("liquidity_sweep") or factors.get("liquidity")
    volatility = None
    if vol_dec:
        volatility = vol_dec.get("band") or vol_dec.get("reason") or vol_dec.get("passed")
    if volatility is None:
        volatility = score.get("market_regime") or factors.get("volatility")
    blocker = None
    if reject:
        blocker = score.get("reject_reason") or score.get("blocking_gate")
        reasons = score.get("reject_reasons") or score.get("failed_gates")
        if not blocker and isinstance(reasons, list) and reasons:
            blocker = str(reasons[0])
    return {
        "symbol": str(score.get("symbol") or "").upper(),
        "quality": quality,
        "confidence": confidence,
        "mtf": mtf,
        "liquidity": liquidity,
        "volatility": volatility,
        "decision": decision,
        "direction": direction,
        "blocking_gate": blocker,
        "reject": reject,
        "eligible": (not reject) and direction in {"BUY", "SELL"},
        "expected_rr": score.get("expected_rr"),
        "setup_family": score.get("setup_family"),
        "market_regime": score.get("market_regime") or score.get("regime"),
        "atr_pct": score.get("atr_pct"),
        "spread_score": score.get("spread_score"),
    }


def resolve_scan_universe(
    config: AiScalpingConfig | None = None,
    *,
    plane: Any | None = None,
) -> tuple[str, ...]:
    """Configurable watchlist — AiScalping universe, optionally intersected by plane."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    base = tuple(cfg.universe or DEFAULT_SCALPING_UNIVERSE)
    # Never spend cycle time on broker-dead index aliases.
    base = tuple(s for s in base if s not in BROKER_UNAVAILABLE_SCALP_SYMBOLS)
    if plane is None:
        return base
    allowed = tuple(
        str(s).strip().upper()
        for s in (getattr(plane, "allowed_symbols", ()) or ())
        if str(s).strip()
    )
    if not allowed:
        return base
    # Defense: never let a stale gold-only plane collapse MULTI_SYMBOL scan.
    try:
        from app.domain.trading.gold_only import GOLD_SYMBOL, gold_only_enabled

        if not gold_only_enabled() and (
            len(allowed) <= 1 or set(allowed) <= {GOLD_SYMBOL}
        ):
            return base
    except Exception:
        pass
    allowed_set = set(allowed) - BROKER_UNAVAILABLE_SCALP_SYMBOLS
    filtered = tuple(s for s in base if s in allowed_set)
    return filtered or base


async def score_symbol_for_scan(
    mt5_adapter: Any,
    symbol: str,
    *,
    position_engine: Any | None = None,
    config: AiScalpingConfig | None = None,
) -> dict[str, Any]:
    """Fetch market data + run existing AI score for one symbol (no Risk/OMS)."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    code = (symbol or "").strip().upper()
    if not code:
        return {
            "symbol": "",
            "reject": True,
            "reject_reason": "empty_symbol",
            "direction": "NONE",
            "ai_confidence": 0,
            "trade_quality": 0,
        }
    try:
        ctx = await build_ite_cycle_market_context(
            mt5_adapter,
            symbol=code,
            position_engine=position_engine,
        )
    except Exception as exc:
        logger.exception("multi_asset_market_context_failed", symbol=code)
        return {
            "symbol": code,
            "reject": True,
            "reject_reason": f"market_context_error:{type(exc).__name__}",
            "direction": "NONE",
            "ai_confidence": 0,
            "trade_quality": 0,
        }
    if not ctx.ok or ctx.snapshot is None or ctx.account is None:
        return {
            "symbol": code,
            "reject": True,
            "reject_reason": ctx.reason or "market_context_unavailable",
            "direction": "NONE",
            "ai_confidence": 0,
            "trade_quality": 0,
            "market_context_reason": ctx.reason,
        }
    snapshot = ctx.snapshot
    account: AccountRiskState = ctx.account
    try:
        score = score_scalping_setup(
            snapshot,
            atr=account.atr,
            mid=account.mid_price,
            config=cfg,
            enforce_adaptive_cooldown=True,
            symbol=code,
            opens=tuple(getattr(snapshot, "entry_opens", ()) or ()),
            highs=tuple(getattr(snapshot, "entry_highs", ()) or ()),
            lows=tuple(getattr(snapshot, "entry_lows", ()) or ()),
            closes=tuple(getattr(snapshot, "entry_closes", ()) or ()),
        )
        payload = score.to_dict()
        payload["symbol"] = code
        payload["mtf_alignment"] = int(
            getattr(getattr(snapshot, "trend", None), "alignment_score", 0) or 0
        )
        return payload
    except Exception as exc:
        logger.exception("multi_asset_score_failed", symbol=code)
        return {
            "symbol": code,
            "reject": True,
            "reject_reason": f"ai_score_error:{type(exc).__name__}",
            "direction": "NONE",
            "ai_confidence": 0,
            "trade_quality": 0,
        }


async def run_institutional_multi_asset_scan(
    mt5_adapter: Any,
    *,
    position_engine: Any | None = None,
    account: AccountRiskState | None = None,
    open_positions: int | None = None,
    config: AiScalpingConfig | None = None,
    plane: Any | None = None,
    ite_config: Any | None = None,
) -> dict[str, Any]:
    """Scan the full watchlist in parallel; rank; return eligible handoff list.

    Downstream Risk / Dynamic Sizing / PRE / OMS / MT5 are intentionally not
    invoked here — eligible symbols are handed to the existing cycle one-by-one
    (up to max_entries_per_cycle) with unchanged institutional gates.
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    universe = resolve_scan_universe(cfg, plane=plane)
    as_of = datetime.now(UTC).isoformat().replace("+00:00", "Z")

    if not bool(getattr(cfg, "multi_asset_scan_enabled", True)):
        payload = {
            "as_of": as_of,
            "enabled": False,
            "universe": list(universe),
            "rows": [],
            "noc_rows": [],
            "ranked": [],
            "best": None,
            "best_symbol": None,
            "eligible_count": 0,
            "eligible_symbols": [],
            "note": "multi_asset_scan_disabled",
            "version": cfg.version,
            "forced_trades": False,
            "governed_by_existing_ai_and_risk": True,
        }
        _store_last_scan(payload)
        return payload

    if mt5_adapter is None:
        payload = {
            "as_of": as_of,
            "enabled": True,
            "universe": list(universe),
            "rows": [],
            "noc_rows": [],
            "ranked": [],
            "best": None,
            "best_symbol": None,
            "eligible_count": 0,
            "eligible_symbols": [],
            "note": "mt5_adapter_unavailable",
            "version": cfg.version,
            "governed_by_existing_ai_and_risk": True,
        }
        _store_last_scan(payload)
        return payload

    scored: list[dict[str, Any]] = []
    if bool(getattr(cfg, "parallel_scan_enabled", True)) and len(universe) > 1:
        conc = max(1, int(getattr(cfg, "parallel_scan_concurrency", 4) or 4))
        sem = asyncio.Semaphore(conc)

        async def _score_one(sym: str) -> dict[str, Any]:
            async with sem:
                return await score_symbol_for_scan(
                    mt5_adapter,
                    sym,
                    position_engine=position_engine,
                    config=cfg,
                )

        scored = list(await asyncio.gather(*[_score_one(s) for s in universe]))
    else:
        for symbol in universe:
            row = await score_symbol_for_scan(
                mt5_adapter,
                symbol,
                position_engine=position_engine,
                config=cfg,
            )
            scored.append(row)

    for row in scored:
        logger.warning(
            "multi_asset_symbol_scored",
            symbol=row.get("symbol"),
            reject=row.get("reject"),
            quality=row.get("trade_quality") or row.get("quality"),
            confidence=row.get("ai_confidence") or row.get("confidence"),
            direction=row.get("direction"),
            reason=row.get("reject_reason"),
        )

    # Opportunity Ranking + Execution Probability + Trade Queue
    try:
        from app.domain.institutional_trading.ai_scalping.execution_probability import (
            estimate_execution_probability,
        )
        from app.domain.institutional_trading.ai_scalping.institutional_trade_queue import (
            rebuild_trade_queue,
        )
        from app.domain.institutional_trading.ai_scalping.opportunity_ranking import (
            enrich_scores_with_opportunity,
            rank_by_opportunity_score,
        )

        for row in scored:
            row["probability"] = estimate_execution_probability(row)
            row["estimated_probability"] = row["probability"]["probability_of_success"]
        scored = enrich_scores_with_opportunity(scored)
        opportunity_ranked = rank_by_opportunity_score(scored)
        queue_snap = rebuild_trade_queue(scored)
    except Exception:
        logger.exception("opportunity_ranking_queue_failed")
        opportunity_ranked = scored
        queue_snap = {"candidates": [], "size": 0}

    open_n = open_positions
    if open_n is None and position_engine is not None:
        try:
            open_n = len(getattr(position_engine, "_positions", {}) or {})
        except Exception:
            open_n = None

    scan = run_multi_asset_scan(
        scored,
        account=account,
        open_positions=open_n,
        ite_config=ite_config,
        config=cfg,
    )
    ranked = scan.get("ranked") if isinstance(scan.get("ranked"), list) else []
    best = scan.get("best") if isinstance(scan.get("best"), dict) else None
    # Portfolio-ranked eligible set — never promote a portfolio-rejected symbol
    portfolio_eligible = {
        str(r.get("symbol") or "").upper()
        for r in ranked
        if isinstance(r, dict) and not r.get("reject")
    }
    # Prefer opportunity-ranked winner among portfolio-eligible only
    if not bool(scan.get("blocked_by_portfolio")) and portfolio_eligible:
        for row in opportunity_ranked:
            sym = str(row.get("symbol") or "").upper()
            if (
                sym in portfolio_eligible
                and row.get("opportunity_eligible")
                and not row.get("reject")
            ):
                best = {**(best or {}), **row}
                best["symbol"] = sym
                best["opportunity_score"] = row.get("opportunity_score")
                break
    best_symbol = (
        str(best.get("symbol") or "").upper()
        if best and not bool(scan.get("blocked_by_portfolio"))
        else None
    )
    if best and bool(scan.get("blocked_by_portfolio")):
        best_symbol = None

    # Ranked eligible handoff list — independent symbols may enter sequentially
    # in one outer cycle (max_entries_per_cycle) without lowering quality.
    eligible_symbols: list[str] = []
    if not bool(scan.get("blocked_by_portfolio")):
        seen_elig: set[str] = set()
        for row in opportunity_ranked:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or "").upper()
            if (
                sym
                and sym in portfolio_eligible
                and row.get("opportunity_eligible")
                and not row.get("reject")
                and sym not in seen_elig
            ):
                eligible_symbols.append(sym)
                seen_elig.add(sym)
        if not eligible_symbols:
            for r in ranked:
                if not isinstance(r, dict) or r.get("reject"):
                    continue
                sym = str(r.get("symbol") or "").upper()
                if sym and sym not in seen_elig:
                    eligible_symbols.append(sym)
                    seen_elig.add(sym)
        if best_symbol and best_symbol not in seen_elig:
            eligible_symbols.insert(0, best_symbol)
        elif best_symbol and eligible_symbols and eligible_symbols[0] != best_symbol:
            eligible_symbols = [best_symbol] + [
                s for s in eligible_symbols if s != best_symbol
            ]

    # If current best disappears, evaluate next ranked eligible from queue
    if best_symbol is None and not bool(scan.get("blocked_by_portfolio")):
        try:
            from app.domain.institutional_trading.ai_scalping.institutional_trade_queue import (
                peek_next_eligible,
                select_for_risk,
            )

            excluded: set[str] = set()
            nxt = peek_next_eligible(exclude_symbols=excluded)
            while nxt is not None:
                cand_sym = str(nxt.get("symbol") or "").upper()
                if portfolio_eligible and cand_sym not in portfolio_eligible:
                    excluded.add(cand_sym)
                    nxt = peek_next_eligible(exclude_symbols=excluded)
                    continue
                selected = select_for_risk(cand_sym)
                if selected:
                    best_symbol = cand_sym or None
                    best = {**(best or {}), **selected}
                break
        except Exception:
            logger.exception("trade_queue_next_eligible_failed")
    elif best_symbol:
        try:
            from app.domain.institutional_trading.ai_scalping.institutional_trade_queue import (
                select_for_risk,
            )

            select_for_risk(best_symbol)
        except Exception:
            logger.exception("trade_queue_select_failed")

    noc_rows = [_noc_row_from_score(r) for r in scored]
    # Prefer ranked portfolio rows for richer reject/cooldown annotations
    by_sym = {
        str(r.get("symbol") or "").upper(): r
        for r in (scan.get("rows") or [])
        if isinstance(r, dict)
    }
    enriched_noc: list[dict[str, Any]] = []
    for base in noc_rows:
        sym = base["symbol"]
        port = by_sym.get(sym) or {}
        enriched = dict(base)
        raw = next((r for r in scored if str(r.get("symbol") or "").upper() == sym), {})
        enriched["opportunity_score"] = raw.get("opportunity_score")
        enriched["estimated_probability"] = raw.get("estimated_probability")
        if port.get("reject_reason"):
            enriched["blocking_gate"] = port.get("reject_reason") or enriched.get(
                "blocking_gate"
            )
        if port.get("reject"):
            enriched["reject"] = True
            enriched["eligible"] = False
            enriched["decision"] = "NO_TRADE"
        enriched_noc.append(enriched)

    payload: dict[str, Any] = {
        "as_of": as_of,
        "enabled": True,
        "universe": list(universe),
        "scored_count": len(scored),
        "rows": list(scan.get("rows") or []),
        "noc_rows": enriched_noc,
        "ranked": ranked,
        "opportunity_ranked": [
            {
                "symbol": r.get("symbol"),
                "opportunity_score": r.get("opportunity_score"),
                "quality": r.get("trade_quality") or r.get("quality"),
                "confidence": r.get("ai_confidence") or r.get("confidence"),
                "direction": r.get("direction"),
                "eligible": r.get("opportunity_eligible"),
                "blocking_gate": r.get("reject_reason"),
                "estimated_probability": r.get("estimated_probability"),
            }
            for r in opportunity_ranked[:20]
        ],
        "trade_queue": queue_snap,
        "best": best,
        "best_symbol": best_symbol,
        "eligible_count": len(ranked) if not eligible_symbols else len(eligible_symbols),
        "eligible_symbols": list(eligible_symbols),
        "blocked_by_portfolio": bool(scan.get("blocked_by_portfolio")),
        "portfolio_block_reason": scan.get("portfolio_block_reason"),
        "portfolio_risk": scan.get("portfolio_risk"),
        "scheduler": scan.get("scheduler"),
        "symbol_state": scan.get("symbol_state"),
        "note": scan.get("note")
        or "institutional_multi_asset_scan — parallel score + multi-symbol handoff",
        "version": cfg.version,
        "quality_floor": 80,
        "confidence_floor": 80,
        "execute_only_best": False,
        "max_entries_per_cycle": int(
            getattr(cfg, "max_entries_per_cycle", 3) or 3
        ),
        "parallel_scan": bool(getattr(cfg, "parallel_scan_enabled", True)),
        "forced_trades": False,
        "governed_by_existing_ai_and_risk": True,
    }
    _store_last_scan(payload)
    logger.warning(
        "multi_asset_scan_complete",
        universe=list(universe),
        best_symbol=best_symbol,
        eligible_count=payload["eligible_count"],
        eligible_symbols=list(eligible_symbols)[:8],
        blocked_by_portfolio=payload["blocked_by_portfolio"],
        parallel_scan=payload["parallel_scan"],
    )
    return payload
