"""Offline institutional execution validation — prove full pipeline on real setups.

Walks historical (or deterministic synthetic) XAUUSD bars through the *unchanged*
production analysis + decision + safety + execution bridge path. When a setup
satisfies all production gates, replays it through OMS → MT5 Gateway → Broker
using a simulated offline OMS (never calls live ``order_send``).

Hard constraints:
- Does not modify strategy, MTF, quality/confluence thresholds, risk %, or safety
- Does not fabricate BUY/SELL signals
- Does not force trades
- Reports honestly when no qualifying setup exists in the window
"""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.application.services.institutional_decision_pipeline import (
    InstitutionalDecisionPipeline,
)
from app.application.services.institutional_execution_integration import (
    InstitutionalExecutionIntegration,
)
from app.application.services.institutional_oms_adapter import RecordingOmsPort
from app.application.services.institutional_trading_analysis import (
    InstitutionalTradingAnalysisService,
)
from app.application.services.production_replay_validation import (
    ALLOWED_SESSIONS,
    _CANDLE_BUFFER,
    _MIN_HISTORY_PER_TF,
    _REQUIRED_TIMEFRAMES,
    _compute_atr,
    _normalize_bars_by_tf,
    _select_walk_points,
    build_synthetic_bars,
)
from app.domain.institutional_trading.auto_trading import (
    AutoTradeLiveFacts,
    evaluate_auto_trade_safety,
)
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    DecisionAction,
    TradeDecision,
)
from app.domain.institutional_trading.execution.config import ExecutionBridgeConfig
from app.domain.institutional_trading.execution.models import (
    ExecutionBridgeContext,
    ExecutionMode,
    OmsSubmitResult,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
)
from app.domain.institutional_trading.operations.models import OpsExecutionMode
from app.domain.institutional_trading.session_filter import classify_session_utc
from app.domain.market_data.candle import Candle
from app.domain.market_data.timeframe import Timeframe
from app.domain.trading.gold_only import GOLD_SYMBOL
from app.domain.trading.xauusd_specs import VOLUME_MIN

_TRADE_ACTIONS = frozenset({DecisionAction.BUY, DecisionAction.SELL})
_BROKER_MIN_LOT = VOLUME_MIN
_PRODUCTION_QUALITY = int(DEFAULT_ITE_CONFIG.min_trade_quality_score)
_PRODUCTION_CONFLUENCE = int(DEFAULT_ITE_CONFIG.min_confluence_score)


@dataclass(frozen=True, slots=True)
class StageResult:
    stage: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return {
            "stage": self.stage,
            "status": self.status,
            "detail": self.detail,
        }


