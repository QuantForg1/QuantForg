"""Historical Replay Lab + Walk-Forward + Paper — supplied data only."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from app.domain.research_validation_platform.config import ResearchValidationConfig
from app.domain.research_validation_platform.util import (
    dec,
    opt_int,
    reproducible_hash,
)
from app.domain.trading.gold_only import GOLD_SYMBOL


@dataclass
class HistoricalReplayLab:
    """Replay supplied bars only — never invents OHLC."""

    config: ResearchValidationConfig
    _session: dict[str, Any] = field(default_factory=dict)

    def load(
        self,
        *,
        strategy_key: str,
        bars: list[dict[str, Any]],
        version: str | None,
    ) -> dict[str, Any]:
        capped = bars[: self.config.max_replay_bars]
        clean: list[dict[str, Any]] = []
        for bar in capped:
            if not isinstance(bar, dict):
                continue
            if all(k in bar for k in ("open", "high", "low", "close")):
                clean.append(
                    {
                        "time": bar.get("time"),
                        "open": str(bar["open"]),
                        "high": str(bar["high"]),
                        "low": str(bar["low"]),
                        "close": str(bar["close"]),
                    }
                )
        input_payload = {
            "strategy_key": strategy_key,
            "version": version,
            "bars": clean,
        }
        self._session = {
            "strategy_key": strategy_key,
            "version": version,
            "bars": clean,
            "index": 0,
            "input_hash": reproducible_hash(input_payload),
            "symbol": GOLD_SYMBOL,
            "affects_live_execution": False,
            "never_order_send": True,
        }
        return {
            "status": "available" if clean else "empty",
            "strategy_key": strategy_key,
            "version": version,
            "total_bars": len(clean),
            "input_hash": self._session["input_hash"],
            "reproducible": True,
            "affects_live_execution": False,
            "never_order_send": True,
            "invented_bars": False,
        }

    def step(self) -> dict[str, Any]:
        if not self._session.get("bars"):
            return {
                "status": "unavailable",
                "detail": "No replay loaded",
                "affects_live_execution": False,
            }
        bars: list[dict[str, Any]] = self._session["bars"]
        idx = int(self._session.get("index") or 0)
        if idx >= len(bars):
            return {
                "status": "complete",
                "index": idx,
                "total_bars": len(bars),
                "input_hash": self._session.get("input_hash"),
                "affects_live_execution": False,
            }
        current = bars[idx]
        self._session["index"] = idx + 1
        return {
            "status": "available",
            "index": idx,
            "current": current,
            "total_bars": len(bars),
            "input_hash": self._session.get("input_hash"),
            "reproducible": True,
            "affects_live_execution": False,
            "never_order_send": True,
        }

    def status(self) -> dict[str, Any]:
        if not self._session:
            return {"status": "empty", "affects_live_execution": False}
        return {
            "status": "loaded",
            "strategy_key": self._session.get("strategy_key"),
            "version": self._session.get("version"),
            "index": self._session.get("index"),
            "total_bars": len(self._session.get("bars") or []),
            "input_hash": self._session.get("input_hash"),
            "reproducible": True,
            "affects_live_execution": False,
        }


def run_walk_forward(
    payload: dict[str, Any], config: ResearchValidationConfig
) -> dict[str, Any]:
    """Walk-forward from supplied fold metrics — never invents results."""
    folds = payload.get("folds")
    strategy_key = str(payload.get("strategy_key") or "unknown")
    version = str(payload.get("version") or "unversioned")

    if folds is None:
        return {
            "status": "unavailable",
            "strategy_key": strategy_key,
            "version": version,
            "passed": False,
            "score": None,
            "reasons": [
                "No walk-forward folds supplied — never invents results",
            ],
            "input_hash": None,
            "reproducible": False,
            "affects_live_execution": False,
        }
    if not isinstance(folds, list) or len(folds) == 0:
        return {
            "status": "empty",
            "strategy_key": strategy_key,
            "version": version,
            "passed": False,
            "score": "0",
            "reasons": ["Empty folds list"],
            "input_hash": reproducible_hash(
                {"strategy_key": strategy_key, "version": version, "folds": []}
            ),
            "reproducible": True,
            "affects_live_execution": False,
        }

    scores: list[Decimal] = []
    reasons: list[str] = []
    fold_rows: list[dict[str, Any]] = []
    for i, fold in enumerate(folds):
        if not isinstance(fold, dict):
            continue
        s = dec(fold.get("score"))
        pf = dec(fold.get("profit_factor"))
        dd = dec(fold.get("max_drawdown_pct"))
        row = {
            "fold": fold.get("fold", i + 1),
            "score": str(s) if s is not None else None,
            "profit_factor": str(pf) if pf is not None else None,
            "max_drawdown_pct": str(dd) if dd is not None else None,
        }
        fold_rows.append(row)
        if s is not None:
            scores.append(s)

    input_hash = reproducible_hash(
        {
            "strategy_key": strategy_key,
            "version": version,
            "folds": fold_rows,
        }
    )
    if not scores:
        return {
            "status": "unavailable",
            "strategy_key": strategy_key,
            "version": version,
            "passed": False,
            "score": None,
            "folds": fold_rows,
            "reasons": ["Folds present but unscored — not invented"],
            "input_hash": input_hash,
            "reproducible": True,
            "affects_live_execution": False,
        }

    avg = (sum(scores) / Decimal(len(scores))).quantize(Decimal("0.01"))
    passed = avg >= config.min_walkforward_score
    reasons.append(
        f"Avg fold score {avg} vs min {config.min_walkforward_score}"
    )
    reasons.append(f"{len(scores)} scored folds (supplied)")
    reasons.append("Result reproducible via input_hash")
    return {
        "status": "available",
        "strategy_key": strategy_key,
        "version": version,
        "passed": passed,
        "score": str(avg),
        "folds": fold_rows,
        "reasons": reasons,
        "input_hash": input_hash,
        "reproducible": True,
        "affects_live_execution": False,
        "never_order_send": True,
    }


def run_paper_environment(
    payload: dict[str, Any], config: ResearchValidationConfig
) -> dict[str, Any]:
    """Paper trading environment — simulated fills from supplied stats only."""
    strategy_key = str(payload.get("strategy_key") or "unknown")
    version = str(payload.get("version") or "unversioned")
    trades = opt_int(payload.get("trade_count"))
    pf = dec(payload.get("profit_factor"))
    dd = dec(payload.get("max_drawdown_pct"))
    win_rate = dec(payload.get("win_rate"))

    if all(v is None for v in (trades, pf, dd, win_rate)):
        return {
            "status": "unavailable",
            "strategy_key": strategy_key,
            "version": version,
            "passed": False,
            "score": None,
            "reasons": [
                "No paper metrics supplied — never fabricates paper PnL",
            ],
            "input_hash": None,
            "reproducible": False,
            "affects_live_execution": False,
            "paper_only": True,
        }

    score = Decimal("50")
    reasons: list[str] = []
    if pf is not None:
        if pf >= config.min_profit_factor:
            score += Decimal("15")
            reasons.append(
                f"Paper PF {pf} meets min {config.min_profit_factor}"
            )
        else:
            score -= Decimal("10")
            reasons.append(
                f"Paper PF {pf} below min {config.min_profit_factor}"
            )
    if dd is not None:
        if dd <= config.max_drawdown_pct:
            score += Decimal("10")
            reasons.append(
                f"Paper DD {dd}% within max {config.max_drawdown_pct}"
            )
        else:
            score -= Decimal("15")
            reasons.append(
                f"Paper DD {dd}% exceeds max {config.max_drawdown_pct}"
            )
    if trades is not None:
        if trades >= config.min_trades:
            score += Decimal("10")
            reasons.append(
                f"Paper trades {trades} >= min {config.min_trades}"
            )
        else:
            score -= Decimal("5")
            reasons.append(
                f"Paper trades {trades} below min {config.min_trades}"
            )
    if win_rate is not None:
        reasons.append(
            f"Paper win_rate {win_rate}% (supplied, not invented)"
        )

    score = min(max(score, Decimal("0")), Decimal("100")).quantize(
        Decimal("0.01")
    )
    passed = score >= config.min_paper_score
    inputs = {
        "strategy_key": strategy_key,
        "version": version,
        "trade_count": trades,
        "profit_factor": str(pf) if pf is not None else None,
        "max_drawdown_pct": str(dd) if dd is not None else None,
        "win_rate": str(win_rate) if win_rate is not None else None,
    }
    reasons.append(
        "Paper environment isolated from live execution pipeline"
    )
    return {
        "status": "available",
        "strategy_key": strategy_key,
        "version": version,
        "passed": passed,
        "score": str(score),
        "reasons": reasons,
        "input_hash": reproducible_hash(inputs),
        "reproducible": True,
        "affects_live_execution": False,
        "never_order_send": True,
        "paper_only": True,
        "inputs": inputs,
    }
