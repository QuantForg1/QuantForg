"""Shadow AI — independent second evaluation before live trade."""

from __future__ import annotations

import json
import threading
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.institutional_trading.ai_validation.config import (
    DEFAULT_AI_VALIDATION_CONFIG,
    AiValidationConfig,
)
from core.logging import get_logger

logger = get_logger(__name__)

# Independent weight set — intentionally different from primary Opportunity Score
_SHADOW_WEIGHTS: dict[str, float] = {
    "trend": 1.35,
    "momentum": 1.15,
    "liquidity": 0.95,
    "volatility": 0.85,
    "session": 1.05,
    "structure": 1.20,  # BOS/CHOCH/FVG/OB blend
}


@dataclass(frozen=True, slots=True)
class ShadowVerdict:
    direction: str
    confidence: int
    risk_score: int
    expected_rr: float
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "direction": self.direction,
            "confidence": self.confidence,
            "risk_score": self.risk_score,
            "expected_rr": self.expected_rr,
            "reasons": list(self.reasons),
        }


@dataclass(frozen=True, slots=True)
class ShadowComparison:
    id: str
    created_at: str
    symbol: str
    trace_id: str | None
    primary: dict[str, Any]
    shadow: dict[str, Any]
    significant_disagreement: bool
    disagreement_flags: tuple[str, ...]
    used_engine: str  # primary | shadow (shadow only if veto enabled)

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["disagreement_flags"] = list(self.disagreement_flags)
        return d


def _clamp(n: int) -> int:
    return max(0, min(100, int(n)))


def _factor_map(decision: Any, snapshot: Any | None = None) -> dict[str, int]:
    factors: dict[str, int] = {}
    confluence = getattr(decision, "confluence", None)
    raw = getattr(confluence, "factors", None) if confluence is not None else None
    if isinstance(raw, dict):
        for k, v in raw.items():
            try:
                factors[str(k).lower()] = _clamp(int(v))
            except Exception:
                continue
    # Fallbacks from decision quality / confidence
    conf = int(getattr(decision, "confidence", 50) or 50)
    quality = int(getattr(decision, "quality", conf) or conf)
    factors.setdefault("trend", quality)
    factors.setdefault("momentum", conf)
    factors.setdefault("liquidity", 70)
    factors.setdefault("volatility", 55)
    factors.setdefault("session", 60)
    # Structure proxies from snapshot if present
    structure = 50
    if snapshot is not None:
        mtf = getattr(snapshot, "mtf", None) or getattr(snapshot, "structure", None)
        if mtf is not None:
            aligned = getattr(mtf, "aligned", None)
            if aligned is True:
                structure = 75
            elif aligned is False:
                structure = 35
    factors["structure"] = structure
    # Map structure into SMC labels for optimizer feedback
    factors.setdefault("bos", structure)
    factors.setdefault("choch", max(0, structure - 10))
    factors.setdefault("fvg", max(0, structure - 5))
    factors.setdefault("order_block", structure)
    return factors