def _account(
    *,
    equity: Decimal,
    atr: Decimal | None,
    mid: Decimal,
) -> AccountRiskState:
    return AccountRiskState(
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


def _setup_live_ops_plane() -> OperationsControlPlane:
    """Isolated offline ops plane — LIVE + auto-trading, no durable persist.

    Sets fields directly so validation never mutates the operator ops-state
    file / Postgres via ``transition_mode`` / ``update_auto_trade_controls``.
    """
    plane = OperationsControlPlane()
    plane.mode = OpsExecutionMode.LIVE
    plane.kill_switch_armed = False
    plane.auto_trading_enabled = True
    plane.auto_trading_run_state = "running"
    plane.daily_loss_exceeded = False
    return plane


def _is_production_quality_setup(
    snapshot: MarketAnalysisSnapshot,
    decision: TradeDecision,
) -> tuple[bool, str]:
    """Strict production gates — no threshold weakening."""
    if decision.action not in _TRADE_ACTIONS:
        return False, f"action={decision.action.value} (not BUY/SELL)"
    if not snapshot.session.allowed:
        return False, f"session not allowed ({snapshot.session.session})"
    if not snapshot.trend.aligned:
        return False, "MTF not aligned"
    if decision.quality < _PRODUCTION_QUALITY:
        return (
            False,
            f"quality {decision.quality} < {_PRODUCTION_QUALITY}",
        )
    if decision.confluence.confidence < _PRODUCTION_CONFLUENCE:
        return (
            False,
            f"confluence {decision.confluence.confidence} < {_PRODUCTION_CONFLUENCE}",
        )
    lots = decision.approved_lots
    if lots is None or lots < _BROKER_MIN_LOT:
        return (
            False,
            f"approved_lots={lots} below broker min {_BROKER_MIN_LOT}",
        )
    if decision.risk_reasons:
        return False, f"risk reasons: {'; '.join(decision.risk_reasons)}"
    if not decision.eligibility.eligible:
        return (
            False,
            f"eligibility: {'; '.join(decision.eligibility.rejection_reasons)}",
        )
    return True, "all production gates satisfied"


def _replay_full_pipeline(
    *,
    snapshot: MarketAnalysisSnapshot,
    decision: TradeDecision,
    account: AccountRiskState,
    plane: OperationsControlPlane,
) -> dict[str, Any]:
    """Safety → Execution Bridge → simulated OMS → gateway/broker fill."""
    started = perf_counter()
    stages: list[StageResult] = []

    # Market data / signal / gates already proven by caller — record PASS.
    stages.append(
        StageResult(
            "Market Data",
            "PASS",
            f"bars as_of={snapshot.as_of.isoformat()} spread={snapshot.spread}",
        )
    )
    stages.append(
        StageResult(
            "Signal Generation",
            "PASS",
            f"action={decision.action.value} id={decision.id}",
        )
    )
    stages.append(
        StageResult(
            "MTF Alignment",
            "PASS",
            f"aligned={snapshot.trend.aligned} score={snapshot.trend.alignment_score}",
        )
    )
    stages.append(
        StageResult(
            "Quality",
            "PASS",
            f"{decision.quality} >= {_PRODUCTION_QUALITY}",
        )
    )
    stages.append(
        StageResult(
            "Confluence",
            "PASS",
            f"{decision.confluence.confidence} >= {_PRODUCTION_CONFLUENCE}",
        )
    )
    stages.append(
        StageResult(
            "Risk",
            "PASS",
            f"approved_lots={decision.approved_lots} (>= {_BROKER_MIN_LOT})",
        )
    )

    session_val = str(
        getattr(snapshot.session.session, "value", None) or snapshot.session.session
    )
    facts = AutoTradeLiveFacts(
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        risk_engine_pass=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol=GOLD_SYMBOL,
        symbol_tradable=True,
        margin_available=True,
        no_broker_restrictions=True,
        open_positions=account.open_positions,
        session=session_val,
        spread=snapshot.spread,
        news_blocked=bool(snapshot.news.blocked),
        news_reason=str(snapshot.news.reason or ""),
        daily_loss_exceeded=False,
        emergency_stop=False,
        ops_mode="LIVE",
        execution_enabled=True,
    )
    safety = evaluate_auto_trade_safety(plane.auto_trade_policy(), facts)
    if not safety.allowed:
        stages.append(
            StageResult(
                "Safety",
                "FAIL",
                "; ".join(safety.failed_reasons) or "safety blocked",
            )
        )
        return {
            "pipeline_complete": False,
            "execution_decision": "BLOCKED",
            "stages": [s.to_dict() for s in stages],
            "safety": safety.to_dict(),
            "oms_calls": 0,
            "latency_ms": round((perf_counter() - started) * 1000.0, 3),
        }
    stages.append(
        StageResult("Safety", "PASS", f"status={safety.status}")
    )
    stages.append(
        StageResult(
            "Execution Decision",
            "EXECUTE_TRADE",
            f"{decision.action.value} lots={decision.approved_lots}",
        )
    )

    oms = RecordingOmsPort(
        result=OmsSubmitResult(
            outcome="success",
            message="offline simulated fill",
            retcode=10009,
            order_ticket=700_001,
            deal_ticket=800_001,
            oms_status="success",
            gateway_status="order_sent",
            latency_ms=8.0,
            retryable=False,
            raw={
                "simulated": True,
                "offline": True,
                "gateway": "Order Sent (simulated/offline)",
                "broker": "Order Filled (simulated/offline)",
            },
        )
    )
    integ = InstitutionalExecutionIntegration.create(
        oms,
        config=ExecutionBridgeConfig(
            mode=ExecutionMode.LIVE,
            decision_ttl_seconds=120,
        ),
    )
    integ.bridge.bind_ops(plane)

    ctx = ExecutionBridgeContext(
        expected_input_hash=decision.input_hash,
        now=decision.as_of,
        snapshot=snapshot,
        account=account,
        risk_allowed=True,
        execution_enabled=True,
        connected=True,
        login=99_001,
        user_id=uuid4(),
        request_id=f"offline_exec_val_{decision.id}",
        gateway_connected=True,
        broker_connected=True,
        market_data_live=True,
        account_trading_enabled=True,
        mt5_autotrading_enabled=True,
        symbol_tradable=True,
        no_broker_restrictions=True,
    )
    bridge_result = integ.execute(decision, ctx)

    if not bridge_result.forwarded_to_oms or bridge_result.aborted:
        stages.append(
            StageResult(
                "OMS",
                "FAIL",
                f"abort={bridge_result.abort_reason} comment={bridge_result.journal_entry.comment}",
            )
        )
        return {
            "pipeline_complete": False,
            "execution_decision": "EXECUTE_TRADE",
            "stages": [s.to_dict() for s in stages],
            "safety": safety.to_dict(),
            "bridge": bridge_result.journal_entry.to_dict(),
            "oms_calls": len(oms.calls),
            "latency_ms": round((perf_counter() - started) * 1000.0, 3),
        }

    stages.append(
        StageResult(
            "OMS",
            "PASS",
            f"outcome={bridge_result.journal_entry.oms_status} "
            f"ticket={bridge_result.journal_entry.mt5_ticket}",
        )
    )
    stages.append(
        StageResult(
            "MT5 Gateway",
            "Order Sent (simulated/offline)",
            f"gateway_status={bridge_result.journal_entry.gateway_status}",
        )
    )
    stages.append(
        StageResult(
            "Broker",
            "Order Filled (simulated/offline)",
            f"deal={bridge_result.journal_entry.mt5_deal} "
            f"retcode={bridge_result.journal_entry.retcode}",
        )
    )

    return {
        "pipeline_complete": True,
        "execution_decision": "EXECUTE_TRADE",
        "stages": [s.to_dict() for s in stages],
        "safety": safety.to_dict(),
        "bridge": bridge_result.journal_entry.to_dict(),
        "oms_intent": oms.calls[0]["intent"] if oms.calls else None,
        "oms_calls": len(oms.calls),
        "latency_ms": round((perf_counter() - started) * 1000.0, 3),
    }


async def run_institutional_execution_validation(
    *,
    days: int = 90,
    max_evaluations: int = 400,
    max_valid_setups: int = 3,
    equity: Decimal = Decimal("10000"),
    bars_by_tf: dict[Timeframe | str, list[Candle]] | None = None,
    bar_source: str = "synthetic",
) -> dict[str, Any]:
    """Search for production-quality setups and replay the full execution stack."""
    generated_at = datetime.now(UTC)
    normalized = (
        _normalize_bars_by_tf(bars_by_tf)
        if bars_by_tf
        else build_synthetic_bars(days)
    )
    source_label = bar_source if bars_by_tf else "synthetic_deterministic"

    m15 = normalized.get(Timeframe.M15, [])
    close_times_by_tf: dict[Timeframe, list[datetime]] = {
        tf: [c.close_time for c in candles] for tf, candles in normalized.items()
    }

    eligible: list[tuple[int, datetime]] = []
    for i, candle in enumerate(m15):
        as_of = candle.close_time
        if classify_session_utc(as_of) in ALLOWED_SESSIONS:
            eligible.append((i, as_of))

    walk_points = _select_walk_points(eligible, max_evaluations=max_evaluations)

    analysis_service = InstitutionalTradingAnalysisService()
    pipeline = InstitutionalDecisionPipeline()  # DEFAULT_ITE_CONFIG — unchanged
    plane = _setup_live_ops_plane()

    near_misses: list[dict[str, Any]] = []
    reject_tallies: dict[str, int] = {}
    valid_setups: list[dict[str, Any]] = []
    evaluations = 0

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

        atr = _compute_atr(sliced[Timeframe.M15])
        mid = sliced[Timeframe.M15][-1].close.value
        account = _account(equity=equity, atr=atr, mid=mid)

        snapshot = await analysis_service.analyze_bars(
            sliced,
            as_of=as_of,
            spread=Decimal("0.30"),
        )
        decision = pipeline.run(
            snapshot,
            account,
            request_id=f"exec_val_{eval_idx}_{snapshot.input_hash[:12]}",
        )
        evaluations += 1

        ok, reason = _is_production_quality_setup(snapshot, decision)
        if not ok:
            reject_tallies[reason.split("(")[0].strip()[:80]] = (
                reject_tallies.get(reason.split("(")[0].strip()[:80], 0) + 1
            )
            if (
                decision.quality >= 70
                or decision.confluence.confidence >= 70
                or decision.action in _TRADE_ACTIONS
            ):
                near_misses.append(
                    {
                        "as_of": as_of.isoformat(),
                        "action": decision.action.value,
                        "quality": decision.quality,
                        "confluence": decision.confluence.confidence,
                        "mtf_aligned": snapshot.trend.aligned,
                        "session_allowed": snapshot.session.allowed,
                        "approved_lots": (
                            str(decision.approved_lots)
                            if decision.approved_lots is not None
                            else None
                        ),
                        "reason": reason,
                    }
                )
            continue

        replay = _replay_full_pipeline(
            snapshot=snapshot,
            decision=decision,
            account=account,
            plane=plane,
        )
        valid_setups.append(
            {
                "as_of": as_of.isoformat(),
                "session": str(
                    getattr(snapshot.session.session, "value", snapshot.session.session)
                ),
                "action": decision.action.value,
                "quality": decision.quality,
                "confluence": decision.confluence.confidence,
                "mtf_aligned": snapshot.trend.aligned,
                "mtf_score": snapshot.trend.alignment_score,
                "approved_lots": str(decision.approved_lots),
                "atr": str(atr) if atr is not None else None,
                "mid_price": str(mid),
                "equity": str(equity),
                "decision_id": str(decision.id),
                "input_hash": snapshot.input_hash,
                "execution_trace": replay,
            }
        )
        if len(valid_setups) >= max_valid_setups:
            break

    valid_exists = any(
        s.get("execution_trace", {}).get("pipeline_complete") for s in valid_setups
    )
    none_reason = ""
    if not valid_setups:
        top = sorted(reject_tallies.items(), key=lambda kv: -kv[1])[:8]
        top_txt = "; ".join(f"{k} ({v})" for k, v in top) if top else "no evaluations"
        none_reason = (
            f"No historical setup in the selected window satisfied all production "
            f"gates (session allowed, MTF aligned, quality>={_PRODUCTION_QUALITY}, "
            f"confluence>={_PRODUCTION_CONFLUENCE}, approved_lots>={_BROKER_MIN_LOT}, "
            f"risk/eligibility pass). Top reject reasons: {top_txt}"
        )
    elif not valid_exists:
        none_reason = (
            "Production-quality signals were found but the full execution replay "
            "did not complete (safety or bridge abort). See valid_setups traces."
        )

    return {
        "schema_version": "1.0.0",
        "report_type": "institutional_execution_validation",
        "generated_at": generated_at.isoformat(),
        "symbol": GOLD_SYMBOL,
        "offline": True,
        "simulation_only": True,
        "live_order_send_called": False,
        "strategy_modified": False,
        "thresholds_modified": False,
        "risk_policy_modified": False,
        "safety_policy_modified": False,
        "production_gates": {
            "min_quality": _PRODUCTION_QUALITY,
            "min_confluence": _PRODUCTION_CONFLUENCE,
            "broker_min_lot": str(_BROKER_MIN_LOT),
            "ite_config_version": DEFAULT_ITE_CONFIG.config_version,
            "allowed_sessions": sorted(s.value for s in ALLOWED_SESSIONS),
        },
        "params": {
            "days": days,
            "max_evaluations": max_evaluations,
            "max_valid_setups": max_valid_setups,
            "equity": str(equity),
            "bar_source": source_label,
        },
        "eligible_bars_considered": len(eligible),
        "evaluations": evaluations,
        "valid_production_setup_exists": valid_exists,
        "valid_setup_count": len(valid_setups),
        "none_exists_reason": none_reason,
        "valid_setups": valid_setups,
        "near_misses_sample": near_misses[:25],
        "reject_tallies": dict(
            sorted(reject_tallies.items(), key=lambda kv: -kv[1])[:30]
        ),
    }


def report_to_markdown(report: dict[str, Any]) -> str:
    """Human-readable validation report."""
    lines: list[str] = []
    lines.append("# Institutional Execution Validation Report")
    lines.append("")
    lines.append(f"- Generated at: `{report.get('generated_at', '—')}`")
    lines.append(f"- Symbol: `{report.get('symbol', '—')}`")
    params = report.get("params") or {}
    lines.append(
        f"- Window: **{params.get('days')}** days · "
        f"evaluations **{report.get('evaluations')}** · "
        f"equity **{params.get('equity')}** · "
        f"bars **{params.get('bar_source')}**"
    )
    lines.append(
        f"- Live `order_send` called: **{report.get('live_order_send_called')}**"
    )
    lines.append(
        f"- Strategy / thresholds / risk / safety modified: "
        f"**{report.get('strategy_modified')}** / "
        f"**{report.get('thresholds_modified')}** / "
        f"**{report.get('risk_policy_modified')}** / "
        f"**{report.get('safety_policy_modified')}**"
    )
    gates = report.get("production_gates") or {}
    lines.append(
        f"- Production gates: Q≥{gates.get('min_quality')} · "
        f"C≥{gates.get('min_confluence')} · "
        f"min lot {gates.get('broker_min_lot')} · "
        f"`{gates.get('ite_config_version')}`"
    )
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    exists = bool(report.get("valid_production_setup_exists"))
    if exists:
        lines.append(
            "**YES** — at least one production-quality historical setup was found "
            "and the complete offline execution pipeline reached Broker fill."
        )
    else:
        lines.append(
            "**NO** — no production-quality setup completed the full pipeline "
            "in this window."
        )
        reason = report.get("none_exists_reason") or ""
        if reason:
            lines.append("")
            lines.append(f"Exact reason: {reason}")
    lines.append("")
    lines.append("## Execution traces")
    lines.append("")
    setups = report.get("valid_setups") or []
    if not setups:
        lines.append("_No valid setups to trace._")
    for i, setup in enumerate(setups, start=1):
        lines.append(f"### Setup {i}")
        lines.append("")
        lines.append(f"- as_of: `{setup.get('as_of')}`")
        lines.append(f"- session: `{setup.get('session')}`")
        lines.append(
            f"- action: **{setup.get('action')}** · "
            f"Q={setup.get('quality')} · C={setup.get('confluence')} · "
            f"lots={setup.get('approved_lots')}"
        )
        lines.append(
            f"- MTF aligned: `{setup.get('mtf_aligned')}` "
            f"(score={setup.get('mtf_score')})"
        )
        trace = setup.get("execution_trace") or {}
        lines.append(
            f"- pipeline_complete: **{trace.get('pipeline_complete')}** · "
            f"decision: `{trace.get('execution_decision')}`"
        )
        lines.append("")
        lines.append("| Stage | Status | Detail |")
        lines.append("|---|---|---|")
        for stage in trace.get("stages") or []:
            lines.append(
                f"| {stage.get('stage')} | {stage.get('status')} | "
                f"{stage.get('detail') or '—'} |"
            )
        lines.append("")
    tallies = report.get("reject_tallies") or {}
    if tallies:
        lines.append("## Reject tallies (search window)")
        lines.append("")
        for reason, count in list(tallies.items())[:15]:
            lines.append(f"- `{reason}`: {count}")
        lines.append("")
    return "\n".join(lines)
