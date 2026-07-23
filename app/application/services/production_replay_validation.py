"""Production Replay & Validation — simulation-only walk-forward evidence.

Walks historical (or synthetic) XAUUSD multi-timeframe bars, evaluates the
*unchanged* institutional analysis + decision pipeline at each eligible M15
close, and records what would have happened. Never places an order, never
touches the OMS / MT5 gateway, and never mutates RiskEngine, SafetyEngine, or
the strategy pipeline — it only calls their public, read-only entry points
with caller-supplied bars and account state.

Reused unchanged:
- ``InstitutionalTradingAnalysisService.analyze_bars``
- ``InstitutionalDecisionPipeline.run``
- ``classify_session_utc`` / the London / New York / London-NY-overlap gate

This module owns only: bar construction (synthetic or injected), time-walk
slicing, and evidence aggregation/reporting.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from random import Random
from time import perf_counter
from typing import Any

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.institutional_trading_analysis import (
    InstitutionalTradingAnalysisService,
)
from app.domain.institutional_trading.atr import compute_atr
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    DecisionAction,
    TradeDecision,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.market_context.enums import MarketSession
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.value_objects.identity import SymbolCode

ALLOWED_SESSIONS: frozenset[MarketSession] = frozenset(
    {
        MarketSession.LONDON,
        MarketSession.NEW_YORK,
        MarketSession.LONDON_NY_OVERLAP,
    }
)

_MIN_HISTORY_PER_TF = 50
_CANDLE_BUFFER = 600  # keep well above ITEConfig.candle_limit (500)
_TRADE_ACTIONS = frozenset({DecisionAction.BUY, DecisionAction.SELL})

_REQUIRED_TIMEFRAMES: tuple[Timeframe, ...] = (
    Timeframe.H4,
    Timeframe.H1,
    Timeframe.M15,
    Timeframe.M5,
)

# Aggregation factor relative to M5 (5-minute bars).
_AGG_FACTOR_FROM_M5: dict[Timeframe, int] = {
    Timeframe.M15: 3,
    Timeframe.H1: 12,
    Timeframe.H4: 48,
}


# --------------------------------------------------------------------------
# Synthetic deterministic bar generator (no MT5 / network dependency)
# --------------------------------------------------------------------------


def _generate_m5_series(
    *,
    days: int,
    end: datetime,
    base_price: Decimal = Decimal("2300"),
    seed: int = 20_260_101,
) -> list[Candle]:
    """Deterministic sine-wave + seeded-noise XAUUSD M5 path.

    Fully reproducible for a given ``days``/``end``/``seed`` — no live data,
    no MT5 dependency. Used only so unit tests and empty environments have a
    bar source; production callers should inject real ``bars_by_tf``.
    """
    step = timedelta(minutes=5)
    bars = max(60, int(days * 24 * 60 / 5))
    start = end - step * bars
    rng = Random(seed)  # noqa: S311 - deterministic synthetic data, not crypto
    base = float(base_price)
    price = base
    code = SymbolCode(value=GOLD_SYMBOL)
    out: list[Candle] = []
    for i in range(bars):
        open_time = start + step * i
        close_time = open_time + step
        drift = math.sin(i / 288.0) * 6.0 + math.sin(i / 48.0) * 2.5
        target = base + drift
        move = (target - price) * 0.08 + (rng.random() - 0.5) * 0.6
        o = price
        c = price + move
        hi = max(o, c) + 0.3 + rng.random() * 0.4
        lo = min(o, c) - 0.3 - rng.random() * 0.4
        out.append(
            Candle.create(
                symbol_code=code,
                timeframe=Timeframe.M5,
                open_time=open_time,
                close_time=close_time,
                open=f"{o:.2f}",
                high=f"{hi:.2f}",
                low=f"{lo:.2f}",
                close=f"{c:.2f}",
                volume="1",
            )
        )
        price = c
    return out


def _aggregate_candles(
    candles: list[Candle], *, factor: int, timeframe: Timeframe
) -> list[Candle]:
    """Simple OHLC roll-up of ``factor`` consecutive finer candles."""
    out: list[Candle] = []
    usable = len(candles) - (len(candles) % factor)
    for start_idx in range(0, usable, factor):
        chunk = candles[start_idx : start_idx + factor]
        hi = max(c.high.value for c in chunk)
        lo = min(c.low.value for c in chunk)
        vol = sum((c.volume for c in chunk), Decimal("0"))
        out.append(
            Candle.create(
                symbol_code=chunk[0].symbol_code.value,
                timeframe=timeframe,
                open_time=chunk[0].open_time,
                close_time=chunk[-1].close_time,
                open=str(chunk[0].open),
                high=str(hi),
                low=str(lo),
                close=str(chunk[-1].close),
                volume=str(vol),
            )
        )
    return out


def build_synthetic_bars(
    days: int = 30, *, end: datetime | None = None
) -> dict[Timeframe, list[Candle]]:
    """Deterministic multi-TF (H4/H1/M15/M5) synthetic XAUUSD bar set."""
    anchor = end or datetime.now(UTC).replace(
        minute=0, second=0, microsecond=0
    )
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=UTC)
    m5 = _generate_m5_series(days=days, end=anchor)
    return {
        Timeframe.M5: m5,
        Timeframe.M15: _aggregate_candles(
            m5, factor=_AGG_FACTOR_FROM_M5[Timeframe.M15], timeframe=Timeframe.M15
        ),
        Timeframe.H1: _aggregate_candles(
            m5, factor=_AGG_FACTOR_FROM_M5[Timeframe.H1], timeframe=Timeframe.H1
        ),
        Timeframe.H4: _aggregate_candles(
            m5, factor=_AGG_FACTOR_FROM_M5[Timeframe.H4], timeframe=Timeframe.H4
        ),
    }


def _normalize_bars_by_tf(
    bars_by_tf: dict[Timeframe | str, list[Candle]],
) -> dict[Timeframe, list[Candle]]:
    """Coerce keys to ``Timeframe`` and derive missing TFs by aggregation."""
    normalized: dict[Timeframe, list[Candle]] = {}
    for raw_tf, candles in bars_by_tf.items():
        tf = raw_tf if isinstance(raw_tf, Timeframe) else Timeframe.parse(str(raw_tf))
        normalized[tf] = sorted(candles, key=lambda c: c.close_time)

    if Timeframe.M15 not in normalized:
        raise ValueError("bars_by_tf must include at least Timeframe.M15")

    base_tf = Timeframe.M5 if Timeframe.M5 in normalized else Timeframe.M15
    base_candles = normalized[base_tf]
    base_minutes = {Timeframe.M5: 5, Timeframe.M15: 15}[base_tf]

    for tf in _REQUIRED_TIMEFRAMES:
        if tf in normalized:
            continue
        target_minutes = {
            Timeframe.M15: 15,
            Timeframe.H1: 60,
            Timeframe.H4: 240,
        }[tf]
        factor = max(1, target_minutes // base_minutes)
        normalized[tf] = _aggregate_candles(base_candles, factor=factor, timeframe=tf)

    return normalized


# --------------------------------------------------------------------------
# Evaluation record
# --------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _Opportunity:
    timestamp: datetime
    session: str
    signal_id: str
    quality: int
    confluence: int
    action: str
    risk_result: str
    safety_result: str
    would_reach_oms: str
    would_reach_mt5: str
    rejection_reason: str
    latency_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "session": self.session,
            "signal_id": self.signal_id,
            "quality": self.quality,
            "confluence": self.confluence,
            "action": self.action,
            "risk_result": self.risk_result,
            "safety_result": self.safety_result,
            "would_reach_oms": self.would_reach_oms,
            "would_reach_mt5": self.would_reach_mt5,
            "rejection_reason": self.rejection_reason,
            "latency_ms": round(self.latency_ms, 3),
        }


def _compute_atr(candles: list[Candle], *, period: int = 14) -> Decimal | None:
    """Delegate to shared ITE ATR helper (same TR-window average)."""
    return compute_atr(candles, period=period)


def _rejection_reason(decision: TradeDecision) -> str:
    if decision.action in _TRADE_ACTIONS:
        return ""
    reasons = list(dict.fromkeys(decision.eligibility.rejection_reasons))
    reasons.extend(r for r in decision.risk_reasons if r not in reasons)
    if not reasons:
        reasons.extend(
            r for r in decision.confluence.rejected_rules if r not in reasons
        )
    return "; ".join(reasons) if reasons else "no_qualifying_signal"


def _quality_bucket(score: int) -> str:
    if score >= 90:
        return "90-100"
    if score >= 80:
        return "80-89"
    if score >= 60:
        return "60-79"
    return "0-59"


async def _evaluate_as_of(
    *,
    as_of: datetime,
    session: MarketSession,
    sliced_bars: dict[Timeframe, list[Candle]],
    equity: Decimal,
    idx: int,
) -> _Opportunity:
    started = perf_counter()
    atr = _compute_atr(sliced_bars[Timeframe.M15])
    mid = sliced_bars[Timeframe.M15][-1].close.value

    account = AccountRiskState(
        equity=equity,
        peak_equity=equity,
        daily_pnl=Decimal("0"),
        weekly_pnl=Decimal("0"),
        open_positions=0,
        already_in_trade=False,
        consecutive_losses=0,
        cooldown_active=False,
        cooldown_remaining_minutes=0,
        market_open=True,
        atr=atr,
        mid_price=mid,
        free_margin=equity,
    )

    analysis_service = InstitutionalTradingAnalysisService()
    snapshot: MarketAnalysisSnapshot = await analysis_service.analyze_bars(
        sliced_bars,
        as_of=as_of,
        spread=Decimal("0.30"),
    )
    decision = InstitutionalDecisionPipeline().run(
        snapshot,
        account,
        request_id=f"replay_{idx}_{snapshot.input_hash[:12]}",
    )
    latency_ms = (perf_counter() - started) * 1000.0

    would_trade = decision.action in _TRADE_ACTIONS
    return _Opportunity(
        timestamp=as_of,
        session=session.value,
        signal_id=str(decision.id),
        quality=decision.quality,
        confluence=decision.confluence.confidence,
        action=decision.action.value,
        risk_result="PASS" if not decision.risk_reasons else "FAIL",
        safety_result="PASS" if snapshot.session.allowed else "BLOCK",
        would_reach_oms="YES" if would_trade else "NO",
        would_reach_mt5="YES" if would_trade else "NO",
        rejection_reason=_rejection_reason(decision),
        latency_ms=latency_ms,
    )


def _select_walk_points(
    eligible: list[tuple[int, datetime]], *, max_evaluations: int
) -> list[tuple[int, datetime]]:
    """Evenly sample eligible M15 close times, capped at ``max_evaluations``."""
    if max_evaluations <= 0 or not eligible:
        return []
    if len(eligible) <= max_evaluations:
        return eligible
    step = math.ceil(len(eligible) / max_evaluations)
    return eligible[::step][:max_evaluations]


# --------------------------------------------------------------------------
# Aggregation + markdown reporting
# --------------------------------------------------------------------------


def _aggregate_statistics(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(opportunities)
    signals = sum(1 for o in opportunities if o["would_reach_oms"] == "YES")
    rejected = total - signals
    session_dist = Counter(o["session"] for o in opportunities)
    quality_buckets = Counter(_quality_bucket(int(o["quality"])) for o in opportunities)
    confluence_buckets = Counter(
        _quality_bucket(int(o["confluence"])) for o in opportunities
    )
    latencies = [float(o["latency_ms"]) for o in opportunities]
    avg_latency_ms = round(sum(latencies) / len(latencies), 3) if latencies else 0.0
    reason_counts = Counter(
        o["rejection_reason"] for o in opportunities if o["rejection_reason"]
    )
    rejection_reasons_ranked = [
        {"reason": reason, "count": count}
        for reason, count in reason_counts.most_common(20)
    ]

    return {
        "total_evaluations": total,
        "signals": signals,
        "rejected": rejected,
        "would_execute_count": signals,
        "session_distribution": dict(session_dist),
        "quality_buckets": dict(quality_buckets),
        "confluence_buckets": dict(confluence_buckets),
        "avg_latency_ms": avg_latency_ms,
        "rejection_reasons_ranked": rejection_reasons_ranked,
    }


async def run_production_replay(
    *,
    days: int = 30,
    max_evaluations: int = 120,
    bars_by_tf: dict[Timeframe | str, list[Candle]] | None = None,
    equity: Decimal = Decimal("10000"),
) -> dict[str, Any]:
    """Walk-forward replay of the *unchanged* ITE pipeline. Never trades.

    Builds (or accepts) multi-timeframe XAUUSD bars, walks eligible M15
    close times (London / New York / London-NY-overlap only), and records
    what the existing analysis + decision pipeline would have produced.
    """
    generated_at = datetime.now(UTC)
    normalized = (
        _normalize_bars_by_tf(bars_by_tf)
        if bars_by_tf
        else build_synthetic_bars(days)
    )

    m15 = normalized.get(Timeframe.M15, [])
    close_times_by_tf: dict[Timeframe, list[datetime]] = {
        tf: [c.close_time for c in candles] for tf, candles in normalized.items()
    }

    eligible: list[tuple[int, datetime]] = []
    for i, candle in enumerate(m15):
        as_of = candle.close_time
        session = classify_session_utc(as_of)
        if session in ALLOWED_SESSIONS:
            eligible.append((i, as_of))

    walk_points = _select_walk_points(eligible, max_evaluations=max_evaluations)

    opportunities: list[dict[str, Any]] = []
    for eval_idx, (_, as_of) in enumerate(walk_points):
        sliced: dict[Timeframe, list[Candle]] = {}
        sufficient = True
        for tf in _REQUIRED_TIMEFRAMES:
            series = normalized.get(tf, [])
            times = close_times_by_tf.get(tf, [])
            cutoff = bisect_right(times, as_of)
            if cutoff < _MIN_HISTORY_PER_TF:
                sufficient = False
                break
            sliced[tf] = series[max(0, cutoff - _CANDLE_BUFFER) : cutoff]
        if not sufficient:
            continue

        session = classify_session_utc(as_of)
        opportunity = await _evaluate_as_of(
            as_of=as_of,
            session=session,
            sliced_bars=sliced,
            equity=equity,
            idx=eval_idx,
        )
        opportunities.append(opportunity.to_dict())
        if len(opportunities) >= max_evaluations:
            break

    statistics = _aggregate_statistics(opportunities)

    return {
        "schema_version": "1.0.0",
        "generated_at": generated_at.isoformat(),
        "symbol": GOLD_SYMBOL,
        "simulation_only": True,
        "order_send_called": False,
        "mt5_order_send_invoked": False,
        "strategy_engine_modified": False,
        "risk_engine_modified": False,
        "safety_engine_modified": False,
        "allowed_sessions": sorted(s.value for s in ALLOWED_SESSIONS),
        "params": {
            "days": days,
            "max_evaluations": max_evaluations,
            "equity": str(equity),
        },
        "eligible_bars_considered": len(eligible),
        "opportunities": opportunities,
        "statistics": statistics,
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    """Render a replay report dict as a human-readable markdown document."""
    stats = report.get("statistics") or {}
    params = report.get("params") or {}
    lines: list[str] = []
    lines.append("# Production Replay & Validation Report")
    lines.append("")
    lines.append(f"- Generated at: `{report.get('generated_at', '—')}`")
    lines.append(f"- Symbol: `{report.get('symbol', '—')}` (gold-only)")
    lines.append(
        f"- Window: last **{params.get('days', '—')}** days · "
        f"max evaluations **{params.get('max_evaluations', '—')}** · "
        f"equity **{params.get('equity', '—')}**"
    )
    lines.append(
        "- Simulation only — `order_send_called: "
        f"{report.get('order_send_called', False)}` "
        "(never places orders, never mutates Risk/Safety/strategy engines)"
    )
    lines.append(
        f"- Sessions allowed: {', '.join(report.get('allowed_sessions', []))}"
    )
    lines.append("")
    lines.append("## Statistics")
    lines.append("")
    lines.append(f"- Total evaluations: **{stats.get('total_evaluations', 0)}**")
    lines.append(f"- Signals (would reach OMS): **{stats.get('signals', 0)}**")
    lines.append(f"- Rejected / no-trade: **{stats.get('rejected', 0)}**")
    lines.append(f"- Average latency: **{stats.get('avg_latency_ms', 0)} ms**")
    lines.append("")
    lines.append("### Session distribution")
    lines.append("")
    for session, count in (stats.get("session_distribution") or {}).items():
        lines.append(f"- `{session}`: {count}")
    lines.append("")
    lines.append("### Quality buckets")
    lines.append("")
    for bucket, count in (stats.get("quality_buckets") or {}).items():
        lines.append(f"- `{bucket}`: {count}")
    lines.append("")
    lines.append("### Confluence buckets")
    lines.append("")
    for bucket, count in (stats.get("confluence_buckets") or {}).items():
        lines.append(f"- `{bucket}`: {count}")
    lines.append("")
    lines.append("### Rejection reasons (ranked)")
    lines.append("")
    ranked = stats.get("rejection_reasons_ranked") or []
    if not ranked:
        lines.append("- _None recorded_")
    for row in ranked:
        lines.append(f"- `{row.get('reason')}`: {row.get('count')}")
    lines.append("")
    lines.append("## Opportunities")
    lines.append("")
    opportunities = report.get("opportunities") or []
    if not opportunities:
        lines.append("_No eligible opportunities in this window._")
    else:
        lines.append(
            "| Timestamp | Session | Signal ID | Quality | Confluence | Action | "
            "Risk | Safety | OMS | MT5 | Rejection Reason |"
        )
        lines.append(
            "|---|---|---|---|---|---|---|---|---|---|---|"
        )
        for o in opportunities:
            lines.append(
                f"| {o.get('timestamp')} | {o.get('session')} | "
                f"{str(o.get('signal_id'))[:8]} | {o.get('quality')} | "
                f"{o.get('confluence')} | {o.get('action')} | "
                f"{o.get('risk_result')} | {o.get('safety_result')} | "
                f"{o.get('would_reach_oms')} | {o.get('would_reach_mt5')} | "
                f"{o.get('rejection_reason') or '—'} |"
            )
    lines.append("")
    return "\n".join(lines)