def evaluate_shadow(
    *,
    decision: Any,
    snapshot: Any | None = None,
    config: AiValidationConfig | None = None,
) -> ShadowVerdict:
    """Independent evaluation — does not call OMS; does not mutate primary."""
    _ = config or DEFAULT_AI_VALIDATION_CONFIG
    factors = _factor_map(decision, snapshot)
    weighted = 0.0
    total_w = 0.0
    for key, w in _SHADOW_WEIGHTS.items():
        score = factors.get(key, 50)
        weighted += score * w
        total_w += w
    conf = _clamp(round(weighted / total_w) if total_w else 50)

    # Direction: prefer confluence if strong structure/momentum; else NONE
    primary_dir = str(
        getattr(getattr(decision, "direction", None), "value", None)
        or getattr(decision, "direction", "NONE")
        or "NONE"
    ).upper()
    # Shadow may flip only when structure weakly supports primary
    structure = factors.get("structure", 50)
    momentum = factors.get("momentum", 50)
    if conf < 45 or structure < 40:
        direction = "NONE"
    elif abs(momentum - structure) > 35 and structure < 50:
        # Independent disagreement signal
        direction = "SELL" if primary_dir == "BUY" else ("BUY" if primary_dir == "SELL" else "NONE")
    else:
        direction = primary_dir if primary_dir in {"BUY", "SELL"} else "NONE"

    primary_rr = getattr(decision, "estimated_rr", None)
    try:
        base_rr = float(primary_rr) if primary_rr is not None else 1.5
    except Exception:
        base_rr = 1.5
    # Shadow RR tilted by volatility/liquidity
    vol = factors.get("volatility", 50)
    liq = factors.get("liquidity", 50)
    shadow_rr = round(max(0.5, base_rr * (0.85 + (liq - vol) / 200.0)), 3)

    risk = _clamp(100 - conf + max(0, 60 - liq) // 2)
    reasons = (
        f"shadow_conf={conf}",
        f"structure={structure}",
        f"momentum={momentum}",
        f"shadow_rr={shadow_rr}",
    )
    return ShadowVerdict(
        direction=direction,
        confidence=conf,
        risk_score=risk,
        expected_rr=shadow_rr,
        reasons=reasons,
    )


def compare_primary_shadow(
    *,
    decision: Any,
    shadow: ShadowVerdict,
    config: AiValidationConfig | None = None,
    trace_id: str | None = None,
) -> ShadowComparison:
    cfg = config or DEFAULT_AI_VALIDATION_CONFIG
    primary_dir = str(
        getattr(getattr(decision, "direction", None), "value", None)
        or getattr(decision, "direction", "NONE")
        or "NONE"
    ).upper()
    primary_conf = int(getattr(decision, "confidence", 0) or 0)
    primary_risk = int(getattr(decision, "risk_score", 0) or 0)
    try:
        primary_rr = float(getattr(decision, "estimated_rr", None) or 0)
    except Exception:
        primary_rr = 0.0

    flags: list[str] = []
    if primary_dir != shadow.direction and (
        primary_dir in {"BUY", "SELL"} or shadow.direction in {"BUY", "SELL"}
    ):
        flags.append(f"direction {primary_dir}≠{shadow.direction}")
    if abs(primary_conf - shadow.confidence) >= cfg.shadow_confidence_delta:
        flags.append(f"confidence Δ{abs(primary_conf - shadow.confidence)}")
    if abs(primary_risk - shadow.risk_score) >= cfg.shadow_risk_delta:
        flags.append(f"risk Δ{abs(primary_risk - shadow.risk_score)}")
    if abs(primary_rr - shadow.expected_rr) >= cfg.shadow_rr_delta:
        flags.append(f"rr Δ{round(abs(primary_rr - shadow.expected_rr), 3)}")

    significant = len(flags) > 0
    primary_payload = {
        "direction": primary_dir,
        "confidence": primary_conf,
        "risk_score": primary_risk,
        "expected_rr": primary_rr,
        "action": str(getattr(getattr(decision, "action", None), "value", decision.action)),
    }
    used = "primary"
    if significant and cfg.shadow_veto_enabled:
        used = "shadow"  # reserved; runtime still respects primary unless caller acts

    return ShadowComparison(
        id=str(uuid4()),
        created_at=datetime.now(UTC).isoformat(),
        symbol=str(getattr(decision, "symbol", "") or ""),
        trace_id=trace_id,
        primary=primary_payload,
        shadow=shadow.to_dict(),
        significant_disagreement=significant,
        disagreement_flags=tuple(flags),
        used_engine=used,
    )


@dataclass
class ShadowComparisonStore:
    max_rows: int = DEFAULT_AI_VALIDATION_CONFIG.max_shadow_comparisons
    _rows: list[ShadowComparison] = field(default_factory=list)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _path: Path | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._path is None:
            try:
                from core.config.settings import get_settings

                base = Path(getattr(get_settings(), "data_dir", None) or "data")
            except Exception:
                base = Path("data")
            self._path = base / "shadow_ai_comparisons.jsonl"

    def record(self, comparison: ShadowComparison) -> ShadowComparison:
        with self._lock:
            self._rows.append(comparison)
            if len(self._rows) > self.max_rows:
                self._rows = self._rows[-self.max_rows :]
        if comparison.significant_disagreement:
            logger.warning(
                "shadow_ai_disagreement",
                symbol=comparison.symbol,
                flags=list(comparison.disagreement_flags),
                primary=comparison.primary,
                shadow=comparison.shadow,
                used_engine=comparison.used_engine,
            )
        else:
            logger.info(
                "shadow_ai_comparison",
                symbol=comparison.symbol,
                significant=False,
            )
        try:
            if self._path is not None:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                with self._path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(comparison.to_dict()) + "\n")
        except Exception:
            logger.exception("shadow_ai_persist_failed")
        return comparison

    def recent(self, *, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._rows[-max(1, limit) :]
        return [r.to_dict() for r in reversed(rows)]

    def summary(self) -> dict[str, Any]:
        with self._lock:
            total = len(self._rows)
            disagreements = sum(1 for r in self._rows if r.significant_disagreement)
        return {
            "total_comparisons": total,
            "significant_disagreements": disagreements,
            "agreement_rate": (
                round(100.0 * (total - disagreements) / total, 2) if total else None
            ),
        }


_STORE: ShadowComparisonStore | None = None
_LOCK = threading.Lock()


def get_shadow_store() -> ShadowComparisonStore:
    global _STORE
    with _LOCK:
        if _STORE is None:
            _STORE = ShadowComparisonStore()
        return _STORE


def run_shadow_validation(
    *,
    decision: Any,
    snapshot: Any | None = None,
    trace_id: str | None = None,
    config: AiValidationConfig | None = None,
) -> ShadowComparison | None:
    cfg = config or DEFAULT_AI_VALIDATION_CONFIG
    if not cfg.shadow_enabled:
        return None
    shadow = evaluate_shadow(decision=decision, snapshot=snapshot, config=cfg)
    comparison = compare_primary_shadow(
        decision=decision, shadow=shadow, config=cfg, trace_id=trace_id
    )
    get_shadow_store().record(comparison)
    return comparison
