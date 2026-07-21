"""Loss protection gates for Decision Engine V1."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_ai_decision.config import DecisionEngineV1Config


@dataclass(frozen=True, slots=True)
class LossProtectionResult:
    passed: bool
    consecutive_losses_ok: bool
    daily_drawdown_ok: bool
    spread_ok: bool
    volatility_ok: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "passed": self.passed,
            "consecutive_losses_ok": self.consecutive_losses_ok,
            "daily_drawdown_ok": self.daily_drawdown_ok,
            "spread_ok": self.spread_ok,
            "volatility_ok": self.volatility_ok,
            "reasons": list(self.reasons),
        }


def evaluate_loss_protection(
    config: DecisionEngineV1Config,
    *,
    consecutive_losses: int,
    daily_drawdown_pct: Decimal,
    spread: Decimal | None,
    atr: Decimal | None,
    price: Decimal | None,
) -> LossProtectionResult:
    reasons: list[str] = []
    losses_ok = consecutive_losses < config.max_consecutive_losses
    if not losses_ok:
        reasons.append(
            f"Consecutive losses {consecutive_losses} >= "
            f"{config.max_consecutive_losses}."
        )

    dd_ok = daily_drawdown_pct < config.max_daily_drawdown_pct
    if not dd_ok:
        reasons.append(
            f"Daily drawdown {daily_drawdown_pct}% reached "
            f"{config.max_daily_drawdown_pct}%."
        )

    if spread is None:
        spread_ok = False
        reasons.append("Spread unavailable — abnormal-spread gate fail-closed.")
    else:
        spread_ok = spread <= config.max_spread
        if not spread_ok:
            reasons.append(
                f"Abnormal spread {spread} exceeds {config.max_spread}."
            )

    if atr is None or price is None or price <= 0:
        vol_ok = False
        reasons.append("ATR/price unavailable — volatility gate fail-closed.")
    else:
        atr_pct = (atr / price * Decimal("100")).quantize(Decimal("0.01"))
        if atr_pct > config.max_atr_pct_of_price:
            vol_ok = False
            reasons.append(
                f"Abnormal volatility ATR {atr_pct}% > "
                f"{config.max_atr_pct_of_price}%."
            )
        elif atr_pct < config.min_atr_pct_of_price:
            vol_ok = False
            reasons.append(
                f"Abnormal low volatility ATR {atr_pct}% < "
                f"{config.min_atr_pct_of_price}%."
            )
        else:
            vol_ok = True

    passed = losses_ok and dd_ok and spread_ok and vol_ok
    if passed:
        reasons.append("Loss protection gates clear.")
    return LossProtectionResult(
        passed=passed,
        consecutive_losses_ok=losses_ok,
        daily_drawdown_ok=dd_ok,
        spread_ok=spread_ok,
        volatility_ok=vol_ok,
        reasons=tuple(reasons),
    )
