"""RC1 acceptance gates — infrastructure, AI, trading, risk readiness."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.institutional_trading.rc1_production_validation.config import (
    CONFIDENCE_FLOOR,
    QUALITY_FLOOR,
)


class GateStatus(StrEnum):
    PASS = "PASS"  # noqa: S105
    FAIL = "FAIL"
    WARN = "WARN"
    UNKNOWN = "UNKNOWN"


class Rc1Recommendation(StrEnum):
    NOT_READY = "NOT READY"
    LIMITED_LIVE_PILOT = "READY FOR LIMITED LIVE PILOT"
    FULL_PRODUCTION = "READY FOR FULL PRODUCTION"


@dataclass(slots=True)
class GateResult:
    name: str
    status: GateStatus
    detail: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status.value,
            "detail": self.detail,
            "evidence": dict(self.evidence),
        }


def _gate(
    name: str,
    ok: bool | None,
    *,
    detail: str = "",
    **evidence: Any,
) -> GateResult:
    if ok is None:
        status = GateStatus.UNKNOWN
    elif ok:
        status = GateStatus.PASS
    else:
        status = GateStatus.FAIL
    return GateResult(name=name, status=status, detail=detail, evidence=dict(evidence))


def evaluate_acceptance_gates(
    *,
    infrastructure: dict[str, Any] | None = None,
    trade_stats: dict[str, Any] | None = None,
    paper: dict[str, Any] | None = None,
    shadow: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    risk: dict[str, Any] | None = None,
    trading: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Automatically determine RC1 readiness from observed evidence only."""
    infra = infrastructure or {}
    stats = trade_stats or {}
    paper_m = paper or {}
    shadow_m = shadow or {}
    replay_m = replay or {}
    risk_m = risk or {}
    trading_m = trading or {}

    gates: list[GateResult] = []

    # --- Infrastructure ---
    gw = str(infra.get("gateway_health") or infra.get("gateway_status") or "").upper()
    oms = str(infra.get("oms_status") or "").upper()
    mt5 = str(infra.get("mt5_status") or "").upper()
    crashes = int(infra.get("crashes") or 0)
    gates.append(
        _gate(
            "gateway_healthy",
            gw in {"PASS", "HEALTHY", "OK", "UP", "REACHED"} if gw else None,
            detail=f"gateway={gw or 'UNKNOWN'}",
            gateway=gw,
        )
    )
    oms_ok_set = {"PASS", "HEALTHY", "OK", "UP", "REACHED", "SHADOW"}
    gates.append(
        _gate(
            "oms_healthy",
            oms in oms_ok_set if oms else None,
            detail=f"oms={oms or 'UNKNOWN'}",
            oms=oms,
        )
    )
    gates.append(
        _gate(
            "mt5_connected",
            mt5 in {"PASS", "CONNECTED", "OK", "UP", "HEALTHY"} if mt5 else None,
            detail=f"mt5={mt5 or 'UNKNOWN'}",
            mt5=mt5,
        )
    )
    gates.append(
        _gate("no_crashes", crashes == 0, detail=f"crashes={crashes}", crashes=crashes)
    )

    # --- AI floors on accepted trades ---
    q_avg = stats.get("accepted_quality_avg")
    c_avg = stats.get("accepted_confidence_avg")
    dup_penalties = int(stats.get("duplicate_penalties") or 0)
    gates.append(
        _gate(
            "quality_floor_accepted",
            (float(q_avg) >= QUALITY_FLOOR) if q_avg is not None else None,
            detail=f"avg_quality={q_avg} floor={QUALITY_FLOOR}",
            avg_quality=q_avg,
            floor=QUALITY_FLOOR,
        )
    )
    gates.append(
        _gate(
            "confidence_floor_accepted",
            (float(c_avg) >= CONFIDENCE_FLOOR) if c_avg is not None else None,
            detail=f"avg_confidence={c_avg} floor={CONFIDENCE_FLOOR}",
            avg_confidence=c_avg,
            floor=CONFIDENCE_FLOOR,
        )
    )
    gates.append(
        _gate(
            "no_duplicate_penalties",
            dup_penalties == 0,
            detail=f"duplicate_penalties={dup_penalties}",
            duplicate_penalties=dup_penalties,
        )
    )

    # --- Trading integrity ---
    orders_valid = trading_m.get("orders_valid")
    lots_ok = trading_m.get("lot_sizing_correct")
    risk_limits = trading_m.get("risk_limits_respected")
    no_dup_pos = trading_m.get("no_duplicate_positions")
    no_orphan = trading_m.get("no_orphan_positions")
    for name, val in (
        ("orders_valid", orders_valid),
        ("lot_sizing_correct", lots_ok),
        ("risk_limits_respected", risk_limits),
        ("no_duplicate_positions", no_dup_pos),
        ("no_orphan_positions", no_orphan),
    ):
        gates.append(
            _gate(name, bool(val) if val is not None else None, detail=str(val))
        )

    # --- Risk ---
    for name, key in (
        ("daily_loss_enforced", "daily_loss_enforced"),
        ("portfolio_caps_enforced", "portfolio_caps_enforced"),
        ("correlation_enforced", "correlation_enforced"),
        ("emergency_stop_verified", "emergency_stop_verified"),
    ):
        val = risk_m.get(key)
        gates.append(
            _gate(name, bool(val) if val is not None else None, detail=str(val))
        )

    # Soft evidence from paper/shadow/replay (warn if empty)
    if paper_m.get("broker_orders_submitted", 0) not in (0, None):
        gates.append(
            _gate(
                "paper_no_broker_orders",
                False,
                detail="paper mode submitted broker orders",
                **{k: paper_m.get(k) for k in ("broker_orders_submitted",)},
            )
        )
    elif paper_m:
        gates.append(
            _gate(
                "paper_no_broker_orders",
                True,
                detail="paper engine reports zero broker submissions",
            )
        )

    if shadow_m:
        submitted = int(shadow_m.get("broker_submissions") or 0)
        gates.append(
            _gate(
                "shadow_no_broker_submit",
                submitted == 0,
                detail=f"shadow_broker_submissions={submitted}",
            )
        )

    if replay_m:
        missing_r = replay_m.get("coverage", {}).get("regimes_missing") or []
        missing_s = replay_m.get("coverage", {}).get("sessions_missing") or []
        gates.append(
            _gate(
                "replay_regime_coverage",
                len(missing_r) == 0,
                detail=f"missing_regimes={missing_r}",
                missing=missing_r,
            )
        )
        gates.append(
            _gate(
                "replay_session_coverage",
                len(missing_s) == 0,
                detail=f"missing_sessions={missing_s}",
                missing=missing_s,
            )
        )

    passed = sum(1 for g in gates if g.status is GateStatus.PASS)
    failed = sum(1 for g in gates if g.status is GateStatus.FAIL)
    unknown = sum(1 for g in gates if g.status is GateStatus.UNKNOWN)
    hard_fails = [
        g.name
        for g in gates
        if g.status is GateStatus.FAIL
        and g.name
        in {
            "no_crashes",
            "quality_floor_accepted",
            "confidence_floor_accepted",
            "no_duplicate_penalties",
            "orders_valid",
            "lot_sizing_correct",
            "risk_limits_respected",
            "daily_loss_enforced",
            "emergency_stop_verified",
            "paper_no_broker_orders",
            "shadow_no_broker_submit",
        }
    ]

    if failed == 0 and unknown == 0 and passed >= 12:
        recommendation = Rc1Recommendation.FULL_PRODUCTION
    elif (
        failed == 0
        and not hard_fails
        and (passed >= 6 or (failed <= 2 and passed >= 4))
    ):
        recommendation = Rc1Recommendation.LIMITED_LIVE_PILOT
    else:
        recommendation = Rc1Recommendation.NOT_READY

    # Unknown-heavy evidence → never claim full production
    if unknown >= 5 and recommendation is Rc1Recommendation.FULL_PRODUCTION:
        recommendation = Rc1Recommendation.LIMITED_LIVE_PILOT
    if hard_fails:
        recommendation = Rc1Recommendation.NOT_READY
    # Infrastructure UNKNOWN blocks any live recommendation
    infra_unknown = any(
        g.name in {"gateway_healthy", "oms_healthy", "mt5_connected"}
        and g.status is GateStatus.UNKNOWN
        for g in gates
    )
    if infra_unknown and recommendation is not Rc1Recommendation.NOT_READY:
        recommendation = Rc1Recommendation.NOT_READY

    return {
        "gates": [g.to_dict() for g in gates],
        "summary": {
            "passed": passed,
            "failed": failed,
            "unknown": unknown,
            "total": len(gates),
            "hard_fails": hard_fails,
            "infra_unknown": infra_unknown,
        },
        "quality_floor": QUALITY_FLOOR,
        "confidence_floor": CONFIDENCE_FLOOR,
        "recommendation": recommendation.value,
        "thresholds_unchanged": True,
        "strategy_unchanged": True,
    }
