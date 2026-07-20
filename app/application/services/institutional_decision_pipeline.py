"""Phase B decision orchestrator.

Snapshot -> Confluence -> Risk -> Eligibility -> Decision.

Never calls OMS / order_send. Deterministic. No AI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from uuid import UUID, uuid4

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.confluence import ConfluenceEngine
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine


def risk_config_from_ite(cfg: ITEConfig) -> RiskEngineConfig:
    """Map ITE defaults onto RiskEngineConfig (XAU contract size)."""
    return RiskEngineConfig(
        max_risk_per_trade_pct=cfg.risk_per_trade_pct,
        max_daily_loss_pct=cfg.max_daily_loss_pct,
        max_weekly_loss_pct=cfg.max_weekly_drawdown_pct,
        max_open_positions=cfg.max_open_trades,
        max_consecutive_losses=cfg.max_consecutive_losses,
        max_spread=cfg.max_spread_reject,
        contract_size=Decimal("100"),
        max_atr_pct_of_price=Decimal("3.0"),
        enforce_session=True,
        enforce_spread=True,
        enforce_atr=True,
    )


def _account_snapshot(
    *, equity: Decimal, free_margin: Decimal | None
) -> AccountSnapshot:
    fm = free_margin if free_margin is not None else equity
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=fm,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=100,
        currency="USD",
        server="ite",
    )


def _synthetic_positions(symbol: str, count: int, entry: Decimal) -> list[MT5Position]:
    out: list[MT5Position] = []
    for i in range(max(0, count)):
        out.append(
            MT5Position(
                ticket=i + 1,
                symbol=symbol,
                side="buy",
                volume=Decimal("0.01"),
                open_price=entry,
                current_price=entry,
            )
        )
    return out


@dataclass
class InstitutionalDecisionPipeline:
    """Phase B pipeline: confluence → risk → eligibility → trade decision."""

    config: ITEConfig = field(default_factory=lambda: DEFAULT_ITE_CONFIG)
    risk_engine: RiskEngine | None = None
    user_id: UUID = field(default_factory=uuid4)

    def __post_init__(self) -> None:
        if self.risk_engine is None:
            self.risk_engine = RiskEngine(config=risk_config_from_ite(self.config))

    def run(
        self,
        snapshot: MarketAnalysisSnapshot,
        account: AccountRiskState,
        *,
        positions: list[MT5Position] | None = None,
        request_id: str | None = None,
    ) -> TradeDecision:
        cfg = self.config
        rid = (request_id or f"ite_{snapshot.input_hash[:12]}").strip()

        daily_dd = Decimal("0")
        if account.equity > 0 and account.daily_pnl < 0:
            daily_dd = abs(account.daily_pnl) / account.equity * Decimal("100")

        confluence = ConfluenceEngine(config=cfg).evaluate(
            snapshot,
            atr=account.atr,
            current_drawdown_pct=daily_dd if daily_dd > 0 else None,
        )

        side = "sell" if confluence.direction is TradeDirection.SELL else "buy"
        stop_distance = account.atr * Decimal("1.5") if account.atr else None
        entry = account.mid_price or Decimal("2300")

        check = RiskCheckInput(
            user_id=self.user_id,
            request_id=rid,
            symbol=snapshot.symbol,
            side=side,
            requested_lots=None,
            stop_loss_distance=stop_distance,
            atr=account.atr,
            sizing_method=PositionSizingMethod.PERCENTAGE_RISK,
            entry_price=entry,
            consecutive_losses=account.consecutive_losses,
            cooldown_active=account.cooldown_active,
            cooldown_remaining_minutes=account.cooldown_remaining_minutes,
            spread=snapshot.spread,
            session_allowed=snapshot.session.allowed,
            session_name=snapshot.session.session.value,
        )

        open_count = max(
            account.open_positions,
            1 if account.already_in_trade else 0,
            len(positions or []),
        )
        pos_list = list(positions or [])
        if len(pos_list) < open_count:
            pos_list = _synthetic_positions(snapshot.symbol, open_count, entry)

        assert self.risk_engine is not None
        assessment = self.risk_engine.evaluate(
            check,
            account=_account_snapshot(
                equity=account.equity, free_margin=account.free_margin
            ),
            positions=pos_list,
            peak_equity=account.peak_equity or account.equity,
            daily_pnl=account.daily_pnl,
            weekly_pnl=account.weekly_pnl,
        )

        risk_allowed = assessment.decision is not RiskDecision.REJECT
        risk_reasons = tuple(assessment.reasons)

        eligibility = PositionEligibilityEngine(config=cfg).evaluate(
            snapshot=snapshot,
            confluence=confluence,
            account=account,
            risk_allowed=risk_allowed,
            risk_reasons=risk_reasons,
        )

        return TradeDecisionEngine(config=cfg).decide(
            snapshot=snapshot,
            confluence=confluence,
            eligibility=eligibility,
            account=account,
            risk_score=assessment.risk_score,
            risk_reasons=risk_reasons,
            approved_lots=assessment.approved_lots if risk_allowed else Decimal("0"),
        )
