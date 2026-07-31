"""Phase B decision orchestrator.

Snapshot -> Confluence -> Risk -> Eligibility -> Decision.

Never calls OMS / order_send. Deterministic.
Scalping mode overlays adaptive thresholds + broker-aware lot sizing.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from decimal import Decimal
from typing import Any
from uuid import UUID, uuid4

from app.application.services.risk_engine import RiskCheckInput, RiskEngine
from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import RiskEngineConfig
from app.domain.enums.risk import PositionSizingMethod, RiskDecision
from app.domain.institutional_trading.config import DEFAULT_ITE_CONFIG, ITEConfig
from app.domain.institutional_trading.confluence import ConfluenceEngine
from app.domain.institutional_trading.decision_models import (
    AccountRiskState,
    EligibilityResult,
    TradeDecision,
    TradeDirection,
)
from app.domain.institutional_trading.eligibility import PositionEligibilityEngine
from app.domain.institutional_trading.executable_direction import (
    resolve_executable_direction,
)
from app.domain.institutional_trading.models import MarketAnalysisSnapshot
from app.domain.institutional_trading.trade_decision import TradeDecisionEngine
from core.logging import get_logger

logger = get_logger(__name__)


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


def _synthetic_positions(
    symbol: str,
    count: int,
    entry: Decimal,
    *,
    side: str = "buy",
) -> list[MT5Position]:
    side_l = (side or "buy").lower()
    if side_l not in {"buy", "sell"}:
        side_l = "buy"
    out: list[MT5Position] = []
    for i in range(max(0, count)):
        out.append(
            MT5Position(
                ticket=i + 1,
                symbol=symbol,
                side=side_l,
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
    _last_ai_score: dict[str, Any] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.risk_engine is None:
            self.risk_engine = RiskEngine(config=risk_config_from_ite(self.config))

    def last_ai_score(self) -> dict[str, Any] | None:
        return dict(self._last_ai_score) if self._last_ai_score else None

    def _prepare_config(self, account: AccountRiskState) -> ITEConfig:
        cfg = self.config
        if not cfg.is_scalping():
            return cfg
        from app.domain.institutional_trading.ai_scalping.adaptive_thresholds import (
            apply_thresholds_to_ite,
            resolve_adaptive_thresholds,
        )
        from app.domain.institutional_trading.ai_scalping.config import (
            DEFAULT_AI_SCALPING_CONFIG,
        )

        resolved = resolve_adaptive_thresholds(
            account.atr,
            account.mid_price,
            config=DEFAULT_AI_SCALPING_CONFIG,
        )
        return apply_thresholds_to_ite(cfg, resolved)

    def run(
        self,
        snapshot: MarketAnalysisSnapshot,
        account: AccountRiskState,
        *,
        positions: list[MT5Position] | None = None,
        request_id: str | None = None,
    ) -> TradeDecision:
        cfg = self._prepare_config(account)
        rid = (request_id or f"ite_{snapshot.input_hash[:12]}").strip()

        daily_dd = Decimal("0")
        if account.equity > 0 and account.daily_pnl < 0:
            daily_dd = abs(account.daily_pnl) / account.equity * Decimal("100")

        # Scalping AI score overlay — quality gates + balanced BUY/SELL
        ai_score = None
        if cfg.is_scalping():
            try:
                from app.domain.institutional_trading.ai_scalping.config import (
                    DEFAULT_AI_SCALPING_CONFIG,
                )
                from app.domain.institutional_trading.ai_scalping.diagnostics import (
                    get_scalping_diagnostics_store,
                )
                from app.domain.institutional_trading.ai_scalping.learning import (
                    get_scalping_learning_store,
                )
                from app.domain.institutional_trading.ai_scalping.scoring import (
                    score_scalping_setup,
                )

                session_name = str(
                    getattr(snapshot.session.session, "value", snapshot.session.session)
                )
                hist = None
                if DEFAULT_AI_SCALPING_CONFIG.learning_enabled:
                    hist = get_scalping_learning_store().historical_similarity_bonus(
                        session=session_name,
                        confidence=70,
                        regime=None,
                        spread=snapshot.spread,
                    )
                ai_score = score_scalping_setup(
                    snapshot,
                    atr=account.atr,
                    mid=account.mid_price,
                    historical_similarity=hist,
                    config=DEFAULT_AI_SCALPING_CONFIG,
                    enforce_adaptive_cooldown=True,
                    symbol=str(getattr(snapshot, "symbol", "") or ""),
                )
                self._last_ai_score = ai_score.to_dict()
                diag = get_scalping_diagnostics_store()
                if ai_score.reject:
                    diag.record(
                        outcome="rejected",
                        symbol=str(snapshot.symbol),
                        direction=ai_score.direction,
                        confidence=ai_score.confidence,
                        reason=ai_score.reject_reason or "quality gates failed",
                        details=ai_score.to_dict(),
                    )
                else:
                    diag.record(
                        outcome="taken",
                        symbol=str(snapshot.symbol),
                        direction=ai_score.direction,
                        confidence=ai_score.confidence,
                        reason="; ".join(ai_score.reasons[-3:])
                        or "quality gates passed",
                        details=ai_score.to_dict(),
                    )
            except Exception:
                self._last_ai_score = None
                ai_score = None
        else:
            self._last_ai_score = None

        confluence = ConfluenceEngine(config=cfg).evaluate(
            snapshot,
            atr=account.atr,
            current_drawdown_pct=daily_dd if daily_dd > 0 else None,
        )

        # Final validated direction — never BUY-default; never flip AI SELL → BUY OMS
        exe = resolve_executable_direction(
            confluence=confluence,
            ai_direction=getattr(ai_score, "direction", None) if ai_score else None,
            ai_reject=bool(ai_score.reject) if ai_score is not None else None,
            scalping=cfg.is_scalping(),
        )
        if exe.direction in {TradeDirection.BUY, TradeDirection.SELL}:
            confluence = replace(
                confluence,
                direction=exe.direction,
                reasons=tuple(dict.fromkeys((*confluence.reasons, exe.reason))),
            )
            side = "buy" if exe.direction is TradeDirection.BUY else "sell"
        else:
            confluence = replace(
                confluence,
                direction=TradeDirection.NONE,
                passed=False,
                reasons=tuple(dict.fromkeys((*confluence.reasons, exe.reason))),
            )
            # No executable side — fail closed for risk sizing (never invent BUY)
            side = "none"

        stop_mult = Decimal("1.10") if cfg.is_scalping() else Decimal("1.5")
        stop_distance = account.atr * stop_mult if account.atr else None
        # Structure-based stop distance when AI computed one
        if ai_score is not None and self._last_ai_score:
            raw_sd = self._last_ai_score.get("stop_loss")
            entry_s = self._last_ai_score.get("entry")
            try:
                if raw_sd and entry_s and account.mid_price:
                    from decimal import Decimal as _D

                    sd = abs(_D(str(entry_s)) - _D(str(raw_sd)))
                    if sd > 0:
                        stop_distance = sd
            except Exception:  # noqa: S110  # best-effort optional path
                pass
        entry = account.mid_price
        if entry is None or entry <= 0:
            # Prefer No Trade — never invent an entry price for risk sizing.
            return TradeDecisionEngine(config=cfg).decide(
                snapshot=snapshot,
                confluence=confluence,
                eligibility=EligibilityResult(
                    eligible=False,
                    checks={"entry_price_available": False},
                    rejection_reasons=("decision_entry_price_unavailable",),
                ),
                account=account,
                risk_score=100,
                risk_reasons=("decision_entry_price_unavailable",),
                approved_lots=Decimal("0"),
            )

        if side not in {"buy", "sell"}:
            return TradeDecisionEngine(config=cfg).decide(
                snapshot=snapshot,
                confluence=confluence,
                eligibility=EligibilityResult(
                    eligible=False,
                    checks={"validated_direction": False},
                    rejection_reasons=(exe.reason or "no_validated_direction",),
                ),
                account=account,
                risk_score=100,
                risk_reasons=(exe.reason or "no_validated_direction",),
                approved_lots=Decimal("0"),
            )

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
            pos_list = _synthetic_positions(
                snapshot.symbol, open_count, entry, side=side
            )

        assert self.risk_engine is not None
        # Keep risk engine limits in sync with adaptive / scalping config.
        self.risk_engine = RiskEngine(config=risk_config_from_ite(cfg))
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
        risk_reasons = list(assessment.reasons)
        approved_lots = assessment.approved_lots if risk_allowed else Decimal("0")

        # Broker-aware scalping lot overlay (never invent fixed lots)
        if cfg.is_scalping() and risk_allowed:
            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG,
            )
            from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
                may_add_scalping_trade,
            )
            from app.domain.institutional_trading.ai_scalping.sizing import (
                calculate_scalping_lots,
            )

            sized = calculate_scalping_lots(
                equity=account.equity,
                stop_distance=stop_distance,
                atr=account.atr,
                risk_pct=cfg.risk_per_trade_pct,
                peak_equity=account.peak_equity,
                compounding_enabled=DEFAULT_AI_SCALPING_CONFIG.compounding_enabled,
                config=DEFAULT_AI_SCALPING_CONFIG,
            )
            if sized.valid:
                approved_lots = sized.lots
            else:
                risk_allowed = False
                risk_reasons.append(sized.reason)
                approved_lots = Decimal("0")

            min_entry_distance: Decimal | None = None
            if account.atr is not None and account.atr > 0:
                min_entry_distance = (account.atr * Decimal("0.15")).quantize(
                    Decimal("0.00001")
                )
            elif stop_distance is not None and stop_distance > 0:
                min_entry_distance = stop_distance
            # Incomplete open-book facts must never allow add-ons (fail closed).
            if (
                account.open_positions > 0
                and not account.open_directions
                and not account.open_entries
            ):
                risk_allowed = False
                risk_reasons.append("open_book_facts_incomplete — blocking add-on")
                approved_lots = Decimal("0")

            add = may_add_scalping_trade(
                open_positions=account.open_positions,
                max_open=cfg.max_open_trades,
                new_confidence=confluence.confidence,
                best_open_confidence=account.best_open_confidence,
                new_direction=confluence.direction.value,
                open_directions=account.open_directions,
                entry=entry,
                open_entries=account.open_entries,
                min_entry_distance=min_entry_distance,
                require_improvement=DEFAULT_AI_SCALPING_CONFIG.require_probability_improvement
                and account.open_positions > 0,
                min_confidence_delta=DEFAULT_AI_SCALPING_CONFIG.min_confidence_delta_for_add,
            )
            if not add.allow:
                risk_allowed = False
                risk_reasons.append(add.reason)
                approved_lots = Decimal("0")

            # Institutional quality gates — never bypass risk; block weak setups
            if ai_score is not None and ai_score.reject:
                risk_allowed = False
                risk_reasons.append(
                    f"ai_scalping_quality_reject:{ai_score.reject_reason or 'gates'}"
                )
                approved_lots = Decimal("0")

            # Portfolio-wide exposure + daily loss (all symbols combined)
            if DEFAULT_AI_SCALPING_CONFIG.multi_asset_scan_enabled:
                try:
                    from app.domain.institutional_trading.ai_scalping.portfolio_risk import (  # noqa: E501
                        aggregate_portfolio_risk,
                    )
                    from app.domain.institutional_trading.ai_scalping.portfolio_scanner import (  # noqa: E501
                        check_portfolio_limits,
                    )

                    risk_snap = aggregate_portfolio_risk(
                        account,
                        config=DEFAULT_AI_SCALPING_CONFIG,
                        ite_config=cfg,
                    )
                    blocked, block_why = check_portfolio_limits(
                        open_positions=risk_snap.open_positions,
                        max_open_positions=risk_snap.max_open_positions,
                        daily_loss_pct=risk_snap.daily_loss_pct,
                        max_daily_loss_pct=risk_snap.max_daily_loss_pct,
                        exposure_pct=risk_snap.exposure_pct,
                        max_exposure_pct=risk_snap.max_exposure_pct,
                    )
                    if blocked:
                        risk_allowed = False
                        risk_reasons.append(
                            f"portfolio_risk_block:{block_why or 'limits'}"
                        )
                        approved_lots = Decimal("0")
                except Exception:
                    logger.exception("portfolio_risk_check_failed")
                    risk_allowed = False
                    risk_reasons.append("portfolio_risk_check_failed")
                    approved_lots = Decimal("0")

        eligibility = PositionEligibilityEngine(config=cfg).evaluate(
            snapshot=snapshot,
            confluence=confluence,
            account=account,
            risk_allowed=risk_allowed,
            risk_reasons=tuple(risk_reasons),
        )

        return TradeDecisionEngine(config=cfg).decide(
            snapshot=snapshot,
            confluence=confluence,
            eligibility=eligibility,
            account=account,
            risk_score=assessment.risk_score,
            risk_reasons=tuple(risk_reasons),
            approved_lots=approved_lots if risk_allowed else Decimal("0"),
        )
