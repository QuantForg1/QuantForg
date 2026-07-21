"""Six institutional AI agents — advisory, explainable, event-emitting."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from app.domain.multi_agent_ai.events import AgentEventBus
from app.domain.multi_agent_ai.types import AgentOutput, CollaborationInput, Vote


def _conf(value: Decimal | float | int | None, default: str = "50") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _emit(
    bus: AgentEventBus | None,
    *,
    agent: str,
    event_type: str,
    payload: dict[str, Any],
    session_id: str,
) -> None:
    if bus is None:
        return
    bus.publish(
        event_type=event_type,
        agent=agent,
        payload=payload,
        session_id=session_id,
    )


def run_market_agent(
    inp: CollaborationInput,
    *,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> AgentOutput:
    reasons: list[str] = []
    vote: Vote = "HOLD"
    conf = Decimal("50")
    snap = inp.market_snapshot or {}
    spread = inp.spread
    if spread is None and snap.get("spread") is not None:
        spread = _conf(snap.get("spread"), "0")  # type: ignore[assignment]
    regime = inp.regime or (str(snap["regime"]) if snap.get("regime") else None)

    if spread is None and regime is None and not snap:
        status = "unavailable"
        reasons.append("No market facts supplied — abstain")
        vote = "ABSTAIN"
        conf = Decimal("0")
    else:
        status = "available"
        if spread is not None:
            if spread > Decimal("2"):
                vote = "REJECT"
                conf = Decimal("75")
                reasons.append(f"Spread {spread} too wide for XAUUSD")
            elif spread > Decimal("1"):
                vote = "HOLD"
                conf = Decimal("60")
                reasons.append(f"Spread {spread} elevated — caution")
            else:
                vote = "APPROVE"
                conf = Decimal("70")
                reasons.append(f"Spread {spread} acceptable")
        if regime in {"news", "volatile"}:
            vote = "HOLD" if vote == "APPROVE" else vote
            conf = min(conf, Decimal("55"))
            reasons.append(f"Regime {regime} — market caution")
        elif regime:
            reasons.append(f"Regime {regime} observed")
        if not reasons:
            reasons.append("Market snapshot observed without clear veto")

    out = AgentOutput(
        agent="market",
        vote=vote,
        confidence=conf,
        reasons=tuple(reasons),
        observations={
            "spread": str(spread) if spread is not None else None,
            "regime": regime,
        },
        status=status,
    )
    _emit(
        bus,
        agent="market",
        event_type="agent.voted",
        payload=out.to_dict(),
        session_id=session_id,
    )
    return out


def run_strategy_agent(
    inp: CollaborationInput,
    *,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> AgentOutput:
    reasons: list[str] = []
    signal = (inp.strategy_signal or "").lower()
    snap = inp.strategy_snapshot or {}
    if not signal and snap.get("signal"):
        signal = str(snap["signal"]).lower()
    conf_in = inp.confidence
    if conf_in is None and snap.get("confidence") is not None:
        conf_in = _conf(snap.get("confidence"))

    if not signal and conf_in is None and not snap:
        out = AgentOutput(
            agent="strategy",
            vote="ABSTAIN",
            confidence=Decimal("0"),
            reasons=("No strategy facts — abstain",),
            observations={},
            status="unavailable",
        )
    else:
        vote: Vote = "HOLD"
        conf = conf_in if conf_in is not None else Decimal("50")
        if signal in {"buy", "sell", "long", "short"}:
            if conf >= Decimal("70"):
                vote = "APPROVE"
                reasons.append(f"Strategy signal {signal} with confidence {conf}")
            else:
                vote = "HOLD"
                reasons.append(
                    f"Signal {signal} but confidence {conf} below strong threshold"
                )
        elif signal in {"flat", "none", "neutral"}:
            vote = "HOLD"
            reasons.append("Strategy flat — no entry")
        else:
            vote = "HOLD"
            reasons.append("Strategy signal unclear — HOLD")
        if inp.strategy_id:
            reasons.append(f"Strategy id {inp.strategy_id}")
        out = AgentOutput(
            agent="strategy",
            vote=vote,
            confidence=conf,
            reasons=tuple(reasons),
            observations={
                "strategy_id": inp.strategy_id,
                "signal": signal or None,
                "confidence": str(conf),
            },
            status="available",
        )
    _emit(
        bus,
        agent="strategy",
        event_type="agent.voted",
        payload=out.to_dict(),
        session_id=session_id,
    )
    return out


def run_risk_agent(
    inp: CollaborationInput,
    *,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> AgentOutput:
    """Advisory wrapper — existing Risk Engine remains authoritative."""
    reasons: list[str] = []
    passed = inp.risk_engine_passed
    if passed is None:
        out = AgentOutput(
            agent="risk",
            vote="HOLD",
            confidence=Decimal("100"),
            reasons=(
                "Risk Engine not assessed — fail closed",
                "Risk Agent cannot bypass existing Risk Engine",
            ),
            observations={"risk_engine_passed": None},
            status="unavailable",
            authoritative=True,
        )
    elif passed is False:
        out = AgentOutput(
            agent="risk",
            vote="REJECT",
            confidence=Decimal("100"),
            reasons=(
                "Risk Engine rejected — authoritative",
                "Coordinator must not approve",
            ),
            observations={"risk_engine_passed": False},
            status="available",
            authoritative=True,
        )
    else:
        reasons.append("Risk Engine passed (external, unchanged)")
        reasons.append("Risk Agent advisory only — engine remains authoritative")
        out = AgentOutput(
            agent="risk",
            vote="APPROVE",
            confidence=Decimal("90"),
            reasons=tuple(reasons),
            observations={"risk_engine_passed": True},
            status="available",
            authoritative=True,
        )
    _emit(
        bus,
        agent="risk",
        event_type="agent.voted",
        payload=out.to_dict(),
        session_id=session_id,
    )
    return out


def run_safety_agent(
    inp: CollaborationInput,
    *,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> AgentOutput:
    """Advisory wrapper — existing Safety Engine remains authoritative."""
    reasons: list[str] = []
    passed = inp.safety_engine_passed
    if inp.kill_switch is True:
        out = AgentOutput(
            agent="safety",
            vote="REJECT",
            confidence=Decimal("100"),
            reasons=("Kill switch observed — Safety Agent rejects",),
            observations={"kill_switch": True, "safety_engine_passed": passed},
            status="available",
            authoritative=True,
        )
    elif inp.news_blackout is True:
        out = AgentOutput(
            agent="safety",
            vote="HOLD",
            confidence=Decimal("95"),
            reasons=("News blackout — Safety Agent holds",),
            observations={"news_blackout": True, "safety_engine_passed": passed},
            status="available",
            authoritative=True,
        )
    elif passed is None:
        out = AgentOutput(
            agent="safety",
            vote="HOLD",
            confidence=Decimal("100"),
            reasons=(
                "Safety Engine not assessed — fail closed",
                "Safety Agent cannot bypass existing Safety Engine",
            ),
            observations={"safety_engine_passed": None},
            status="unavailable",
            authoritative=True,
        )
    elif passed is False:
        out = AgentOutput(
            agent="safety",
            vote="REJECT",
            confidence=Decimal("100"),
            reasons=(
                "Safety Engine rejected — authoritative",
                "Coordinator must not approve",
            ),
            observations={"safety_engine_passed": False},
            status="available",
            authoritative=True,
        )
    else:
        reasons.append("Safety Engine passed (external, unchanged)")
        reasons.append("Safety Agent advisory only — engine remains authoritative")
        out = AgentOutput(
            agent="safety",
            vote="APPROVE",
            confidence=Decimal("90"),
            reasons=tuple(reasons),
            observations={"safety_engine_passed": True},
            status="available",
            authoritative=True,
        )
    _emit(
        bus,
        agent="safety",
        event_type="agent.voted",
        payload=out.to_dict(),
        session_id=session_id,
    )
    return out


def run_portfolio_agent(
    inp: CollaborationInput,
    *,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> AgentOutput:
    reasons: list[str] = []
    snap = inp.portfolio_snapshot or {}
    exposure = inp.portfolio_exposure
    if exposure is None and snap.get("exposure") is not None:
        exposure = _conf(snap.get("exposure"))
    opens = inp.open_positions
    if opens is None and snap.get("open_positions") is not None:
        try:
            opens = int(snap["open_positions"])
        except Exception:
            opens = None

    if exposure is None and opens is None and not snap:
        out = AgentOutput(
            agent="portfolio",
            vote="ABSTAIN",
            confidence=Decimal("0"),
            reasons=("No portfolio facts — abstain",),
            observations={},
            status="unavailable",
        )
    else:
        vote: Vote = "APPROVE"
        conf = Decimal("65")
        if exposure is not None and exposure > Decimal("50"):
            vote = "HOLD"
            conf = Decimal("80")
            reasons.append(f"Exposure {exposure}% elevated — hold sizing")
        elif exposure is not None:
            reasons.append(f"Exposure {exposure}% within comfort")
        if opens is not None and opens >= 3:
            vote = "HOLD"
            conf = max(conf, Decimal("75"))
            reasons.append(f"{opens} open positions — concentration caution")
        elif opens is not None:
            reasons.append(f"{opens} open positions observed")
        if not reasons:
            reasons.append("Portfolio posture acceptable")
        out = AgentOutput(
            agent="portfolio",
            vote=vote,
            confidence=conf,
            reasons=tuple(reasons),
            observations={
                "exposure": str(exposure) if exposure is not None else None,
                "open_positions": opens,
            },
            status="available",
        )
    _emit(
        bus,
        agent="portfolio",
        event_type="agent.voted",
        payload=out.to_dict(),
        session_id=session_id,
    )
    return out


def run_execution_agent(
    inp: CollaborationInput,
    *,
    session_id: str,
    bus: AgentEventBus | None = None,
) -> AgentOutput:
    """Advisory execution readiness — never calls order_send / gateway."""
    reasons: list[str] = []
    snap = inp.execution_snapshot or {}
    mode = (inp.execution_mode or str(snap.get("mode") or "")).upper()
    spread = inp.spread
    if spread is None and snap.get("spread") is not None:
        spread = _conf(snap.get("spread"))  # type: ignore[assignment]

    if not mode and spread is None and not snap:
        out = AgentOutput(
            agent="execution",
            vote="ABSTAIN",
            confidence=Decimal("0"),
            reasons=("No execution facts — abstain",),
            observations={},
            status="unavailable",
        )
    else:
        vote: Vote = "APPROVE"
        conf = Decimal("60")
        if mode in {"HALTED", "OFFLINE", "DISCONNECTED"}:
            vote = "REJECT"
            conf = Decimal("100")
            reasons.append(f"Execution mode {mode} — reject")
        elif mode in {"SHADOW", "PAPER"}:
            vote = "HOLD"
            conf = Decimal("70")
            reasons.append(f"Mode {mode} — advisory HOLD (no live send)")
        elif mode:
            reasons.append(f"Mode {mode} observed")
        if spread is not None and spread > Decimal("1.5"):
            vote = "HOLD" if vote == "APPROVE" else vote
            conf = max(conf, Decimal("70"))
            reasons.append(f"Execution spread {spread} elevated")
        reasons.append("Execution Agent never calls order_send")
        reasons.append("Existing execution pipeline unchanged")
        lead = reasons[0] if reasons else ""
        if not any(
            token in lead.lower() for token in ("mode", "spread", "reject")
        ):
            reasons.insert(0, "Execution readiness advisory complete")
        out = AgentOutput(
            agent="execution",
            vote=vote,
            confidence=conf,
            reasons=tuple(reasons),
            observations={
                "execution_mode": mode or None,
                "spread": str(spread) if spread is not None else None,
                "never_order_send": True,
            },
            status="available",
        )
    _emit(
        bus,
        agent="execution",
        event_type="agent.voted",
        payload=out.to_dict(),
        session_id=session_id,
    )
    return out


AGENT_RUNNERS = (
    ("market", run_market_agent),
    ("strategy", run_strategy_agent),
    ("risk", run_risk_agent),
    ("safety", run_safety_agent),
    ("portfolio", run_portfolio_agent),
    ("execution", run_execution_agent),
)
