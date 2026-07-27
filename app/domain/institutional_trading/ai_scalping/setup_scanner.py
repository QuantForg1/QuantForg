"""Multi-signal setup scanner — independent families, best-only selection.

A failed setup must NOT reject other valid setups. Quality floors are never
lowered; selection only ranks candidates that already clear local structure
evidence. Global institutional gates still apply after selection.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from app.domain.institutional_trading.ai_scalping.config import (
    DEFAULT_AI_SCALPING_CONFIG,
    AiScalpingConfig,
    SetupFamily,
)
from app.domain.institutional_trading.decision_models import TradeDirection

SetupFamilyName = SetupFamily


@dataclass(frozen=True, slots=True)
class SetupCandidate:
    family: SetupFamilyName
    score: int
    direction: str  # BUY | SELL | NONE
    passed: bool
    reasons: tuple[str, ...]
    evidence: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "family": self.family,
            "score": self.score,
            "direction": self.direction,
            "passed": self.passed,
            "reasons": list(self.reasons),
            "evidence": dict(self.evidence),
        }


@dataclass(frozen=True, slots=True)
class SetupScanResult:
    candidates: tuple[SetupCandidate, ...]
    best: SetupCandidate | None
    selected_family: str | None
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidates": [c.to_dict() for c in self.candidates],
            "best": self.best.to_dict() if self.best else None,
            "selected_family": self.selected_family,
            "reasons": list(self.reasons),
            "note": "Highest-quality setup only — failed families do not poison others.",
        }


def _dir_str(buy: int, sell: int) -> str:
    if buy > sell and buy >= 55:
        return TradeDirection.BUY.value
    if sell > buy and sell >= 55:
        return TradeDirection.SELL.value
    return TradeDirection.NONE.value


def _score_pullback(
    *,
    alignment: int,
    bos: int,
    momentum: int,
    ema: int,
    buy: int,
    sell: int,
    min_pass: int,
) -> SetupCandidate:
    reasons: list[str] = []
    # Pullback continuation needs trend + soft momentum recovery + EMA lean
    base = 0
    if alignment >= 70 and bos:
        base += 35
        reasons.append("Aligned trend with BOS for pullback continuation")
    elif alignment >= 60:
        base += 20
        reasons.append("Moderate alignment for pullback")
    if 55 <= momentum <= 85:
        base += 25
        reasons.append("Momentum in continuation band")
    elif momentum >= 50:
        base += 10
    if ema >= 60:
        base += 25
        reasons.append("EMA stack supports continuation")
    elif ema >= 45:
        base += 10
    score = max(0, min(100, base))
    direction = _dir_str(buy, sell) if score >= min_pass else TradeDirection.NONE.value
    passed = score >= min_pass and direction != TradeDirection.NONE.value
    if not passed:
        reasons.append(f"Pullback score {score} < {min_pass} or no direction")
    return SetupCandidate(
        family="pullback_continuation",
        score=score,
        direction=direction if passed else TradeDirection.NONE.value,
        passed=passed,
        reasons=tuple(reasons),
        evidence={
            "alignment": alignment,
            "bos": bos,
            "momentum": momentum,
            "ema": ema,
        },
    )


def _score_bos(
    *,
    bos: int,
    alignment: int,
    volume: int,
    buy: int,
    sell: int,
    min_pass: int,
) -> SetupCandidate:
    reasons: list[str] = []
    base = 0
    if bos:
        base += 45
        reasons.append(f"BOS count={bos}")
    if alignment >= 65:
        base += 30
        reasons.append("MTF aligned with BOS continuation")
    elif alignment >= 50:
        base += 15
    if volume >= 65:
        base += 20
        reasons.append("Volume supports BOS continuation")
    score = max(0, min(100, base))
    direction = _dir_str(buy, sell) if score >= min_pass else TradeDirection.NONE.value
    passed = score >= min_pass and direction != TradeDirection.NONE.value
    if not passed:
        reasons.append(f"BOS continuation score {score} < {min_pass} or no direction")
    return SetupCandidate(
        family="bos_continuation",
        score=score,
        direction=direction if passed else TradeDirection.NONE.value,
        passed=passed,
        reasons=tuple(reasons),
        evidence={"bos": bos, "alignment": alignment, "volume": volume},
    )


def _score_choch(
    *,
    choch: int,
    sweeps: int,
    alignment: int,
    buy: int,
    sell: int,
    min_pass: int,
) -> SetupCandidate:
    reasons: list[str] = []
    base = 0
    if choch:
        base += 40
        reasons.append(f"CHOCH count={choch}")
    if sweeps:
        base += 25
        reasons.append(f"Sweep confirmation sweeps={sweeps}")
    # Reversal prefers weaker prior alignment (exhausted trend)
    if alignment < 60:
        base += 20
        reasons.append("Prior trend soft — CHOCH reversal favored")
    elif alignment < 75:
        base += 8
    score = max(0, min(100, base))
    # Flip lean: if buy dominated prior, sell reversal and vice versa
    if choch and sweeps:
        if buy >= sell:
            direction = TradeDirection.SELL.value
        else:
            direction = TradeDirection.BUY.value
    else:
        direction = _dir_str(buy, sell)
    passed = score >= min_pass and direction != TradeDirection.NONE.value
    if not passed:
        reasons.append(f"CHOCH reversal score {score} < {min_pass} or no direction")
        direction = TradeDirection.NONE.value
    return SetupCandidate(
        family="choch_reversal",
        score=score,
        direction=direction if passed else TradeDirection.NONE.value,
        passed=passed,
        reasons=tuple(reasons),
        evidence={"choch": choch, "sweeps": sweeps, "alignment": alignment},
    )


def _score_sweep_reversal(
    *,
    sweeps: int,
    choch: int,
    liquidity: int,
    buy: int,
    sell: int,
    min_pass: int,
) -> SetupCandidate:
    reasons: list[str] = []
    base = 0
    if sweeps:
        base += 45
        reasons.append(f"Liquidity sweeps={sweeps}")
    if liquidity >= 70:
        base += 25
        reasons.append("Liquidity quality supportive")
    elif liquidity >= 55:
        base += 12
    if choch:
        base += 15
        reasons.append("CHOCH accompanies sweep reversal")
    score = max(0, min(100, base))
    if sweeps and buy >= sell:
        direction = TradeDirection.SELL.value
    elif sweeps:
        direction = TradeDirection.BUY.value
    else:
        direction = TradeDirection.NONE.value
    passed = score >= min_pass and direction != TradeDirection.NONE.value
    if not passed:
        reasons.append(f"Sweep reversal score {score} < {min_pass} or no direction")
        direction = TradeDirection.NONE.value
    return SetupCandidate(
        family="liquidity_sweep_reversal",
        score=score,
        direction=direction if passed else TradeDirection.NONE.value,
        passed=passed,
        reasons=tuple(reasons),
        evidence={"sweeps": sweeps, "choch": choch, "liquidity": liquidity},
    )


def _score_fvg(
    *,
    open_fvg: int,
    alignment: int,
    momentum: int,
    buy: int,
    sell: int,
    min_pass: int,
) -> SetupCandidate:
    reasons: list[str] = []
    base = 0
    if open_fvg:
        base += 45
        reasons.append(f"Active FVG gaps={open_fvg}")
    if alignment >= 60:
        base += 25
        reasons.append("Alignment supports FVG continuation")
    if momentum >= 60:
        base += 20
        reasons.append("Momentum supports FVG fill continuation")
    score = max(0, min(100, base))
    direction = _dir_str(buy, sell) if score >= min_pass else TradeDirection.NONE.value
    passed = score >= min_pass and direction != TradeDirection.NONE.value
    if not passed:
        reasons.append(f"FVG continuation score {score} < {min_pass} or no direction")
    return SetupCandidate(
        family="fvg_continuation",
        score=score,
        direction=direction if passed else TradeDirection.NONE.value,
        passed=passed,
        reasons=tuple(reasons),
        evidence={"fvg": open_fvg, "alignment": alignment, "momentum": momentum},
    )


def _score_breakout(
    *,
    bos: int,
    volume: int,
    atr_band: str,
    alignment: int,
    buy: int,
    sell: int,
    min_pass: int,
) -> SetupCandidate:
    reasons: list[str] = []
    base = 0
    if bos and volume >= 70:
        base += 50
        reasons.append("BOS + volume expansion → breakout continuation")
    elif bos:
        base += 25
        reasons.append("BOS without strong volume")
    if atr_band == "high":
        base += 25
        reasons.append("High ATR expansion favors breakout")
    elif atr_band == "normal":
        base += 10
    if alignment >= 55:
        base += 15
    score = max(0, min(100, base))
    direction = _dir_str(buy, sell) if score >= min_pass else TradeDirection.NONE.value
    passed = score >= min_pass and direction != TradeDirection.NONE.value
    if not passed:
        reasons.append(f"Breakout continuation score {score} < {min_pass} or no direction")
    return SetupCandidate(
        family="breakout_continuation",
        score=score,
        direction=direction if passed else TradeDirection.NONE.value,
        passed=passed,
        reasons=tuple(reasons),
        evidence={
            "bos": bos,
            "volume": volume,
            "alignment": alignment,
            "atr_high": 1 if atr_band == "high" else 0,
        },
    )


def scan_setup_families(
    *,
    alignment: int = 0,
    bos: int = 0,
    choch: int = 0,
    sweeps: int = 0,
    open_fvg: int = 0,
    momentum: int = 50,
    volume: int = 50,
    liquidity: int = 50,
    ema: int = 50,
    buy_score: int = 50,
    sell_score: int = 50,
    atr_band: Literal["high", "normal", "low"] = "normal",
    config: AiScalpingConfig | None = None,
) -> SetupScanResult:
    """Score each setup family independently; return highest-quality passer."""
    cfg = config or DEFAULT_AI_SCALPING_CONFIG
    min_pass = int(cfg.setup_min_local_score)

    candidates = (
        _score_pullback(
            alignment=alignment,
            bos=bos,
            momentum=momentum,
            ema=ema,
            buy=buy_score,
            sell=sell_score,
            min_pass=min_pass,
        ),
        _score_bos(
            bos=bos,
            alignment=alignment,
            volume=volume,
            buy=buy_score,
            sell=sell_score,
            min_pass=min_pass,
        ),
        _score_choch(
            choch=choch,
            sweeps=sweeps,
            alignment=alignment,
            buy=buy_score,
            sell=sell_score,
            min_pass=min_pass,
        ),
        _score_sweep_reversal(
            sweeps=sweeps,
            choch=choch,
            liquidity=liquidity,
            buy=buy_score,
            sell=sell_score,
            min_pass=min_pass,
        ),
        _score_fvg(
            open_fvg=open_fvg,
            alignment=alignment,
            momentum=momentum,
            buy=buy_score,
            sell=sell_score,
            min_pass=min_pass,
        ),
        _score_breakout(
            bos=bos,
            volume=volume,
            atr_band=atr_band,
            alignment=alignment,
            buy=buy_score,
            sell=sell_score,
            min_pass=min_pass,
        ),
    )

    passed = [c for c in candidates if c.passed]
    best = max(passed, key=lambda c: (c.score, c.family)) if passed else None
    meta: list[str] = []
    if best:
        meta.append(
            f"Selected setup={best.family} score={best.score} dir={best.direction}"
        )
        failed_n = len(candidates) - len(passed)
        if failed_n:
            meta.append(
                f"{failed_n} other setup(s) failed independently — not blocking winner"
            )
    else:
        meta.append("No setup family cleared local evidence floor")

    return SetupScanResult(
        candidates=candidates,
        best=best,
        selected_family=best.family if best else None,
        reasons=tuple(meta),
    )
