"""XAUUSD strategy audit — read-only evidence + recommendations.

Never modifies ITEConfig, ConfluenceEngine, Risk, Safety, or Execution.
Never auto-changes production strategy rules.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.institutional_trading.config import ITEConfig
from app.domain.market_context.enums import MarketSession

# Minimum samples before a session/regime bucket is "adequate"
_MIN_SESSION_SAMPLES = 20
_MIN_REGIME_SAMPLES = 15
_MIN_NEWS_SAMPLES = 10


def _dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _session_key(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "london_ny_overlap": "overlap",
        "london_new_york_overlap": "overlap",
        "ny": "new_york",
        "asia": "tokyo",
    }
    return aliases.get(s, s or "unknown")


def _regime_key(raw: Any) -> str:
    s = str(raw or "").strip().lower().replace(" ", "_")
    if "trend" in s:
        return "trend"
    if "range" in s or "mean" in s:
        return "range"
    if "high" in s and "vol" in s:
        return "high_volatility"
    if "low" in s and "vol" in s:
        return "low_volatility"
    if "news" in s:
        return "news"
    return s or "unknown"


@dataclass(frozen=True, slots=True)
class ComponentFinding:
    component: str
    status: str  # consistent | complexity | gap | ui_only
    finding: str
    evidence: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status,
            "finding": self.finding,
            "evidence": self.evidence,
        }


@dataclass(frozen=True, slots=True)
class SignalQualityScore:
    score: int
    band: str
    reasons: tuple[str, ...]
    factors: dict[str, int]
    why_entry_allowed: str
    filter_opportunities: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "band": self.band,
            "reasons": list(self.reasons),
            "factors": dict(self.factors),
            "why_entry_allowed": self.why_entry_allowed,
            "filter_opportunities": list(self.filter_opportunities),
        }


@dataclass(frozen=True, slots=True)
class StrategyAuditReport:
    version: str
    never_auto_modifies_strategy: bool
    components: tuple[ComponentFinding, ...]
    signal_quality: SignalQualityScore | None
    entry_audit: dict[str, Any]
    exit_audit: dict[str, Any]
    no_trade_audit: dict[str, Any]
    session_performance: dict[str, Any]
    regime_performance: dict[str, Any]
    recommendations: tuple[str, ...]
    strengths: tuple[str, ...]
    weaknesses: tuple[str, ...]
    unknowns: tuple[str, ...]
    open_questions: tuple[str, ...]
    future_replay_plan: tuple[str, ...]
    evidence_summary: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "never_auto_modifies_strategy": self.never_auto_modifies_strategy,
            "never_modifies_risk_safety_execution": True,
            "components": [c.to_dict() for c in self.components],
            "signal_quality": (
                self.signal_quality.to_dict() if self.signal_quality else None
            ),
            "entry_audit": self.entry_audit,
            "exit_audit": self.exit_audit,
            "no_trade_audit": self.no_trade_audit,
            "session_performance": self.session_performance,
            "regime_performance": self.regime_performance,
            "recommendations": list(self.recommendations),
            "human_review": {
                "strengths": list(self.strengths),
                "weaknesses": list(self.weaknesses),
                "unknowns": list(self.unknowns),
                "open_questions": list(self.open_questions),
                "future_replay_plan": list(self.future_replay_plan),
            },
            "evidence_summary": self.evidence_summary,
        }


def audit_strategy_components(
    *,
    config: ITEConfig | None = None,
) -> tuple[ComponentFinding, ...]:
    """Static logical audit of SMC stack — no live mutation."""
    cfg = config or ITEConfig()
    allowed = ", ".join(s.value for s in cfg.allowed_sessions)
    return (
        ComponentFinding(
            component="Smart Money Concepts",
            status="consistent",
            finding=(
                "SMC is a composite of Structure + Liquidity + OB + FVG + MTF "
                "trend via ConfluenceEngine; requires an active OB or FVG zone"
            ),
            evidence="app/domain/institutional_trading/confluence.py (no_smc_zone)",
        ),
        ComponentFinding(
            component="BOS",
            status="consistent",
            finding=(
                "Break of Structure detected on primary TF (H1); contributes "
                "structure factor; directional bias from latest BOS"
            ),
            evidence="market_structure/structure_analyzer.py + confluence structure",
        ),
        ComponentFinding(
            component="CHOCH",
            status="consistent",
            finding=(
                "Change of Character tracked alongside BOS; both raise structure "
                "score when present — ensure direction agrees with MTF bias"
            ),
            evidence="market_structure models + confluence factors['structure']",
        ),
        ComponentFinding(
            component="Order Blocks",
            status="consistent",
            finding=(
                "OB engine validates/mitigates/breaks zones; confluence requires "
                "active OB or FVG for tradable direction"
            ),
            evidence="order_block/* + confluence order_blocks branch",
        ),
        ComponentFinding(
            component="Fair Value Gaps",
            status="consistent",
            finding=(
                "FVG detector + fill/invalidation/quality; pairs with OB as "
                "SMC zone requirement"
            ),
            evidence="fair_value_gap/* + confluence fvgs branch",
        ),
        ComponentFinding(
            component="Liquidity Sweeps",
            status="consistent",
            finding=(
                "Sweeps/pools/equal H/L feed liquidity factor; sweeps score "
                "higher than pools alone"
            ),
            evidence="liquidity/sweep_detector.py + confluence liquidity",
        ),
        ComponentFinding(
            component="Market Structure",
            status="consistent",
            finding=(
                "Swing → BOS/CHoCH → trend snapshot; pipeline order Structure "
                "before Liquidity/OB/FVG"
            ),
            evidence="institutional_trading/pipeline.py",
        ),
        ComponentFinding(
            component="Trend Filter",
            status="consistent",
            finding=(
                f"MTF hierarchy {cfg.macro_bias_tf.value}/"
                f"{cfg.primary_structure_tf.value}/"
                f"{cfg.entry_confirmation_tf.value}/"
                f"{cfg.execution_management_tf.value}; "
                "H4 must agree with H1 or confluence rejects mtf_not_aligned"
            ),
            evidence="trend_engine.py + confluence MTF gate",
        ),
        ComponentFinding(
            component="Session Filter",
            status="consistent",
            finding=(
                f"Default allowed sessions: {allowed}. "
                "Sydney/Tokyo classified but excluded from ITE entries by default"
            ),
            evidence="session_filter.py + ITEConfig.allowed_sessions",
        ),
        ComponentFinding(
            component="Volatility Filter",
            status="gap",
            finding=(
                "ATR soft/hard factors in confluence + robot volatility filter; "
                "qualitative VolatilityProfileResolver is observational — "
                "ensure live ATR always supplied on status polls"
            ),
            evidence="confluence ATR factors + ai_trading_robot/filters.py",
        ),
        ComponentFinding(
            component="Frontend strategy toggles",
            status="ui_only",
            finding=(
                "localStorage module toggles (SMC/BOS/CHOCH/OB/FVG/Sweep) do not "
                "gate ConfluenceEngine — cosmetic arming only; risk of operator "
                "believing modules are independently wired"
            ),
            evidence="frontend/src/lib/auto-trading/strategy-modules.ts",
        ),
        ComponentFinding(
            component="Dual signal paths",
            status="complexity",
            finding=(
                "Boolean StrategyRuntime preconditions exist alongside full ITE "
                "ConfluenceEngine — potential duplicated/conflicting signal "
                "surfaces if both are operator-facing"
            ),
            evidence="strategy_runtime.py vs institutional_decision_pipeline.py",
        ),
        ComponentFinding(
            component="News Protection",
            status="gap",
            finding=(
                "news_protection_enabled=False until calendar feed wired — "
                "news regime evidence cannot be claimed"
            ),
            evidence="ITEConfig.news_protection_enabled",
        ),
    )


def score_signal_quality(facts: dict[str, Any] | None) -> SignalQualityScore | None:
    """Score one strategy signal 0-100 from supplied facts only."""
    if not facts:
        return None

    factors: dict[str, int] = {}
    reasons: list[str] = []
    filters: list[str] = []

    def _bool(key: str) -> bool | None:
        if key not in facts or facts[key] is None:
            return None
        return bool(facts[key])

    # Weights sum to 100
    mtf = _bool("mtf_aligned")
    if mtf is True:
        factors["trend"] = 20
        reasons.append("Trend aligned (MTF)")
    elif mtf is False:
        factors["trend"] = 0
        filters.append("Require H4/H1 alignment before entry")
    else:
        factors["trend"] = 10
        reasons.append("Trend alignment unknown — partial credit")

    bos = _bool("bos")
    choch = _bool("choch")
    if bos or choch:
        factors["structure"] = 15 if (bos and choch) else 12
        if bos:
            reasons.append("BOS present")
        if choch:
            reasons.append("CHOCH present")
    else:
        factors["structure"] = 0
        filters.append("Wait for BOS or CHOCH on primary structure TF")

    sweep = _bool("liquidity_sweep")
    if sweep is True:
        factors["liquidity"] = 15
        reasons.append("Liquidity sweep confirmed")
    elif sweep is False:
        factors["liquidity"] = 5
        filters.append("Prefer entries after liquidity sweep reclaim")
    else:
        factors["liquidity"] = 8
        reasons.append("Liquidity context unknown")

    ob = _bool("order_block")
    if ob is True:
        factors["order_block"] = 15
        reasons.append("SMC order block aligned")
    elif ob is False:
        factors["order_block"] = 0
        filters.append("Require active order block or FVG zone")
    else:
        factors["order_block"] = 7

    fvg = _bool("fair_value_gap")
    if fvg is True:
        factors["fair_value_gap"] = 10
        reasons.append("Fair value gap present")
    elif fvg is False:
        factors["fair_value_gap"] = 0
    else:
        factors["fair_value_gap"] = 5

    session_ok = _bool("session_allowed")
    if session_ok is True:
        factors["session"] = 10
        reasons.append("Session filter passed")
    elif session_ok is False:
        factors["session"] = 0
        filters.append("Skip Sydney/Tokyo/off-hours unless policy expanded")
    else:
        factors["session"] = 5

    spread_ok = _bool("spread_acceptable")
    if spread_ok is True:
        factors["spread"] = 10
        reasons.append("Spread acceptable")
    elif spread_ok is False:
        factors["spread"] = 0
        filters.append("Reject when spread exceeds max_spread_reject")
    else:
        factors["spread"] = 5

    vol_ok = _bool("volatility_acceptable")
    if vol_ok is True:
        # Informational — ATR already enforced in confluence/risk; no extra points
        factors["volatility"] = 0
        reasons.append("Volatility filter passed")
    elif vol_ok is False:
        factors["volatility"] = 0
        filters.append("Filter high/low volatility extremes via ATR band")
    else:
        factors["volatility"] = 0

    # SMC composite bonus note
    if (ob is True or fvg is True) and (mtf is True):
        reasons.append("SMC aligned")

    score = max(0, min(100, sum(factors.values())))
    if score >= 90:
        band = "high_confidence"
    elif score >= 80:
        band = "tradable"
    else:
        band = "reject"

    why = (
        "; ".join(reasons)
        if reasons
        else "Insufficient supplied factors to justify entry"
    )
    return SignalQualityScore(
        score=score,
        band=band,
        reasons=tuple(reasons),
        factors=factors,
        why_entry_allowed=why,
        filter_opportunities=tuple(dict.fromkeys(filters)),
    )


def _bucket_trades(
    trades: list[dict[str, Any]],
    *,
    key_fn: Any,
) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for t in trades:
        buckets[key_fn(t)].append(t)
    out: dict[str, dict[str, Any]] = {}
    for key, rows in sorted(buckets.items()):
        wins = losses = 0
        pnl_sum = Decimal("0")
        rrs: list[Decimal] = []
        for t in rows:
            pnl = _dec(t.get("pnl") or t.get("net_pnl")) or Decimal("0")
            pnl_sum += pnl
            if isinstance(t.get("win"), bool):
                if t["win"]:
                    wins += 1
                else:
                    losses += 1
            elif pnl > 0:
                wins += 1
            elif pnl < 0:
                losses += 1
            rr = _dec(t.get("rr") or t.get("r_multiple") or t.get("reward_risk"))
            if rr is not None:
                rrs.append(rr)
        n = wins + losses
        out[key] = {
            "trades": len(rows),
            "wins": wins,
            "losses": losses,
            "win_rate": round(wins / n, 4) if n else None,
            "net_pnl": str(pnl_sum),
            "avg_rr": str(
                (sum(rrs) / Decimal(len(rrs))).quantize(Decimal("0.01"))
            )
            if rrs
            else None,
            "mixed_with_other_buckets": False,
        }
    return out


def audit_entries(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "status": "insufficient_data",
            "message": "No completed trades supplied — never fabricates entry quality",
        }
    late = early = 0
    reasons: list[str] = []
    for t in trades:
        timing = str(t.get("entry_timing") or "").lower()
        if "late" in timing:
            late += 1
        if "early" in timing:
            early += 1
        why = t.get("entry_reason") or t.get("why") or t.get("decision_reason")
        if why:
            reasons.append(str(why))
    return {
        "status": "available" if (late + early + len(reasons)) else "partial",
        "sample_size": len(trades),
        "late_entries": late,
        "early_entries": early,
        "sample_reasons": reasons[:12],
        "could_have_been_filtered": late + early,
        "note": "From supplied trade fields only",
    }


def audit_exits(trades: list[dict[str, Any]]) -> dict[str, Any]:
    if not trades:
        return {
            "status": "insufficient_data",
            "message": "No completed trades supplied — never fabricates exit quality",
        }
    winners: list[Decimal] = []
    losers: list[Decimal] = []
    rrs: list[Decimal] = []
    early_ex = late_ex = stopouts = 0
    for t in trades:
        pnl = _dec(t.get("pnl") or t.get("net_pnl"))
        if pnl is not None:
            if pnl > 0:
                winners.append(pnl)
            elif pnl < 0:
                losers.append(abs(pnl))
        rr = _dec(t.get("rr") or t.get("r_multiple") or t.get("reward_risk"))
        if rr is not None:
            rrs.append(rr)
        exit_timing = str(t.get("exit_timing") or t.get("exit_quality") or "").lower()
        if "early" in exit_timing or "premature" in exit_timing:
            early_ex += 1
        if "late" in exit_timing:
            late_ex += 1
        cause = str(t.get("exit_cause") or t.get("stop_reason") or "").lower()
        if "stop" in cause:
            stopouts += 1
    return {
        "status": "available",
        "sample_size": len(trades),
        "average_winner": str(
            (sum(winners) / Decimal(len(winners))).quantize(Decimal("0.01"))
        )
        if winners
        else None,
        "average_loser": str(
            (sum(losers) / Decimal(len(losers))).quantize(Decimal("0.01"))
        )
        if losers
        else None,
        "rr_achieved_avg": str(
            (sum(rrs) / Decimal(len(rrs))).quantize(Decimal("0.01"))
        )
        if rrs
        else None,
        "early_exits": early_ex,
        "late_exits": late_ex,
        "stop_out_count": stopouts,
        "note": "Sessions/regimes must be reviewed in separate buckets",
    }


def audit_no_trade(decisions: list[dict[str, Any]] | None) -> dict[str, Any]:
    if not decisions:
        return {
            "status": "insufficient_data",
            "message": (
                "No decision journal supplied — cannot prove No Trade reduced losses"
            ),
            "recommendation": "Need more No-Trade / reject decision samples tagged",
        }
    no_trade = [
        d
        for d in decisions
        if str(d.get("decision") or d.get("action") or "")
        .upper()
        .replace(" ", "_")
        in {"NO_TRADE", "REJECT", "WATCH", "BLOCKED"}
    ]
    return {
        "status": "available",
        "total_decisions": len(decisions),
        "no_trade_count": len(no_trade),
        "no_trade_rate": round(len(no_trade) / len(decisions), 4)
        if decisions
        else None,
        "sample_reasons": [
            str(d.get("reason") or d.get("rejected") or d.get("why") or "")
            for d in no_trade[:15]
            if (d.get("reason") or d.get("rejected") or d.get("why"))
        ],
        "assessment": (
            "No Trade path exists in TradeDecisionEngine; "
            "loss-reduction proof requires paired counterfactual replay"
        ),
    }


def build_recommendations(
    *,
    session_perf: dict[str, Any],
    regime_perf: dict[str, Any],
    components: tuple[ComponentFinding, ...],
    trade_count: int,
    decision_count: int,
) -> tuple[str, ...]:
    recs: list[str] = []
    sessions = session_perf.get("buckets") or {}
    for name in ("sydney", "tokyo", "london", "new_york", "overlap"):
        n = int((sessions.get(name) or {}).get("trades") or 0)
        if n < _MIN_SESSION_SAMPLES:
            label = name.replace("_", " ").title()
            recs.append(
                f"Need more {label} evidence "
                f"(have {n}, want >={_MIN_SESSION_SAMPLES})"
            )

    regimes = regime_perf.get("buckets") or {}
    for name, label in (
        ("trend", "Trend"),
        ("range", "Range"),
        ("high_volatility", "High Volatility"),
        ("low_volatility", "Low Volatility"),
        ("news", "News"),
    ):
        n = int((regimes.get(name) or {}).get("trades") or 0)
        need = _MIN_NEWS_SAMPLES if name == "news" else _MIN_REGIME_SAMPLES
        if n < need:
            recs.append(
                f"Need more {label} samples (have {n}, want >={need})"
            )

    if trade_count < 50:
        recs.append(
            f"Need more completed XAUUSD trade samples "
            f"(have {trade_count}, want >=50)"
        )
    if decision_count < 100:
        recs.append(
            "Need more Decision Engine NO_TRADE / WATCH samples for refusal quality"
        )

    for c in components:
        if c.status == "gap" and "News" in c.component:
            recs.append("Need more News replay once calendar blackout is wired")
        if c.status == "ui_only":
            recs.append(
                "Clarify operator UX: frontend strategy toggles are preferences only"
            )
        if c.status == "complexity":
            recs.append(
                "Prefer single operator-facing signal path (ITE Confluence) "
                "to avoid duplicated signals"
            )

    # Deduplicate preserving order
    return tuple(dict.fromkeys(recs))


def build_strategy_audit(
    *,
    trades: list[dict[str, Any]] | None = None,
    decisions: list[dict[str, Any]] | None = None,
    signal_facts: dict[str, Any] | None = None,
    config: ITEConfig | None = None,
    version: str = "1.0.1",
) -> StrategyAuditReport:
    """Full read-only audit. Recommendations only — never mutates strategy."""
    rows = [t for t in (trades or []) if isinstance(t, dict)]
    decs = [d for d in (decisions or []) if isinstance(d, dict)]
    components = audit_strategy_components(config=config)
    quality = score_signal_quality(signal_facts)

    session_buckets = _bucket_trades(
        rows,
        key_fn=lambda t: _session_key(
            t.get("session") or t.get("trading_session") or t.get("session_name")
        ),
    )
    regime_buckets = _bucket_trades(
        rows,
        key_fn=lambda t: _regime_key(
            t.get("regime") or t.get("market_regime") or t.get("regime_label")
        ),
    )
    session_perf = {
        "status": "available" if rows else "insufficient_data",
        "buckets": session_buckets,
        "note": "Sessions never mixed — each bucket is independent",
    }
    regime_perf = {
        "status": "available" if rows else "insufficient_data",
        "buckets": regime_buckets,
        "note": "Regimes never mixed — each bucket is independent",
    }

    recs = build_recommendations(
        session_perf=session_perf,
        regime_perf=regime_perf,
        components=components,
        trade_count=len(rows),
        decision_count=len(decs),
    )

    return StrategyAuditReport(
        version=version,
        never_auto_modifies_strategy=True,
        components=components,
        signal_quality=quality,
        entry_audit=audit_entries(rows),
        exit_audit=audit_exits(rows),
        no_trade_audit=audit_no_trade(decs),
        session_performance=session_perf,
        regime_performance=regime_perf,
        recommendations=recs,
        strengths=(
            "Deterministic SMC confluence with MTF alignment hard gate",
            "OB or FVG zone required — reduces naked structure entries",
            "Session filter defaults to London / New York / Overlap only",
            "Trade quality score (0-100) with explicit reject band",
            "NO_TRADE / WATCH decisions exist before OMS",
            "PME exit ladder (BE / partial / trail) is separate from entry logic",
        ),
        weaknesses=(
            "Frontend strategy toggles do not wire into ConfluenceEngine",
            "Dual signal surfaces (StrategyRuntime vs ITE) add complexity",
            "News protection disabled — news regime unproven",
            "Sparse live journals limit session/regime statistical power",
            "ATR volatility may be unevaluated on status-only polls",
        ),
        unknowns=(
            "Realized RR by session without tagged live deals",
            "Whether No Trade decisions reduced losses (needs counterfactual replay)",
            "Sydney/Tokyo edge if sessions were ever enabled",
            "Stop-out causes distribution without exit_cause tags",
        ),
        open_questions=(
            "Should operator UI hide localStorage toggles or bind them "
            "read-only to ITE?",
            "Minimum sample size per session before expanding allowed_sessions?",
            "When should news_protection_enabled flip after calendar certification?",
            "Is StrategyRuntime still needed for operator desks?",
        ),
        future_replay_plan=(
            "Replay London-only XAUUSD bars with confluence journal export",
            "Replay New York + Overlap separately — never mix buckets",
            "Tagged News blackout replay once calendar feed is certified",
            "Trend vs Range labeled walk-forward with fixed ITEConfig",
            "No-Trade counterfactual: apply rejected signals hypothetically offline",
        ),
        evidence_summary={
            "completed_trades": len(rows),
            "decisions": len(decs),
            "signal_facts_supplied": signal_facts is not None,
            "recommendation_count": len(recs),
            "component_findings": len(components),
            "source": "read_only_xauusd_strategy_audit",
        },
    )


# Explicit session enum coverage for audits (never mix)
SESSION_BUCKETS: tuple[str, ...] = (
    MarketSession.SYDNEY.value,
    MarketSession.TOKYO.value,
    MarketSession.LONDON.value,
    MarketSession.NEW_YORK.value,
    MarketSession.LONDON_NY_OVERLAP.value,
)
