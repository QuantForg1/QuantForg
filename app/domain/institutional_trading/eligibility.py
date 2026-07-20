"""Position Eligibility Engine — last gate before OMS (never calls OMS)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from app.domain.institutional_trading.config import ITEConfig
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    ConfluenceResult,
    EligibilityResult,
    TradeDirection,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot


@dataclass(frozen=True, slots=True)
class PositionEligibilityEngine:
    """Answer every pre-OMS checklist question. Any NO → ineligible."""

    config: ITEConfig

    def evaluate(
        self,
        *,
        snapshot: MarketAnalysisSnapshot,
        confluence: ConfluenceResult,
        account: AccountRiskState,
        risk_allowed: bool,
        risk_reasons: tuple[str, ...] = (),
    ) -> EligibilityResult:
        cfg = self.config
        checks: dict[str, bool] = {}
        rejects: list[str] = []

        checks["already_in_trade"] = not account.already_in_trade
        if account.already_in_trade:
            rejects.append("Already in trade")

        checks["max_open_trades"] = account.open_positions < cfg.max_open_trades
        if not checks["max_open_trades"]:
            rejects.append(
                f"Open positions {account.open_positions} at max {cfg.max_open_trades}"
            )

        checks["risk_available"] = risk_allowed
        if not risk_allowed:
            rejects.extend(risk_reasons or ("Risk engine rejected",))

        checks["market_open"] = account.market_open
        if not account.market_open:
            rejects.append("Market is closed")

        spread = snapshot.spread
        checks["spread_acceptable"] = (
            spread is None or spread <= cfg.max_spread_reject
        )
        if not checks["spread_acceptable"]:
            rejects.append(f"Spread {spread} not acceptable")

        checks["session_valid"] = snapshot.session.allowed
        if not snapshot.session.allowed:
            rejects.append(snapshot.session.reason)

        checks["news_clear"] = not snapshot.news.blocked
        if snapshot.news.blocked:
            rejects.append(snapshot.news.reason)

        checks["confluence_ok"] = (
            confluence.passed
            and confluence.confidence >= cfg.min_confluence_score
            and confluence.direction is not TradeDirection.NONE
        )
        if not checks["confluence_ok"]:
            rejects.append(
                f"Confluence {confluence.confidence} "
                f"({confluence.direction.value}) below institutional gate"
            )

        checks["quality_ok"] = (
            snapshot.trade_quality.passed
            and snapshot.trade_quality.total >= cfg.min_trade_quality_score
        )
        if not checks["quality_ok"]:
            rejects.append(
                f"Trade quality {snapshot.trade_quality.total} below "
                f"{cfg.min_trade_quality_score}"
            )

        if account.free_margin is not None and account.free_margin <= 0:
            checks["margin_available"] = False
            rejects.append("Insufficient free margin")
        else:
            checks["margin_available"] = True

        # Exposure proxy: equity must be positive
        checks["exposure_ok"] = account.equity > 0
        if not checks["exposure_ok"]:
            rejects.append("Equity not available")

        eligible = all(checks.values())
        return EligibilityResult(
            eligible=eligible,
            checks=checks,
            rejection_reasons=tuple(dict.fromkeys(rejects)),
        )
