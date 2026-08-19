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
_SCAN_GATE = asyncio.Lock()


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
    broker_symbol_rows: tuple[dict[str, Any], ...] | list[dict[str, Any]] | None = None,
    session: str | None = None,
) -> tuple[str, ...]:
    """Watchlist: seed ∪ liquid broker discoveries, session/learning prioritized.

    Quality / structure / momentum / RR gates are unchanged — this only decides
    *which* symbols are scored each cycle.
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    try:
        from app.domain.trading.gold_only import (
            autonomous_execution_symbols,
            gold_only_enabled,
        )

        if gold_only_enabled():
            return autonomous_execution_symbols(
                broker_symbol_rows=broker_symbol_rows
            )
    except Exception:
        logger.exception("gold_only_scan_universe_failed")
    seed = tuple(cfg.universe or DEFAULT_SCALPING_UNIVERSE)
    seed = tuple(s for s in seed if s not in BROKER_UNAVAILABLE_SCALP_SYMBOLS)

    demoted: set[str] = set()
    boost: dict[str, float] = {}
    seed_recovery: set[str] = set()
    if getattr(cfg, "live_symbol_learning_enabled", True):
        try:
            from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
                get_symbol_stats_book,
            )

            book = get_symbol_stats_book()
            # Cooldown expiry + recovery eligibility before universe assembly.
            book.expire_stale_demotions()
            demoted = set(book.demoted_symbols())
            boost = book.performance_boost()
        except Exception:
            logger.exception("symbol_stats_priority_unavailable")

    base = seed
    if getattr(cfg, "dynamic_universe_enabled", False) and broker_symbol_rows:
        try:
            from app.domain.institutional_trading.ai_scalping.universe_discovery import (
                build_dynamic_scalping_universe,
                discover_from_broker_rows,
                resolve_seed_to_broker_symbol,
            )

            discovered = discover_from_broker_rows(list(broker_symbol_rows))
            # Catalogue-liquid seeds are recovery-eligible even if demoted.
            for s in seed:
                resolved = resolve_seed_to_broker_symbol(s, discovered=discovered)
                for d in discovered:
                    if (
                        d.code.upper() == resolved
                        and d.liquid_scalp
                        and int(d.trade_mode) == 4
                    ):
                        seed_recovery.add(resolved)
                        break
            base = build_dynamic_scalping_universe(
                discovered,
                seed=seed,
                max_symbols=int(getattr(cfg, "max_universe_symbols", 28) or 28),
                demoted=demoted,
                seed_recovery=seed_recovery,
            )
        except Exception:
            logger.exception("dynamic_universe_build_failed")
            base = seed
    else:
        # Preserve configured seeds for recovery probes even if demoted.
        seed_u = {str(s).strip().upper() for s in seed}
        base = tuple(
            s for s in base if s not in demoted or str(s).strip().upper() in seed_u
        )

    if plane is not None:
        allowed = tuple(
            str(s).strip().upper()
            for s in (getattr(plane, "allowed_symbols", ()) or ())
            if str(s).strip()
        )
        if allowed:
            try:
                from app.domain.trading.gold_only import GOLD_SYMBOL, gold_only_enabled

                if gold_only_enabled():
                    from app.domain.trading.gold_only import (
                        autonomous_execution_symbols,
                        is_gold_symbol,
                    )

                    gold_only = tuple(s for s in base if is_gold_symbol(s))
                    base = gold_only or autonomous_execution_symbols(
                        broker_symbol_rows=broker_symbol_rows
                    )
                elif len(allowed) <= 1 or set(allowed) <= {GOLD_SYMBOL}:
                    # Stale gold-only plane — keep dynamic / seed base
                    pass
                elif getattr(cfg, "dynamic_universe_enabled", False) and broker_symbol_rows:
                    # LIVE broker discovery owns membership; plane must not
                    # shrink the liquid scalping universe back to a static seed.
                    pass
                else:
                    allowed_set = set(allowed) - BROKER_UNAVAILABLE_SCALP_SYMBOLS
                    filtered = tuple(s for s in base if s in allowed_set)
                    base = filtered or base
            except Exception:
                if not (
                    getattr(cfg, "dynamic_universe_enabled", False)
                    and broker_symbol_rows
                ):
                    allowed_set = set(allowed) - BROKER_UNAVAILABLE_SCALP_SYMBOLS
                    filtered = tuple(s for s in base if s in allowed_set)
                    base = filtered or base

    if getattr(cfg, "session_symbol_priority_enabled", True):
        try:
            from app.domain.institutional_trading.ai_scalping.session_symbol_priority import (
                prioritize_universe_for_session,
            )

            base = prioritize_universe_for_session(
                base, session, performance_boost=boost
            )
        except Exception:
            logger.exception("session_symbol_priority_failed")

    return base


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
    try:
        from app.domain.trading.gold_only import (
            gold_only_enabled,
            is_gold_symbol,
        )

        if gold_only_enabled() and code and not is_gold_symbol(code):
            return {
                "symbol": code,
                "reject": True,
                "reject_reason": "GOLD_ONLY_SYMBOL_REJECTED",
                "direction": "NONE",
                "ai_confidence": 0,
                "trade_quality": 0,
            }
    except Exception:
        logger.exception("gold_only_score_gate_failed")
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
            "broker_ok": False,
        }
    snapshot = ctx.snapshot
    account: AccountRiskState = ctx.account
    resolved = str(
        (ctx.diagnostics or {}).get("broker_symbol_resolved")
        or (ctx.diagnostics or {}).get("symbol")
        or code
    ).upper()
    try:
        score = score_scalping_setup(
            snapshot,
            atr=account.atr,
            mid=account.mid_price,
            config=cfg,
            enforce_adaptive_cooldown=True,
            symbol=resolved or code,
            opens=tuple(getattr(snapshot, "entry_opens", ()) or ()),
            highs=tuple(getattr(snapshot, "entry_highs", ()) or ()),
            lows=tuple(getattr(snapshot, "entry_lows", ()) or ()),
            closes=tuple(getattr(snapshot, "entry_closes", ()) or ()),
        )
        payload = score.to_dict()
        payload["symbol"] = resolved or code
        payload["requested_symbol"] = code
        payload["broker_ok"] = True
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
    invoked here — every independent eligible is handed to the existing cycle
    (up to max_entries_per_cycle / max_open_trades) with unchanged gates.
    Already-open symbols are excluded from new-entry handoff (no same-symbol
    duplicate unless pyramid rules allow via PRE on a deliberate re-entry).
    """
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    # Prevent overlapping scanner cycles (shared gateway / MT5 terminal pressure).
    try:
        await asyncio.wait_for(_SCAN_GATE.acquire(), timeout=0.01)
    except TimeoutError:
        last = get_last_multi_asset_scan() or {}
        logger.warning(
            "multi_asset_scan_overlap_skipped",
            note="previous scan still in flight — reuse last snapshot",
        )
        if last:
            skipped = dict(last)
            skipped["overlap_skipped"] = True
            try:
                from app.domain.institutional_trading.operations.fast_decision_path import (
                    build_current_scan_decision,
                    publish_current_scan_decision,
                )

                current = skipped.get("current_scan")
                if not isinstance(current, dict):
                    current = build_current_scan_decision(skipped)
                    skipped["current_scan"] = current
                publish_current_scan_decision(current)
            except Exception:
                logger.exception("current_scan_overlap_publish_failed")
            return skipped
        return {
            "as_of": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            "enabled": True,
            "universe": [],
            "rows": [],
            "noc_rows": [],
            "ranked": [],
            "best": None,
            "best_symbol": None,
            "best_candidate": None,
            "best_eligible_candidate": None,
            "no_eligible_setup": True,
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
            "eligible_count": 0,
            "eligible_symbols": [],
            "overlap_skipped": True,
            "note": "scan_in_flight_no_prior_snapshot",
            "version": cfg.version,
            "forced_trades": False,
            "governed_by_existing_ai_and_risk": True,
        }
    try:
        return await _run_institutional_multi_asset_scan_body(
            mt5_adapter,
            position_engine=position_engine,
            account=account,
            open_positions=open_positions,
            config=cfg,
            plane=plane,
            ite_config=ite_config,
        )
    finally:
        _SCAN_GATE.release()


