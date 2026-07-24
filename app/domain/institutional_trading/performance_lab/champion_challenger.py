"""Champion vs Challenger — challenger never executes."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.performance_lab.config import (
    DEFAULT_CHALLENGER_TILT,
    DEFAULT_LAB_CONFIG,
    PerformanceLabConfig,
)
from core.logging import get_logger

logger = get_logger(__name__)


def _clamp(n: int) -> int:
    return max(0, min(100, int(n)))


@dataclass(frozen=True, slots=True)
class ProfileDecision:
    profile: str  # champion | challenger
    direction: str
    confidence: int
    opportunity_score: int
    expected_rr: float
    risk_score: int
    may_execute: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChampionChallengerDuel:
    id: str
    at: str
    symbol: str
    session: str
    regime: str
    trace_id: str | None
    champion: dict[str, Any]
    challenger: dict[str, Any]
    agree_direction: bool
    confidence_delta: int
    score_delta: int
    challenger_executed: bool  # always False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _factors_from_decision(decision: Any, snapshot: Any | None = None) -> dict[str, int]:
    factors: dict[str, int] = {}
    confluence = getattr(decision, "confluence", None)
    raw = getattr(confluence, "factors", None) if confluence is not None else None
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                factors[str(k).lower()] = _clamp(int(v))
            except Exception:
                continue
    conf = int(getattr(decision, "confidence", 50) or 50)
    quality = int(getattr(decision, "quality", conf) or conf)
    factors.setdefault("trend", quality)
    factors.setdefault("momentum", conf)
    factors.setdefault("liquidity", 70)
    factors.setdefault("volatility", 55)
    factors.setdefault("session", 60)
    structure = 50
    if snapshot is not None:
        mtf = getattr(snapshot, "mtf", None)
        if mtf is not None and getattr(mtf, "aligned", None) is True:
            structure = 75
        elif mtf is not None and getattr(mtf, "aligned", None) is False:
            structure = 35
    factors.setdefault("bos", structure)
    factors.setdefault("choch", max(0, structure - 10))
    factors.setdefault("fvg", max(0, structure - 5))
    factors.setdefault("order_block", structure)
    return factors


def champion_from_decision(decision: Any) -> ProfileDecision:
    direction = str(
        getattr(getattr(decision, "direction", None), "value", None)
        or getattr(decision, "direction", "NONE")
        or "NONE"
    ).upper()
    try:
        rr = float(getattr(decision, "estimated_rr", None) or 0)
    except Exception:
        rr = 0.0
    conf = int(getattr(decision, "confidence", 0) or 0)
    return ProfileDecision(
        profile="champion",
        direction=direction,
        confidence=conf,
        opportunity_score=_clamp(conf),  # production confidence proxy when no alpha score
        expected_rr=rr,
        risk_score=int(getattr(decision, "risk_score", 0) or 0),
        may_execute=True,
    )


def evaluate_challenger(
    *,
    decision: Any,
    snapshot: Any | None = None,
    opportunity_score: int | None = None,
    config: PerformanceLabConfig | None = None,
) -> ProfileDecision:
    """Candidate scoring profile — observational only."""
    cfg = config or DEFAULT_LAB_CONFIG
    assert cfg.challenger_may_execute is False  # hard safety
    factors = _factors_from_decision(decision, snapshot)
    tilt = cfg.challenger_weight_tilt or DEFAULT_CHALLENGER_TILT
    weighted = 0.0
    total_w = 0.0
    for k, w in tilt.items():
        score = factors.get(k, 50)
        weighted += score * float(w)
        total_w += float(w)
    score = _clamp(round(weighted / total_w) if total_w else 50)
    conf = _clamp(round(0.55 * score + 0.45 * int(getattr(decision, "confidence", 50) or 50)))

    primary_dir = str(
        getattr(getattr(decision, "direction", None), "value", None)
        or getattr(decision, "direction", "NONE")
        or "NONE"
    ).upper()
    # Challenger may diverge on weak structure without ever trading
    bos = factors.get("bos", 50)
    if score < 48 or bos < 38:
        direction = "NONE"
    elif abs(score - conf) > 25 and bos < 55:
        direction = "SELL" if primary_dir == "BUY" else ("BUY" if primary_dir == "SELL" else "NONE")
    else:
        direction = primary_dir if primary_dir in {"BUY", "SELL"} else "NONE"

    try:
        base_rr = float(getattr(decision, "estimated_rr", None) or 1.5)
    except Exception:
        base_rr = 1.5
    liq = factors.get("liquidity", 50)
    vol = factors.get("volatility", 50)
    rr = round(max(0.5, base_rr * (0.9 + (liq - vol) / 250.0)), 3)
    opp = opportunity_score if opportunity_score is not None else score

    return ProfileDecision(
        profile="challenger",
        direction=direction,
        confidence=conf,
        opportunity_score=_clamp(opp if opportunity_score is not None else score),
        expected_rr=rr,
        risk_score=_clamp(100 - conf),
        may_execute=False,
    )


def _session_regime(snapshot: Any | None, decision: Any) -> tuple[str, str]:
    session = "unknown"
    regime = "unknown"
    if snapshot is not None:
        sess = getattr(snapshot, "session", None)
        if sess is not None:
            session = str(
                getattr(sess, "name", None)
                or getattr(getattr(sess, "session", None), "value", None)
                or getattr(sess, "session", None)
                or "unknown"
            )
        regime = str(getattr(snapshot, "regime", None) or "unknown")
    if regime == "unknown":
        regime = str(getattr(decision, "regime", None) or "unknown")
    return session, regime


def run_champion_challenger(
    *,
    decision: Any,
    snapshot: Any | None = None,
    opportunity_score: int | None = None,
    trace_id: str | None = None,
    config: PerformanceLabConfig | None = None,
) -> ChampionChallengerDuel | None:
    cfg = config or DEFAULT_LAB_CONFIG
    if not cfg.challenger_enabled:
        return None
    if cfg.challenger_may_execute:
        # Safety: refuse to run if misconfigured to execute
        logger.error("challenger_execute_blocked_misconfig")
        return None

    champion = champion_from_decision(decision)
    if opportunity_score is not None:
        champion = ProfileDecision(
            profile="champion",
            direction=champion.direction,
            confidence=champion.confidence,
            opportunity_score=_clamp(opportunity_score),
            expected_rr=champion.expected_rr,
            risk_score=champion.risk_score,
            may_execute=True,
        )
    challenger = evaluate_challenger(
        decision=decision,
        snapshot=snapshot,
        opportunity_score=opportunity_score,
        config=cfg,
    )
    session, regime = _session_regime(snapshot, decision)
    duel = ChampionChallengerDuel(
        id=str(uuid4()),
        at=datetime.now(UTC).isoformat(),
        symbol=str(getattr(decision, "symbol", "") or ""),
        session=session,
        regime=regime,
        trace_id=trace_id,
        champion=champion.to_dict(),
        challenger=challenger.to_dict(),
        agree_direction=champion.direction == challenger.direction,
        confidence_delta=abs(champion.confidence - challenger.confidence),
        score_delta=abs(champion.opportunity_score - challenger.opportunity_score),
        challenger_executed=False,
    )
    get_duel_store().record(duel)
    logger.info(
        "champion_challenger_duel",
        symbol=duel.symbol,
        agree=duel.agree_direction,
        challenger_executed=False,
    )
    return duel


@dataclass
class DuelStore:
    max_rows: int = DEFAULT_LAB_CONFIG.max_duels
    _rows: list[ChampionChallengerDuel] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "champion_challenger_duels.jsonl"

    def record(self, duel: ChampionChallengerDuel) -> None:
        # Enforce invariant
        if duel.challenger_executed:
            raise RuntimeError("Challenger must never execute trades")
        with self._lock:
            self._rows.append(duel)
            if len(self._rows) > self.max_rows:
                self._rows = self._rows[-self.max_rows :]
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(duel.to_dict()) + "\n")
        except Exception:
            logger.exception("duel_persist_failed")

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._rows)
            agree = sum(1 for r in self._rows if r.agree_direction)
            executed = sum(1 for r in self._rows if r.challenger_executed)
        return {
            "total_duels": total,
            "direction_agreement_rate": (
                round(100.0 * agree / total, 2) if total else None
            ),
            "challenger_executions": executed,  # must stay 0
            "challenger_may_execute": False,
        }


_STORE: DuelStore | None = None
_LOCK = threading.Lock()


def get_duel_store() -> DuelStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = DuelStore()
        return _STORE
