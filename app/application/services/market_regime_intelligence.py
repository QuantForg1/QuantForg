"""Market Regime Intelligence Engine — read-only classification.

Classifies each Strategy Diagnostics evaluation into observational regimes
using existing artefacts only (MTF, ATR%, structure components, news, spread,
volume). Never modifies Strategy, Risk, Safety, OMS, Thresholds, or Execution.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from statistics import mean
from typing import Any

# Mission regime taxonomy (uppercase labels for Ops desk).
REGIME_TRENDING = "TRENDING"
REGIME_RANGING = "RANGING"
REGIME_BREAKOUT = "BREAKOUT"
REGIME_PULLBACK = "PULLBACK"
REGIME_HIGH_VOL = "HIGH VOLATILITY"
REGIME_LOW_VOL = "LOW VOLATILITY"
REGIME_NEWS_VOL = "NEWS VOLATILITY"
REGIME_LIQ_SWEEP = "LIQUIDITY SWEEP"
REGIME_UNKNOWN = "UNKNOWN"

ALL_REGIMES: tuple[str, ...] = (
    REGIME_TRENDING,
    REGIME_RANGING,
    REGIME_BREAKOUT,
    REGIME_PULLBACK,
    REGIME_HIGH_VOL,
    REGIME_LOW_VOL,
    REGIME_NEWS_VOL,
    REGIME_LIQ_SWEEP,
)

_PRIMARY_PRIORITY: tuple[str, ...] = (
    REGIME_NEWS_VOL,
    REGIME_LIQ_SWEEP,
    REGIME_BREAKOUT,
    REGIME_PULLBACK,
    REGIME_HIGH_VOL,
    REGIME_LOW_VOL,
    REGIME_TRENDING,
    REGIME_RANGING,
)

ATR_HIGH_PCT = Decimal("1.5")
ATR_LOW_PCT = Decimal("0.4")
MTF_TREND_FLOOR = 70
HISTORY_WINDOW = 100


def _f(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _i(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_ts(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _atr_pct(atr: float | None, mid: float | None) -> float | None:
    if atr is None or mid is None or mid <= 0 or atr <= 0:
        return None
    try:
        return float(
            (Decimal(str(atr)) / Decimal(str(mid)) * Decimal("100")).quantize(
                Decimal("0.01")
            )
        )
    except (InvalidOperation, ValueError):
        return None


def _features_from_cycle(cycle: dict[str, Any]) -> dict[str, Any]:
    """Extract observational features from a diagnostics cycle."""
    trend = _as_dict(cycle.get("trend"))
    quality = _as_dict(cycle.get("quality"))
    confluence = _as_dict(cycle.get("confluence"))
    components = _as_dict(confluence.get("components"))
    sizing = _as_dict(cycle.get("sizing"))
    mctx = _as_dict(cycle.get("market_context_diagnostics"))

    atr = _f(cycle.get("atr") or sizing.get("atr") or mctx.get("atr"))
    spread = _f(cycle.get("spread") or mctx.get("spread"))
    mid = _f(
        mctx.get("bid")
        or mctx.get("ask")
        or mctx.get("mid")
        or cycle.get("mid_price")
        or cycle.get("entry")
    )
    if mid is None:
        bid, ask = _f(mctx.get("bid")), _f(mctx.get("ask"))
        if bid is not None and ask is not None:
            mid = (bid + ask) / 2.0

    mtf = _i(trend.get("score"))
    aligned = trend.get("aligned")
    h4 = str(trend.get("h4") or "").lower()
    h1 = str(trend.get("h1") or "").lower()
    m15 = str(trend.get("m15") or "").lower()
    m5 = str(trend.get("m5") or "").lower()

    bos = _i(components.get("bos")) or 0
    choch = _i(components.get("choch")) or 0
    liq = _i(components.get("liquidity_sweep")) or 0
    fvg = _i(components.get("fair_value_gap")) or 0
    vol_score = _i(components.get("volume"))
    news_filter = _i(components.get("news_filter"))
    volume_raw = _f(cycle.get("volume_raw") or mctx.get("volume"))

    rejection = _as_dict(cycle.get("rejection"))
    codes = [str(c).lower() for c in (rejection.get("all_codes") or [])]
    news_blocked = (
        "news_blackout" in codes
        or (news_filter is not None and news_filter < 40)
        or bool(cycle.get("news_blocked"))
    )

    return {
        "mtf_score": mtf,
        "mtf_aligned": aligned if isinstance(aligned, bool) else None,
        "h4": h4,
        "h1": h1,
        "m15": m15,
        "m5": m5,
        "atr": atr,
        "atr_pct": _atr_pct(atr, mid),
        "spread": spread,
        "mid": mid,
        "bos": bos,
        "choch": choch,
        "liquidity_sweep": liq,
        "fvg": fvg,
        "volume_score": vol_score,
        "volume_raw": volume_raw,
        "news_blocked": news_blocked,
        "quality": _i(quality.get("score")),
        "confluence": _i(confluence.get("total")),
        "adx_proxy": mtf,
        "range_width_proxy": _atr_pct(atr, mid),
    }


def classify_regime(cycle: dict[str, Any]) -> dict[str, Any]:
    """Classify one evaluation into primary/secondary regimes + confidence."""
    feat = _features_from_cycle(cycle)
    hits: list[tuple[str, int, str]] = []

    mtf = feat["mtf_score"]
    aligned = feat["mtf_aligned"]
    atr_pct = feat["atr_pct"]
    bos = int(feat["bos"] or 0)
    choch = int(feat["choch"] or 0)
    liq = int(feat["liquidity_sweep"] or 0)
    h4, h1, m15, m5 = feat["h4"], feat["h1"], feat["m15"], feat["m5"]

    trending = bool(aligned) or (mtf is not None and int(mtf) >= MTF_TREND_FLOOR)
    ranging = (mtf is not None or aligned is not None) and not trending

    if feat["news_blocked"]:
        hits.append((REGIME_NEWS_VOL, 92, "News blackout / news filter low"))

    if liq >= 70:
        hits.append(
            (REGIME_LIQ_SWEEP, min(95, 70 + liq // 5), f"Liquidity sweep score={liq}")
        )
    elif liq >= 40:
        hits.append(
            (REGIME_LIQ_SWEEP, 55 + liq // 4, f"Liquidity sweep soft={liq}")
        )

    if atr_pct is not None:
        if atr_pct >= float(ATR_HIGH_PCT):
            conf = min(95, int(70 + (atr_pct - float(ATR_HIGH_PCT)) * 10))
            hits.append(
                (REGIME_HIGH_VOL, conf, f"ATR%={atr_pct:.2f} >= {ATR_HIGH_PCT}")
            )
        elif atr_pct <= float(ATR_LOW_PCT):
            conf = min(90, int(70 + (float(ATR_LOW_PCT) - atr_pct) * 20))
            hits.append(
                (REGIME_LOW_VOL, conf, f"ATR%={atr_pct:.2f} <= {ATR_LOW_PCT}")
            )

    high_vol = atr_pct is not None and atr_pct >= float(ATR_HIGH_PCT)
    if bos >= 70 and (high_vol or (mtf is not None and mtf >= 75)):
        conf = 80 + (5 if high_vol else 0) + (5 if bos >= 90 else 0)
        hits.append(
            (
                REGIME_BREAKOUT,
                min(96, conf),
                f"BOS={bos}"
                + (" + vol expansion" if high_vol else " + strong MTF"),
            )
        )
    elif bos >= 70 and trending:
        hits.append((REGIME_BREAKOUT, 72, f"BOS={bos} with trend"))

    htf_bias = h4 if h4 in {"up", "down"} else (h1 if h1 in {"up", "down"} else "")
    ltf_against = False
    if htf_bias == "up" and (m15 == "down" or m5 == "down"):
        ltf_against = True
    if htf_bias == "down" and (m15 == "up" or m5 == "up"):
        ltf_against = True
    if htf_bias and ltf_against and (mtf is not None and 45 <= mtf < 85):
        hits.append(
            (
                REGIME_PULLBACK,
                78 if aligned is not True else 70,
                f"HTF {htf_bias} with LTF counter (M15={m15} M5={m5})",
            )
        )

    if trending:
        conf = 90 if aligned is True else (80 if mtf and mtf >= 80 else 72)
        if mtf is not None:
            conf = min(95, max(conf, 60 + int(mtf) // 3))
        hits.append(
            (REGIME_TRENDING, conf, f"MTF score={mtf} aligned={aligned}")
        )
    elif ranging:
        conf = 75 if aligned is False else 65
        if choch >= 70:
            conf = min(88, conf + 8)
        hits.append(
            (
                REGIME_RANGING,
                conf,
                f"MTF not aligned (score={mtf}, CHOCH={choch})",
            )
        )

    best: dict[str, tuple[int, str]] = {}
    for regime, conf, ev in hits:
        prev = best.get(regime)
        if prev is None or conf > prev[0]:
            best[regime] = (conf, ev)

    if not best:
        return {
            "primary": REGIME_UNKNOWN,
            "secondary": None,
            "regimes": [],
            "confidence": 0,
            "confidence_pct": 0,
            "evidence": ["Insufficient market artefacts"],
            "features": feat,
            "advisory_only": True,
        }

    ordered = sorted(
        best.items(),
        key=lambda kv: (
            _PRIMARY_PRIORITY.index(kv[0])
            if kv[0] in _PRIMARY_PRIORITY
            else 99,
            -kv[1][0],
        ),
    )
    primary = ordered[0][0]
    primary_conf = ordered[0][1][0]
    secondary = ordered[1][0] if len(ordered) > 1 else None
    evidence = [f"{r}: {best[r][1]}" for r, _ in ordered]

    return {
        "primary": primary,
        "secondary": secondary,
        "regimes": [
            {"regime": r, "confidence": best[r][0], "evidence": best[r][1]}
            for r, _ in ordered
        ],
        "confidence": primary_conf,
        "confidence_pct": primary_conf,
        "evidence": evidence,
        "features": feat,
        "advisory_only": True,
        "never_influences_execution": True,
    }


def cycle_regime_point(cycle: dict[str, Any]) -> dict[str, Any]:
    classified = classify_regime(cycle)
    return {
        "recorded_at": cycle.get("recorded_at"),
        "signal_id": cycle.get("signal_id"),
        "decision_action": str(cycle.get("decision_action") or "").upper()
        or "NO_TRADE",
        "primary": classified["primary"],
        "secondary": classified["secondary"],
        "confidence": classified["confidence"],
        "mtf_score": classified["features"].get("mtf_score"),
        "atr_pct": classified["features"].get("atr_pct"),
        "spread": classified["features"].get("spread"),
        "session": cycle.get("market_session"),
    }


def historical_performance_by_regime(
    trades: list[dict[str, Any]],
) -> dict[str, Any]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    mapping = {
        "TRENDING": REGIME_TRENDING,
        "RANGING": REGIME_RANGING,
        "HIGH_VOLATILITY": REGIME_HIGH_VOL,
        "LOW_VOLATILITY": REGIME_LOW_VOL,
        "HIGH VOLATILITY": REGIME_HIGH_VOL,
        "LOW VOLATILITY": REGIME_LOW_VOL,
        "BREAKOUT": REGIME_BREAKOUT,
        "PULLBACK": REGIME_PULLBACK,
        "NEWS VOLATILITY": REGIME_NEWS_VOL,
        "NEWS_DRIVEN": REGIME_NEWS_VOL,
        "LIQUIDITY SWEEP": REGIME_LIQ_SWEEP,
    }
    for t in trades:
        regime = str(t.get("regime_primary") or t.get("market_regime") or "").upper()
        regime = mapping.get(regime, regime)
        if not regime or regime in {"UNKNOWN", ""}:
            continue
        buckets[regime].append(t)

    out: dict[str, Any] = {}
    for regime, rows in buckets.items():
        if not rows:
            continue
        wins = [r for r in rows if (_f(r.get("profit_loss")) or 0) > 0]
        losses = [r for r in rows if (_f(r.get("profit_loss")) or 0) < 0]
        n = len(rows)
        win_rate = round(100.0 * len(wins) / n, 1) if n else None
        gross_win = sum(_f(r.get("profit_loss")) or 0 for r in wins)
        gross_loss = abs(sum(_f(r.get("profit_loss")) or 0 for r in losses))
        if gross_loss > 0:
            pf = round(gross_win / gross_loss, 2)
        elif gross_win > 0:
            pf = None
        else:
            pf = 0.0

        rr_vals = [
            x
            for x in (_f(r.get("risk_reward")) for r in rows)
            if x is not None
        ]
        expectancy = round(mean(rr_vals), 2) if rr_vals else None
        if expectancy is None and wins:
            avg_win = mean(_f(r.get("profit_loss")) or 0 for r in wins)
            avg_loss = (
                mean(abs(_f(r.get("profit_loss")) or 0) for r in losses)
                if losses
                else avg_win
            )
            if avg_loss > 0:
                p = len(wins) / n
                expectancy = round(p * (avg_win / avg_loss) - (1 - p) * 1.0, 2)

        out[regime] = {
            "regime": regime,
            "sample_size": n,
            "wins": len(wins),
            "losses": len(losses),
            "win_rate_pct": win_rate,
            "profit_factor": pf,
            "expectancy_r": expectancy,
            "expectancy_display": (
                f"{'+' if expectancy is not None and expectancy > 0 else ''}"
                f"{expectancy}R"
                if expectancy is not None
                else None
            ),
            "total_pnl": round(
                sum(_f(r.get("profit_loss")) or 0 for r in rows), 2
            ),
        }
    return out


def attach_regime_to_trades(
    trades: list[dict[str, Any]],
    cycles: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    from app.application.services.strategy_intelligence_center import (
        JOIN_WINDOW_SEC,
    )

    out: list[dict[str, Any]] = []
    for trade in trades:
        row = dict(trade)
        entry_ts = _parse_ts(row.get("entry_time"))
        best = None
        best_delta = None
        if entry_ts is not None:
            for c in cycles:
                cts = _parse_ts(c.get("recorded_at"))
                if cts is None:
                    continue
                delta = abs((cts - entry_ts).total_seconds())
                if delta > JOIN_WINDOW_SEC:
                    continue
                if best_delta is None or delta < best_delta:
                    best_delta = delta
                    best = c
        if best is not None:
            classified = classify_regime(best)
            row["regime_primary"] = classified["primary"]
            row["regime_secondary"] = classified["secondary"]
            row["regime_confidence"] = classified["confidence"]
        elif row.get("market_regime"):
            mr = str(row.get("market_regime") or "").lower()
            row["regime_primary"] = {
                "trending": REGIME_TRENDING,
                "ranging": REGIME_RANGING,
                "high_volatility": REGIME_HIGH_VOL,
                "low_volatility": REGIME_LOW_VOL,
            }.get(mr, REGIME_UNKNOWN)
        out.append(row)
    return out


def evaluation_card(
    cycle: dict[str, Any],
    *,
    performance: dict[str, Any] | None = None,
) -> dict[str, Any]:
    classified = classify_regime(cycle)
    primary = classified["primary"]
    perf = (performance or {}).get(primary) or {}
    return {
        "current_regime": primary,
        "secondary_regime": classified["secondary"],
        "confidence": classified["confidence"],
        "confidence_display": f"{classified['confidence']}%",
        "historical_performance": {
            "win_rate_pct": perf.get("win_rate_pct"),
            "win_rate_display": (
                f"{perf['win_rate_pct']}%"
                if perf.get("win_rate_pct") is not None
                else None
            ),
            "profit_factor": perf.get("profit_factor"),
            "expectancy_r": perf.get("expectancy_r"),
            "expectancy_display": perf.get("expectancy_display"),
            "sample_size": perf.get("sample_size"),
        },
        "regimes": classified["regimes"],
        "evidence": classified["evidence"],
        "features": classified["features"],
        "recorded_at": cycle.get("recorded_at"),
        "advisory_only": True,
        "never_influences_execution": True,
    }


def build_regime_distribution(
    points: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counter: Counter[str] = Counter()
    for p in points:
        primary = str(p.get("primary") or REGIME_UNKNOWN)
        counter[primary] += 1
    total = sum(counter.values()) or 1
    rows = [
        {
            "regime": regime,
            "count": counter.get(regime, 0),
            "share_pct": round(100.0 * counter.get(regime, 0) / total, 1),
        }
        for regime in ALL_REGIMES
        if counter.get(regime, 0) > 0
    ]
    if counter.get(REGIME_UNKNOWN, 0):
        rows.append(
            {
                "regime": REGIME_UNKNOWN,
                "count": counter[REGIME_UNKNOWN],
                "share_pct": round(
                    100.0 * counter[REGIME_UNKNOWN] / total, 1
                ),
            }
        )
    return rows


def build_market_regime_intelligence(
    *,
    diagnostics: dict[str, Any] | None = None,
    closed_trades: list[dict[str, Any]] | None = None,
    limit: int = HISTORY_WINDOW,
    skip_sic_trade_load: bool = False,
) -> dict[str, Any]:
    """Full Market Regime Dashboard payload (read-only)."""
    window = max(1, min(int(limit or HISTORY_WINDOW), HISTORY_WINDOW))

    if diagnostics is None:
        try:
            from app.application.services.strategy_diagnostics import (
                get_strategy_diagnostics_store,
            )

            diagnostics = get_strategy_diagnostics_store().snapshot(limit=window)
        except Exception:
            diagnostics = {"cycles": []}

    cycles = list((diagnostics or {}).get("cycles") or [])[:window]
    points = [cycle_regime_point(c) for c in cycles]
    points_chrono = list(reversed(points))

    trades = list(closed_trades or [])
    if not trades and not skip_sic_trade_load:
        try:
            from app.application.services.strategy_intelligence_center import (
                build_strategy_intelligence_center,
            )

            # Load enriched trades only — SIC embeds a compact regime summary
            # that uses skip_sic_trade_load to avoid recursion.
            sic = build_strategy_intelligence_center(
                days=90, diagnostics=diagnostics
            )
            trades = list(sic.get("trades") or [])
        except Exception:
            trades = []

    labeled = attach_regime_to_trades(trades, cycles)
    performance = historical_performance_by_regime(labeled)

    latest_cycle = cycles[0] if cycles else None
    current = (
        evaluation_card(latest_cycle, performance=performance)
        if latest_cycle
        else {
            "current_regime": REGIME_UNKNOWN,
            "secondary_regime": None,
            "confidence": 0,
            "confidence_display": "0%",
            "historical_performance": {},
            "regimes": [],
            "evidence": ["No live evaluations yet"],
            "advisory_only": True,
        }
    )

    return {
        "schema_version": "1.0.0",
        "mode": "market_regime_intelligence",
        "mutates_engines": False,
        "never_modifies_strategy_risk_safety_oms_thresholds_execution": True,
        "never_influences_trade_decisions": True,
        "advisory_only": True,
        "window": window,
        "count": len(points),
        "current": current,
        "regime_history": points,
        "regime_history_chronological": points_chrono,
        "regime_distribution": build_regime_distribution(points),
        "regime_performance": performance,
        "observed_at": datetime.now(UTC).isoformat(),
        "integrated_with_strategy_intelligence_center": True,
    }


def regime_summary_for_sic(
    *,
    diagnostics: dict[str, Any] | None = None,
    trades: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Compact block embedded into Strategy Intelligence Center payload."""
    full = build_market_regime_intelligence(
        diagnostics=diagnostics,
        closed_trades=trades,
        limit=HISTORY_WINDOW,
        skip_sic_trade_load=True,
    )
    cur = full.get("current") or {}
    return {
        "current_regime": cur.get("current_regime"),
        "secondary_regime": cur.get("secondary_regime"),
        "confidence": cur.get("confidence"),
        "confidence_display": cur.get("confidence_display"),
        "historical_performance": cur.get("historical_performance"),
        "regime_distribution": full.get("regime_distribution"),
        "dashboard_path": "/market-regime-intelligence",
        "advisory_only": True,
        "never_influences_trade_decisions": True,
    }