async def _run_institutional_multi_asset_scan_body(
    mt5_adapter: Any,
    *,
    position_engine: Any | None = None,
    account: AccountRiskState | None = None,
    open_positions: int | None = None,
    config: AiScalpingConfig | None = None,
    plane: Any | None = None,
    ite_config: Any | None = None,
) -> dict[str, Any]:
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    # LIVE broker catalogue → dynamic liquid universe (quality gates unchanged).
    broker_rows: tuple[dict[str, Any], ...] = ()
    session_name: str | None = None
    try:
        from datetime import UTC as _UTC

        from app.domain.institutional_trading.session_filter import classify_session_utc

        session_name = classify_session_utc(datetime.now(_UTC)).value
    except Exception:
        session_name = None
    if mt5_adapter is not None and getattr(cfg, "dynamic_universe_enabled", False):
        try:
            from app.domain.institutional_trading.ai_scalping.universe_discovery import (
                fetch_broker_symbol_rows,
            )

            # Offload sync catalogue I/O so login/health stay responsive.
            broker_rows = await asyncio.to_thread(
                fetch_broker_symbol_rows, mt5_adapter
            )
        except Exception:
            logger.exception("broker_universe_fetch_failed")
    universe = resolve_scan_universe(
        cfg,
        plane=plane,
        broker_symbol_rows=broker_rows or None,
        session=session_name,
    )
    as_of = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    if broker_rows:
        try:
            from app.domain.institutional_trading.ai_scalping.universe_discovery import (
                classify_catalogue_summary,
                discover_from_broker_rows,
            )

            logger.warning(
                "scalping_dynamic_universe_resolved",
                session=session_name,
                universe_size=len(universe),
                universe=list(universe),
                catalogue=classify_catalogue_summary(discover_from_broker_rows(broker_rows)),
            )
        except Exception:
            logger.exception("dynamic_universe_log_failed")

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
            "best_candidate": None,
            "best_eligible_candidate": None,
            "no_eligible_setup": True,
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
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
            "best_candidate": None,
            "best_eligible_candidate": None,
            "no_eligible_setup": True,
            "first_blocking_gate": "NO_ELIGIBLE_SETUP",
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
        # Live learning: production scan stats (priority only — not gate weakening).
        if getattr(cfg, "live_symbol_learning_enabled", True):
            try:
                from app.domain.institutional_trading.ai_scalping.symbol_production_stats import (
                    get_symbol_stats_book,
                )

                reason = str(row.get("reject_reason") or "")
                reason_l = reason.lower()
                hard = any(
                    k in reason_l
                    for k in (
                        "market_context",
                        "symbol_select",
                        "unavailable",
                        "503",
                        "not found",
                        "market data load failed",
                        "terminal: call failed",
                    )
                )
                broker_ok = bool(row.get("broker_ok")) and not hard
                direction = str(row.get("direction") or "NONE").upper()
                eligible = (not bool(row.get("reject"))) and direction in {
                    "BUY",
                    "SELL",
                }
                atr_raw = row.get("atr_pct")
                spread_raw = row.get("spread") or row.get("spread_score")
                sym_code = str(row.get("symbol") or "")
                get_symbol_stats_book().record_scan(
                    sym_code,
                    eligible=eligible,
                    reject_reason=reason or None,
                    spread=float(spread_raw) if spread_raw is not None else None,
                    atr_pct=float(atr_raw) if atr_raw is not None else None,
                    broker_hard_fail=hard,
                    broker_ok=broker_ok,
                )
                if broker_ok:
                    get_symbol_stats_book().record_broker_ok(
                        sym_code, source="multi_asset_scan_md"
                    )
            except Exception:
                logger.exception("symbol_scan_stats_record_failed")

    # Multi-strategy pack — evaluate ALL strategies per symbol; one winner each.
    strategy_global_best = None
    strategy_winners: list[Any] = []
    if getattr(cfg, "multi_strategy_enabled", True):
        try:
            from app.domain.institutional_trading.ai_scalping.strategies import (
                attach_strategies_to_scores,
                evaluate_all_strategies,
                get_strategy_stats_book,
            )

            book = get_strategy_stats_book()
            boosts = book.live_rank_boosts()
            by_sym: dict[str, Any] = {}
            for row in scored:
                sym = str(row.get("symbol") or "").upper()
                evals = evaluate_all_strategies(row, config=cfg, live_boosts=boosts)
                by_sym[sym] = evals
                for ev in evals:
                    book.record_evaluation(ev.strategy_id, passed=ev.passed)
            scored, strategy_global_best, strategy_winners = attach_strategies_to_scores(
                scored, evaluations_by_symbol=by_sym
            )
            if strategy_global_best is not None:
                logger.warning(
                    "multi_strategy_best_opportunity",
                    strategy_id=strategy_global_best.strategy_id,
                    symbol=strategy_global_best.symbol,
                    quality=strategy_global_best.quality,
                    confidence=strategy_global_best.confidence,
                    direction=strategy_global_best.direction,
                )
            else:
                logger.warning(
                    "multi_strategy_no_passer",
                    strategies_evaluated=5,
                    symbols=len(scored),
                    note="SCALPING_V1 floors unchanged — no forced trades",
                )
        except Exception:
            logger.exception("multi_strategy_evaluation_failed")

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
    open_syms: set[str] = set()
    if position_engine is not None:
        try:
            for p in (getattr(position_engine, "_positions", {}) or {}).values():
                s = str(getattr(p, "symbol", "") or "").upper()
                if s:
                    open_syms.add(s)
            if open_n is None:
                open_n = len(open_syms)
        except Exception:
            if open_n is None:
                open_n = None

    # CRITICAL: portfolio ranking must use the SAME resolved scan universe.
    # Scoring uses `universe` (dynamic, up to 36). Leaving cfg.universe at the
    # static DEFAULT_SCALPING_UNIVERSE drops AUDNZD/AUDJPY/… from ranked →
    # portfolio_eligible → strategy winners with Q91/C84 get eligible_count=0.
    from dataclasses import replace as dc_replace

    cfg_for_rank = dc_replace(cfg, universe=tuple(universe))
    scan = run_multi_asset_scan(
        scored,
        account=account,
        open_positions=open_n,
        ite_config=ite_config,
        config=cfg_for_rank,
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
                and sym not in open_syms
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
    if best_symbol and best_symbol in open_syms:
        best_symbol = None
        best = None
    if best and bool(scan.get("blocked_by_portfolio")):
        best_symbol = None

    # Ranked eligible handoff list — independent symbols may all enter
    # (max_entries_per_cycle / max_open) without lowering quality.
    # Skip symbols already open — never duplicate same-symbol via handoff.
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
                and sym not in open_syms
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
                if sym and sym not in seen_elig and sym not in open_syms:
                    eligible_symbols.append(sym)
                    seen_elig.add(sym)
        if best_symbol and best_symbol in open_syms:
            best_symbol = eligible_symbols[0] if eligible_symbols else None
            best = None
        if best_symbol and best_symbol not in seen_elig:
            eligible_symbols.insert(0, best_symbol)
            seen_elig.add(best_symbol)
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

            excluded: set[str] = set(open_syms)
            nxt = peek_next_eligible(exclude_symbols=excluded)
            while nxt is not None:
                cand_sym = str(nxt.get("symbol") or "").upper()
                # Empty portfolio_eligible must still block — never promote a
                # symbol the portfolio ranker dropped (universe/cooldown/reject).
                if cand_sym not in portfolio_eligible:
                    excluded.add(cand_sym)
                    nxt = peek_next_eligible(exclude_symbols=excluded)
                    continue
                if cand_sym in open_syms:
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
    # Mark every independent eligible for Risk visibility (multi-asset concurrent).
    if eligible_symbols and not bool(scan.get("blocked_by_portfolio")):
        try:
            from app.domain.institutional_trading.ai_scalping.institutional_trade_queue import (
                select_for_risk,
            )

            for sym in eligible_symbols:
                select_for_risk(sym)
        except Exception:
            logger.exception("trade_queue_multi_select_failed")

    # Prefer multi-strategy global winner when portfolio-eligible (one strategy/symbol).
    if (
        strategy_global_best is not None
        and not bool(scan.get("blocked_by_portfolio"))
        and strategy_global_best.symbol in portfolio_eligible
        and strategy_global_best.symbol not in open_syms
    ):
        best_symbol = strategy_global_best.symbol
        best = {
            **(best or {}),
            "symbol": best_symbol,
            "strategy_id": strategy_global_best.strategy_id,
            "strategy_name": strategy_global_best.name,
            "strategy_quality": strategy_global_best.quality,
            "strategy_confidence": strategy_global_best.confidence,
            "strategy_explanation": strategy_global_best.explanation,
            "direction": strategy_global_best.direction,
        }
        if best_symbol in eligible_symbols:
            eligible_symbols = [best_symbol] + [
                s for s in eligible_symbols if s != best_symbol
            ]
        else:
            eligible_symbols.insert(0, best_symbol)
    elif strategy_global_best is not None:
        logger.warning(
            "multi_strategy_winner_blocked_final_gate",
            strategy_id=strategy_global_best.strategy_id,
            symbol=strategy_global_best.symbol,
            quality=strategy_global_best.quality,
            confidence=strategy_global_best.confidence,
            direction=strategy_global_best.direction,
            blocked_by_portfolio=bool(scan.get("blocked_by_portfolio")),
            in_portfolio_eligible=strategy_global_best.symbol in portfolio_eligible,
            already_open=strategy_global_best.symbol in open_syms,
            portfolio_eligible_count=len(portfolio_eligible),
            scan_universe_size=len(universe),
            cfg_universe_size=len(cfg_for_rank.universe),
            boolean=(
                "strategy_global_best is not None "
                "and not blocked_by_portfolio "
                "and symbol in portfolio_eligible "
                "and symbol not in open_syms"
            ),
            runtime_values={
                "blocked_by_portfolio": bool(scan.get("blocked_by_portfolio")),
                "in_portfolio_eligible": strategy_global_best.symbol
                in portfolio_eligible,
                "in_open_syms": strategy_global_best.symbol in open_syms,
            },
        )

    # Focused Pair Watch — hold a still-eligible desk; rotate only when invalid
    # or another eligible candidate is materially more executable.
    try:
        from app.domain.institutional_trading.operations.fast_decision_path import (
            apply_focus_hysteresis,
            opportunity_window_snapshot,
            set_focus,
        )

        scores = {
            str(r.get("symbol") or "").upper(): float(r.get("opportunity_score") or 0)
            for r in opportunity_ranked
            if isinstance(r, dict) and str(r.get("symbol") or "").strip()
        }
        prior = str(
            (opportunity_window_snapshot().get("current_focus") or "")
        ).upper() or None
        held, focus_why = apply_focus_hysteresis(
            current_focus=prior,
            eligible_symbols=list(eligible_symbols),
            scores=scores,
            proposed=best_symbol,
        )
        if held and held != best_symbol:
            best_symbol = held
            for row in opportunity_ranked:
                if str(row.get("symbol") or "").upper() == held:
                    best = {**(best or {}), **row, "symbol": held}
                    break
            if held in eligible_symbols:
                eligible_symbols = [held] + [s for s in eligible_symbols if s != held]
            else:
                eligible_symbols.insert(0, held)
        set_focus(best_symbol, reason=focus_why)
    except Exception:
        logger.exception("focused_pair_watch_hysteresis_failed")

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
        enriched["strategy_id"] = raw.get("strategy_id")
        enriched["strategy_quality"] = raw.get("strategy_quality")
        enriched["strategy_confidence"] = raw.get("strategy_confidence")
        if port.get("reject_reason"):
            enriched["blocking_gate"] = port.get("reject_reason") or enriched.get(
                "blocking_gate"
            )
        if port.get("reject"):
            enriched["reject"] = True
            enriched["eligible"] = False
            enriched["decision"] = "NO_TRADE"
        enriched_noc.append(enriched)

    first_blocking_gate = None
    if bool(scan.get("blocked_by_portfolio")):
        first_blocking_gate = str(
            scan.get("portfolio_block_reason") or "PORTFOLIO_RISK_LIMIT"
        )
    elif not best_symbol:
        for row in opportunity_ranked:
            if not isinstance(row, dict):
                continue
            if row.get("reject") or not row.get("opportunity_eligible"):
                first_blocking_gate = str(
                    row.get("reject_reason")
                    or row.get("blocking_gate")
                    or "NO_ELIGIBLE_SETUP"
                )
                break
        if not first_blocking_gate:
            first_blocking_gate = "NO_ELIGIBLE_SETUP"

    def _candidate_view(row: Any) -> dict[str, Any] | None:
        if not isinstance(row, dict):
            return None
        return {
            "symbol": str(row.get("symbol") or "").upper() or None,
            "direction": row.get("direction"),
            "quality": row.get("quality") or row.get("trade_quality"),
            "confidence": row.get("confidence") or row.get("ai_confidence"),
            "opportunity_score": row.get("opportunity_score"),
            "estimated_probability": row.get("estimated_probability"),
            "eligible": bool(
                row.get("opportunity_eligible")
                if "opportunity_eligible" in row
                else row.get("eligible")
            ),
            "blocking_gate": row.get("reject_reason") or row.get("blocking_gate"),
            "strategy_id": row.get("strategy_id"),
            "atr_pct": row.get("atr_pct"),
            "volatility_decision": row.get("volatility_decision"),
            "thresholds": row.get("thresholds"),
        }

    best_candidate = _candidate_view(
        opportunity_ranked[0] if opportunity_ranked else None
    )
    best_eligible_candidate = _candidate_view(best) if best_symbol else None

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
                "reject": r.get("reject"),
                "reject_reason": r.get("reject_reason"),
                "estimated_probability": r.get("estimated_probability"),
                "atr_pct": r.get("atr_pct"),
                "volatility_decision": r.get("volatility_decision"),
                "thresholds": r.get("thresholds"),
            }
            for r in opportunity_ranked[:20]
        ],
        "trade_queue": queue_snap,
        "best": best,
        "best_symbol": best_symbol,
        "best_candidate": best_candidate,
        "best_eligible_candidate": best_eligible_candidate,
        "no_eligible_setup": best_symbol is None,
        "first_blocking_gate": first_blocking_gate,
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
        "quality_floor": int(cfg.normal_vol.quality),
        "confidence_floor": int(cfg.normal_vol.confidence),
        "execute_only_best": False,
        "independent_multi_asset": True,
        "open_symbols_excluded": sorted(open_syms),
        "max_entries_per_cycle": int(
            getattr(cfg, "max_entries_per_cycle", 3) or 3
        ),
        "max_open_trades": int(getattr(cfg, "max_open_trades", 5) or 5),
        "parallel_scan": bool(getattr(cfg, "parallel_scan_enabled", True)),
        "profile": str(getattr(cfg, "quality_baseline", "") or cfg.version),
        "multi_strategy_enabled": bool(getattr(cfg, "multi_strategy_enabled", True)),
        "strategy_best": (
            strategy_global_best.to_dict() if strategy_global_best is not None else None
        ),
        "strategy_winners": [w.to_dict() for w in strategy_winners],
        "strategy_stats": None,
        "forced_trades": False,
        "governed_by_existing_ai_and_risk": True,
        "atr_source_timeframe": "M15",
        "atr_source_period": 14,
    }
    try:
        from app.domain.institutional_trading.operations.fast_decision_path import (
            build_current_scan_decision,
            publish_current_scan_decision,
        )

        current_scan = build_current_scan_decision(payload)
        payload["current_scan"] = current_scan
        payload["first_blocking_gate_code"] = current_scan.get("fault_code")
        publish_current_scan_decision(current_scan)
    except Exception:
        logger.exception("current_scan_decision_publish_failed")
    try:
        from app.domain.institutional_trading.ai_scalping.strategies import (
            get_strategy_stats_book,
        )

        payload["strategy_stats"] = get_strategy_stats_book().snapshot()
    except Exception:
        pass
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
