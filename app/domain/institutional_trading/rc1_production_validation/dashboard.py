"""Live Pilot Validation Dashboard — observe-only metrics aggregation."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from app.domain.institutional_trading.rc1_production_validation.config import (
    CONFIDENCE_FLOOR,
    QUALITY_FLOOR,
    resolve_validation_runtime,
)
from app.domain.institutional_trading.rc1_production_validation.paper_engine import (
    get_paper_engine,
)
from app.domain.institutional_trading.rc1_production_validation.shadow_engine import (
    get_shadow_journal,
)
from app.domain.institutional_trading.rc1_production_validation.trade_recorder import (
    get_trade_recorder,
)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _avg(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 4)


def build_validation_dashboard(
    *,
    infrastructure: dict[str, Any] | None = None,
    ai_status: str | None = None,
    current_session: str | None = None,
    current_regime: str | None = None,
    acceptance: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Compose Live Pilot Validation Dashboard metrics."""
    cfg = resolve_validation_runtime()
    recorder = get_trade_recorder()
    paper = get_paper_engine()
    shadow = get_shadow_journal()
    trades = recorder.all()
    accepted = [t for t in trades if t.accepted]
    rejected = [t for t in trades if not t.accepted]
    paper_perf = paper.performance()
    shadow_stats = shadow.stats()
    infra = infrastructure or {}

    oms_lats = [t.oms_latency_ms for t in trades if t.oms_latency_ms is not None]
    ai_lats = [t.ai_latency_ms for t in trades if t.ai_latency_ms is not None]
    gw_lats = [
        t.gateway_latency_ms for t in trades if t.gateway_latency_ms is not None
    ]
    rrs: list[float] = []
    for t in accepted:
        if t.risk_reward is None:
            continue
        try:
            rrs.append(float(t.risk_reward))
        except (TypeError, ValueError):
            continue

    qualities = [t.quality for t in accepted if t.quality is not None]
    confidences = [t.confidence for t in accepted if t.confidence is not None]

    fill_rate = None
    if cfg.simulates_fills:
        fills = int(paper_perf.get("fills_simulated") or 0)
        denom = len(accepted) or fills
        fill_rate = round((fills / denom) * 100.0, 2) if denom else None

    # PnL windows — paper realized only (never invent live PnL)
    daily_pnl = paper_perf.get("realized_pnl") if cfg.simulates_fills else None
    weekly_pnl = daily_pnl
    monthly_pnl = daily_pnl

    return {
        "timestamp": _now_iso(),
        "mode": cfg.to_dict(),
        "Gateway Health": infra.get("gateway_health")
        or infra.get("gateway_status")
        or "UNKNOWN",
        "MT5 Status": infra.get("mt5_status") or "UNKNOWN",
        "OMS Status": infra.get("oms_status") or "UNKNOWN",
        "AI Status": ai_status or infra.get("ai_status") or "UNKNOWN",
        "Current Session": current_session
        or infra.get("current_session")
        or "—",
        "Current Regime": current_regime or infra.get("current_regime") or "—",
        "Quality": {
            "floor": QUALITY_FLOOR,
            "accepted_avg": _avg([float(q) for q in qualities]),
            "last": accepted[-1].quality if accepted else None,
        },
        "Confidence": {
            "floor": CONFIDENCE_FLOOR,
            "accepted_avg": _avg([float(c) for c in confidences]),
            "last": accepted[-1].confidence if accepted else None,
        },
        "Eligible Trades": len(accepted),
        "Rejected Trades": len(rejected),
        "Broker Submissions": (
            0
            if cfg.blocks_broker_submit
            else int(infra.get("broker_submissions") or 0)
        ),
        "Fill Rate": fill_rate,
        "Win Rate": paper_perf.get("win_rate_pct"),
        "Loss Rate": paper_perf.get("loss_rate_pct"),
        "Profit Factor": paper_perf.get("profit_factor"),
        "Expectancy": paper_perf.get("expectancy"),
        "Average RR": _avg(rrs),
        "Drawdown": paper_perf.get("drawdown_pct"),
        "Current Equity": paper_perf.get("equity"),
        "Open Positions": paper_perf.get("open_positions"),
        "Closed Positions": paper_perf.get("closed_positions"),
        "Daily PnL": daily_pnl,
        "Weekly PnL": weekly_pnl,
        "Monthly PnL": monthly_pnl,
        "Latency": {
            "OMS_ms_avg": _avg([float(x) for x in oms_lats]),
            "AI_ms_avg": _avg([float(x) for x in ai_lats]),
            "gateway_ms_avg": _avg([float(x) for x in gw_lats]),
        },
        "shadow": shadow_stats,
        "paper": paper_perf,
        "replay": replay or {},
        "acceptance": acceptance or {},
        "observe_only_flags": {
            "never_modifies_strategy": True,
            "never_lowers_quality_gates": True,
            "never_changes_weights": True,
            "never_changes_risk_logic": True,
        },
        "metrics_snake": {
            "gateway_health": infra.get("gateway_health")
            or infra.get("gateway_status")
            or "UNKNOWN",
            "mt5_status": infra.get("mt5_status") or "UNKNOWN",
            "oms_status": infra.get("oms_status") or "UNKNOWN",
            "ai_status": ai_status or infra.get("ai_status") or "UNKNOWN",
            "current_session": current_session
            or infra.get("current_session")
            or "—",
            "current_regime": current_regime or infra.get("current_regime") or "—",
            "eligible_trades": len(accepted),
            "rejected_trades": len(rejected),
            "broker_submissions": (
                0
                if cfg.blocks_broker_submit
                else int(infra.get("broker_submissions") or 0)
            ),
            "fill_rate": fill_rate,
            "win_rate": paper_perf.get("win_rate_pct"),
            "loss_rate": paper_perf.get("loss_rate_pct"),
            "profit_factor": paper_perf.get("profit_factor"),
            "expectancy": paper_perf.get("expectancy"),
            "average_rr": _avg(rrs),
            "drawdown": paper_perf.get("drawdown_pct"),
            "current_equity": paper_perf.get("equity"),
            "open_positions": paper_perf.get("open_positions"),
            "closed_positions": paper_perf.get("closed_positions"),
            "daily_pnl": daily_pnl,
            "weekly_pnl": weekly_pnl,
            "monthly_pnl": monthly_pnl,
            "latency": {
                "oms_ms_avg": _avg([float(x) for x in oms_lats]),
                "ai_ms_avg": _avg([float(x) for x in ai_lats]),
                "gateway_ms_avg": _avg([float(x) for x in gw_lats]),
            },
        },
    }
