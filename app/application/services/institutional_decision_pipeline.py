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
    DecisionAction,
    EligibilityResult,
    PriceZone,
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


def oms_risk_config_from_ite(cfg: ITEConfig | None = None) -> RiskEngineConfig:
    """OMS defensive daily-loss recheck — same ITE policy, not a parallel cap.

    Other OMS RiskEngine defaults (max open positions, weekly/monthly, spread)
    stay unchanged so this does not remap max_open_trades onto OMS.
    """
    ite = cfg if cfg is not None else DEFAULT_ITE_CONFIG
    return RiskEngineConfig(max_daily_loss_pct=ite.max_daily_loss_pct)


def oms_risk_engine_from_ite(cfg: ITEConfig | None = None) -> RiskEngine:
    """OMS RiskEngine that consumes the ITE daily-loss source of truth."""
    return RiskEngine(config=oms_risk_config_from_ite(cfg))


def risk_config_from_ite(
    cfg: ITEConfig,
    *,
    min_lot: Decimal | None = None,
    lot_step: Decimal | None = None,
    max_lot: Decimal | None = None,
    contract_size: Decimal | None = None,
) -> RiskEngineConfig:
    """Map ITE defaults onto RiskEngineConfig (live broker specs when provided)."""
    from app.domain.institutional_trading.config import (
        MAX_PLANNED_SL_RISK_USD,
        MAX_TOTAL_PLANNED_RISK_USD,
        MIN_PLANNED_RISK_USD,
        TARGET_PLANNED_RISK_USD,
    )
    from app.domain.trading.xauusd_specs import (
        CONTRACT_SIZE,
        VOLUME_MAX,
        VOLUME_MIN,
        VOLUME_STEP,
    )

    target_usd = getattr(cfg, "target_risk_per_trade_usd", TARGET_PLANNED_RISK_USD)
    min_usd = getattr(cfg, "min_planned_risk_usd", MIN_PLANNED_RISK_USD)
    max_usd = getattr(cfg, "max_planned_sl_risk_usd", MAX_PLANNED_SL_RISK_USD)
    agg_usd = getattr(cfg, "max_total_planned_risk_usd", MAX_TOTAL_PLANNED_RISK_USD)
    return RiskEngineConfig(
        max_risk_per_trade_pct=cfg.risk_per_trade_pct,
        min_planned_risk_usd=(
            min_usd if min_usd and min_usd > 0 else MIN_PLANNED_RISK_USD
        ),
        target_risk_per_trade_usd=(
            target_usd if target_usd and target_usd > 0 else TARGET_PLANNED_RISK_USD
        ),
        max_planned_sl_risk_usd=(
            max_usd if max_usd and max_usd > 0 else MAX_PLANNED_SL_RISK_USD
        ),
        max_total_planned_risk_usd=(
            agg_usd if agg_usd and agg_usd > 0 else MAX_TOTAL_PLANNED_RISK_USD
        ),
        max_daily_loss_pct=cfg.max_daily_loss_pct,
        max_weekly_loss_pct=cfg.max_weekly_drawdown_pct,
        max_open_positions=cfg.max_open_trades,
        max_consecutive_losses=cfg.max_consecutive_losses,
        max_spread=cfg.max_spread_reject,
        min_lot=min_lot if min_lot is not None and min_lot > 0 else VOLUME_MIN,
        lot_step=lot_step if lot_step is not None and lot_step > 0 else VOLUME_STEP,
        max_lot=max_lot if max_lot is not None and max_lot > 0 else VOLUME_MAX,
        contract_size=contract_size if contract_size is not None else CONTRACT_SIZE,
        max_atr_pct_of_price=Decimal("3.0"),
        enforce_session=True,
        enforce_spread=True,
        enforce_atr=True,
    )


def _positive_spec(value: object) -> Decimal | None:
    try:
        if value is None or value == "":
            return None
        parsed = Decimal(str(value))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return parsed if parsed.is_finite() and parsed > 0 else None


def _live_broker_lot_specs(
    symbol: str,
) -> tuple[Decimal, Decimal, Decimal, Decimal, Decimal | None, Decimal | None]:
    """Live volume/CS/ticks. Never fall back to gold specs for FX/index."""
    from app.domain.entities.risk_engine import contract_size_for_symbol

    min_lot = Decimal("0.01")
    lot_step = Decimal("0.01")
    max_lot = Decimal("100")
    # Unknown instruments (AEXEUR, …) stay 0 until live CS is read.
    contract_size = contract_size_for_symbol(symbol, default=Decimal("0"))
    tick_size: Decimal | None = None
    tick_value: Decimal | None = None
    try:
        from core.di.container import get_container

        adapter = getattr(get_container(), "mt5_adapter", None)
        client = None
        if adapter is not None:
            client = getattr(adapter, "client", None) or getattr(
                adapter, "_client", None
            )
        candidates = [symbol]
        try:
            from app.domain.trading.gold_only import (
                canonical_gold_execution_symbol,
                is_gold_symbol,
            )

            if is_gold_symbol(symbol):
                canon = canonical_gold_execution_symbol(symbol)
                if canon and canon not in candidates:
                    candidates.append(canon)
        except Exception:
            logger.debug(
                "live_broker_gold_symbol_candidates_failed",
                symbol=symbol,
                exc_info=True,
            )
        if client is not None and hasattr(client, "symbol_info"):
            for candidate in candidates:
                info = client.symbol_info(candidate)
                if info is None:
                    continue
                vmin = _positive_spec(getattr(info, "volume_min", None))
                vstep = _positive_spec(getattr(info, "volume_step", None))
                vmax = _positive_spec(getattr(info, "volume_max", None))
                cs = _positive_spec(getattr(info, "contract_size", None))
                if vmin is not None:
                    min_lot = vmin
                if vstep is not None:
                    lot_step = vstep
                if vmax is not None:
                    max_lot = vmax
                # Malformed live CS must fail closed — do not substitute gold/FX.
                contract_size = cs if cs is not None else Decimal("0")
                raw_ts = getattr(info, "trade_tick_size", None) or getattr(
                    info, "tick_size", None
                )
                raw_tv = getattr(info, "trade_tick_value", None) or getattr(
                    info, "tick_value", None
                )
                tick_size = _positive_spec(raw_ts)
                tick_value = _positive_spec(raw_tv)
                _ = getattr(info, "stops_level", None)
                _ = getattr(info, "freeze_level", None)
                break
    except Exception:
        logger.debug("live_broker_lot_specs_unavailable", symbol=symbol, exc_info=True)
    return min_lot, lot_step, max_lot, contract_size, tick_size, tick_value


def _price_zone(level: Decimal) -> PriceZone:
    return PriceZone(low=level, high=level, mid=level)


def _align_decision_to_structural_targets(
    decision: TradeDecision,
    *,
    ai_score: dict[str, Any] | None,
    stop_distance: Decimal | None,
    approved_lots: Decimal,
    actual_sl_risk: Decimal | None,
    live_min: Decimal,
    live_step: Decimal,
    live_max: Decimal,
    live_cs: Decimal,
    live_tick: Decimal | None,
    live_tick_val: Decimal | None,
) -> TradeDecision:
    """Use the same structural SL/TP that sized the lot. Never invent 2R geometry."""
    if (
        decision.action not in {DecisionAction.BUY, DecisionAction.SELL}
        or approved_lots <= 0
    ):
        return decision
    score = ai_score if isinstance(ai_score, dict) else {}
    entry = None
    sl = None
    tp = None
    try:
        if score.get("entry"):
            entry = Decimal(str(score.get("entry")))
        if score.get("stop_loss"):
            sl = Decimal(str(score.get("stop_loss")))
        if score.get("take_profit"):
            tp = Decimal(str(score.get("take_profit")))
    except (TypeError, ValueError, ArithmeticError):
        entry, sl, tp = None, None, None
    if entry is None or entry <= 0:
        mid = getattr(decision.entry_zone, "mid", None) if decision.entry_zone else None
        entry = mid if mid is not None and mid > 0 else None
    if (
        sl is None
        and entry is not None
        and stop_distance is not None
        and stop_distance > 0
    ):
        if decision.action is DecisionAction.BUY:
            sl = entry - stop_distance
        else:
            sl = entry + stop_distance
    if entry is None or sl is None or tp is None:
        if decision.estimated_rr is not None and decision.estimated_rr <= Decimal("1"):
            reasons = [
                *decision.risk_reasons,
                "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS: "
                f"planned RR {decision.estimated_rr} does not exceed 1.0",
            ]
            return replace(
                decision,
                action=DecisionAction.NO_TRADE,
                approved_lots=Decimal("0"),
                risk_reasons=tuple(reasons),
                reasons=tuple(dict.fromkeys([*decision.reasons, *reasons])),
            )
        return decision
    sl_dist = abs(entry - sl)
    tp_dist = abs(tp - entry)
    if sl_dist <= 0 or tp_dist <= sl_dist:
        reasons = [
            *decision.risk_reasons,
            "TP_PROFIT_NOT_GREATER_THAN_SL_LOSS: "
            f"planned TP {tp_dist} <= planned SL {sl_dist}",
        ]
        return replace(
            decision,
            action=DecisionAction.NO_TRADE,
            approved_lots=Decimal("0"),
            risk_reasons=tuple(reasons),
            reasons=tuple(dict.fromkeys([*decision.reasons, *reasons])),
        )
    rr = (tp_dist / sl_dist).quantize(Decimal("0.01"))
    tp_profit = None
    if actual_sl_risk is not None and actual_sl_risk > 0:
        tp_profit = (actual_sl_risk * rr).quantize(Decimal("0.01"))
    if isinstance(score, dict):
        score["final_volume"] = str(approved_lots)
        score["planned_initial_sl_risk_usd"] = (
            str(actual_sl_risk) if actual_sl_risk is not None else None
        )
        score["planned_initial_tp_profit_usd"] = (
            str(tp_profit) if tp_profit is not None else None
        )
        score["risk_reward_ratio"] = str(rr)
        score["initial_stop"] = str(sl)
        score["initial_volume"] = str(approved_lots)
        score["execution_ticket"] = None
        logger.info(
            "signal_sizing_audit",
            symbol=decision.symbol,
            side=decision.action.value,
            entry=str(entry),
            initial_stop=str(sl),
            initial_tp=str(tp),
            stop_distance=str(sl_dist),
            tick_size=str(live_tick) if live_tick is not None else None,
            tick_value=str(live_tick_val) if live_tick_val is not None else None,
            contract_size=str(live_cs),
            volume_min=str(live_min),
            volume_step=str(live_step),
            volume_max=str(live_max),
            final_volume=str(approved_lots),
            planned_initial_sl_risk_usd=(
                str(actual_sl_risk) if actual_sl_risk is not None else None
            ),
            planned_initial_tp_profit_usd=(
                str(tp_profit) if tp_profit is not None else None
            ),
            risk_reward_ratio=str(rr),
            opportunity_score=score.get("opportunity_score"),
        )
    return replace(
        decision,
        stop_zone=_price_zone(sl),
        target_zone=_price_zone(tp),
        estimated_rr=rr,
        approved_lots=approved_lots,
    )


def _resolve_live_positions(
    positions: list[MT5Position] | None,
) -> list[MT5Position]:
    """Prefer caller-supplied positions; else read live MT5 book (fail soft)."""
    if positions:
        return list(positions)
    try:
        from core.di.container import get_container

        adapter = getattr(get_container(), "mt5_adapter", None)
        if adapter is None or not hasattr(adapter, "list_positions"):
            return []
        rows = adapter.list_positions() or []
        out: list[MT5Position] = []
        for p in rows:
            if isinstance(p, MT5Position):
                out.append(p)
                continue
            try:
                raw_initial_vol = getattr(p, "initial_volume", None)
                out.append(
                    MT5Position(
                        ticket=int(getattr(p, "ticket", 0) or 0),
                        symbol=str(getattr(p, "symbol", "") or ""),
                        side=str(getattr(p, "side", "buy") or "buy"),
                        volume=Decimal(str(getattr(p, "volume", 0) or 0)),
                        open_price=Decimal(str(getattr(p, "open_price", 0) or 0)),
                        current_price=Decimal(str(getattr(p, "current_price", 0) or 0)),
                        profit=Decimal(str(getattr(p, "profit", 0) or 0)),
                        magic=int(getattr(p, "magic", 0) or 0),
                        comment=str(getattr(p, "comment", "") or ""),
                        initial_stop=Decimal(str(getattr(p, "initial_stop", 0) or 0)),
                        initial_volume=(
                            Decimal(str(raw_initial_vol))
                            if raw_initial_vol not in (None, "", 0, "0")
                            else None
                        ),
                    )
                )
            except Exception:
                logger.debug("resolve_live_position_row_skipped", exc_info=True)
                continue
        return out
    except Exception:
        logger.debug("resolve_live_positions_failed", exc_info=True)
        return []


def _account_leverage_int(leverage: object) -> int | None:
    """Live MT5 leverage only. Never invent 1:100 gold retail leverage."""
    try:
        if leverage is None or leverage == "":
            return None
        parsed = int(Decimal(str(leverage)))
    except (TypeError, ValueError, ArithmeticError):
        return None
    return parsed if parsed >= 1 else None


def _account_snapshot(
    *,
    equity: Decimal,
    free_margin: Decimal | None,
    leverage: object = None,
) -> AccountSnapshot:
    fm = free_margin if free_margin is not None else equity
    live = _account_leverage_int(leverage)
    # Missing account leverage: RiskEngineConfig.exposure_leverage (1000).
    # Never the previous hardcoded 100 that treated FX notional as 20x too large.
    lev = live if live is not None else int(RiskEngineConfig().exposure_leverage)
    return AccountSnapshot(
        login=1,
        balance=equity,
        equity=equity,
        margin=Decimal("0"),
        free_margin=fm,
        margin_level=Decimal("0"),
        profit=Decimal("0"),
        leverage=lev,
        currency="USD",
        server="ite",
    )


@dataclass
class InstitutionalDecisionPipeline:
    """Phase B pipeline: confluence → risk → eligibility → trade decision."""

    config: ITEConfig = field(default_factory=lambda: DEFAULT_ITE_CONFIG)
    risk_engine: RiskEngine | None = None
    user_id: UUID = field(default_factory=uuid4)
    _last_ai_score: dict[str, Any] | None = field(default=None, repr=False)
    _last_feasibility: dict[str, Any] | None = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self.risk_engine is None:
            self.risk_engine = RiskEngine(config=risk_config_from_ite(self.config))

    def last_ai_score(self) -> dict[str, Any] | None:
        return dict(self._last_ai_score) if self._last_ai_score else None

    def last_min_lot_feasibility(self) -> dict[str, Any] | None:
        return dict(self._last_feasibility) if self._last_feasibility else None

    def evaluate_min_lot_feasibility_gate(
        self,
        *,
        stop_distance: Any,
        equity: Any,
        min_lot: Any,
        contract_size: Any,
        lot_step: Any = None,
        max_lot: Any = None,
    ) -> Any:
        """Audit-only pre-Risk gate. Does not change stop / lot / 5% cap."""
        from app.domain.institutional_trading.operations.min_lot_feasibility import (
            evaluate_setup_tradeability,
        )

        trade = evaluate_setup_tradeability(
            stop_distance=stop_distance,
            equity=equity,
            min_lot=min_lot,
            lot_step=lot_step,
            max_lot=max_lot,
            contract_size=contract_size,
        )
        result = trade.feasibility
        payload = result.to_dict()
        payload.update(trade.to_observability())
        self._last_feasibility = payload
        if isinstance(self._last_ai_score, dict):
            self._last_ai_score["min_lot_feasibility"] = payload
            self._last_ai_score.update(trade.to_observability())
        try:
            from app.application.services.strategy_performance_telemetry import (
                get_strategy_performance_telemetry,
            )

            get_strategy_performance_telemetry().note_feasibility(
                infeasible=result.infeasible,
                skip_expensive_downstream=result.skip_expensive_downstream,
            )
        except Exception:
            logger.exception("min_lot_feasibility_telemetry_failed")
        if result.infeasible:
            logger.warning(
                "min_lot_infeasible_early",
                classification=result.classification,
                tradeability=trade.tradeability,
                tradeability_reason=trade.tradeability_reason,
                stop_distance=str(result.stop_distance),
                max_allowed_stop=str(result.max_allowed_stop),
                needed_pct=str(result.needed_pct),
                equity=str(result.equity),
                skip_expensive_downstream=True,
                risk_engine_authoritative=True,
            )
        return result

    def _prepare_config(
        self,
        account: AccountRiskState,
        *,
        symbol: str | None = None,
    ) -> ITEConfig:
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
            symbol=symbol,
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
        sym = str(getattr(snapshot, "symbol", "") or "")
        cfg = self._prepare_config(account, symbol=sym or None)
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
                    opens=tuple(getattr(snapshot, "entry_opens", ()) or ()),
                    highs=tuple(getattr(snapshot, "entry_highs", ()) or ()),
                    lows=tuple(getattr(snapshot, "entry_lows", ()) or ()),
                    closes=tuple(getattr(snapshot, "entry_closes", ()) or ()),
                    bid=getattr(account, "bid", None),
                    ask=getattr(account, "ask", None),
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
        stop_atr = getattr(snapshot, "entry_atr", None) or account.atr
        if stop_atr is None or stop_atr <= 0:
            stop_atr = account.atr
        atr_stop = stop_atr * stop_mult if stop_atr else None
        stop_distance = atr_stop
        stop_source = "atr_fallback" if atr_stop is not None else "none"
        entry = account.mid_price
        ai_stop_distance = None
        if ai_score is not None and self._last_ai_score:
            raw_sd = self._last_ai_score.get("stop_loss")
            entry_s = self._last_ai_score.get("entry")
            try:
                if raw_sd and entry_s:
                    from decimal import Decimal as _D

                    sd = abs(_D(str(entry_s)) - _D(str(raw_sd)))
                    if sd > 0:
                        ai_stop_distance = sd
            except Exception:
                ai_stop_distance = None
        # Structure-first (existing scalp selector). Never clamp SL to
        # max_allowed_stop_at_min_lot to manufacture eligibility.
        if (
            exe.direction in {TradeDirection.BUY, TradeDirection.SELL}
            and entry is not None
            and entry > 0
        ):
            try:
                from app.domain.institutional_trading.ai_scalping import (
                    structure_targets as st_mod,
                )

                chosen, source = st_mod.choose_strategy_stop_distance(
                    snapshot,
                    direction=exe.direction,
                    entry=entry,
                    atr=stop_atr,
                    stop_atr_mult=stop_mult,
                    ai_stop_distance=ai_stop_distance,
                )
                if chosen is not None and chosen > 0:
                    if source == "atr_cap":
                        logger.warning(
                            "ai_structure_stop_capped_to_atr",
                            file=(
                                "app/application/services/"
                                "institutional_decision_pipeline.py"
                            ),
                            function="InstitutionalDecisionPipeline.decide",
                            symbol=str(snapshot.symbol),
                            ai_stop_distance=(
                                str(ai_stop_distance)
                                if ai_stop_distance is not None
                                else None
                            ),
                            atr_stop=str(atr_stop),
                            chosen_stop=str(chosen),
                            stop_source=source,
                            condition="structure_or_ai_stop > atr * stop_mult",
                        )
                    stop_distance = chosen
                    stop_source = source
            except Exception:  # noqa: S110  # best-effort optional path
                pass
        if isinstance(self._last_ai_score, dict):
            self._last_ai_score["stop_distance"] = (
                str(stop_distance) if stop_distance is not None else None
            )
            self._last_ai_score["stop_source"] = stop_source
        logger.info(
            "risk_sizing_stop_distance",
            symbol=str(snapshot.symbol),
            side=side,
            stop_distance=str(stop_distance) if stop_distance is not None else None,
            stop_source=stop_source,
            atr=str(account.atr) if account.atr is not None else None,
            stop_atr=str(stop_atr) if stop_atr is not None else None,
            atr_stop=str(atr_stop) if atr_stop is not None else None,
        )
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

        from app.domain.institutional_trading.operations.quantforg_position_cap import (
            filter_quantforg_positions,
        )

        live_book = _resolve_live_positions(positions)
        pos_list = filter_quantforg_positions(
            live_book, symbol=str(getattr(snapshot, "symbol", "") or "")
        )
        pos_all = filter_quantforg_positions(live_book)
        live_positions = pos_list

        assert self.risk_engine is not None
        # Keep risk engine limits in sync with adaptive / scalping + live broker specs.
        live_min, live_step, live_max, live_cs, live_tick, live_tick_val = (
            _live_broker_lot_specs(snapshot.symbol)
        )
        feasibility = self.evaluate_min_lot_feasibility_gate(
            stop_distance=stop_distance,
            equity=account.equity,
            min_lot=live_min,
            lot_step=live_step,
            max_lot=live_max,
            contract_size=live_cs,
        )
        if feasibility.skip_expensive_downstream:
            # Early reject only — stop / lot / 5% cap unchanged. Risk would
            # also reject MIN_LOT_CONSTRAINT; skip overlay + Risk evaluate.
            risk_reasons = list(feasibility.risk_reasons)
            eligibility = PositionEligibilityEngine(config=cfg).evaluate(
                snapshot=snapshot,
                confluence=confluence,
                account=account,
                risk_allowed=False,
                risk_reasons=tuple(risk_reasons),
            )
            return TradeDecisionEngine(config=cfg).decide(
                snapshot=snapshot,
                confluence=confluence,
                eligibility=eligibility,
                account=account,
                risk_score=100,
                risk_reasons=tuple(risk_reasons),
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
            contract_size=live_cs,
            tick_size=live_tick,
            tick_value=live_tick_val,
        )
        risk_engine_lots_cap = Decimal("0")
        self.risk_engine = RiskEngine(
            config=risk_config_from_ite(
                cfg,
                min_lot=live_min,
                lot_step=live_step,
                max_lot=live_max,
                contract_size=live_cs,
            )
        )
        assessment = self.risk_engine.evaluate(
            check,
            account=_account_snapshot(
                equity=account.equity,
                free_margin=account.free_margin,
                leverage=account.leverage,
            ),
            positions=pos_all,
            peak_equity=account.peak_equity or account.equity,
            daily_pnl=account.daily_pnl,
            weekly_pnl=account.weekly_pnl,
        )

        risk_allowed = assessment.decision is not RiskDecision.REJECT
        risk_reasons = list(assessment.reasons)
        approved_lots = assessment.approved_lots if risk_allowed else Decimal("0")
        if risk_allowed and approved_lots > 0:
            risk_engine_lots_cap = approved_lots

        # Broker-aware scalping lot overlay (never invent fixed lots)
        if cfg.is_scalping() and risk_allowed:
            from dataclasses import replace as dc_replace

            from app.domain.institutional_trading.ai_scalping.config import (
                DEFAULT_AI_SCALPING_CONFIG,
            )
            from app.domain.institutional_trading.ai_scalping.duplicate_guard import (
                may_add_scalping_trade,
            )
            from app.domain.institutional_trading.ai_scalping.dynamic_sizing_v2 import (
                calculate_dynamic_lots_v2,
                check_portfolio_sizing_limits,
            )
            from app.domain.institutional_trading.ai_scalping.session_intelligence import (  # noqa: E501
                assess_session,
            )
            from app.domain.institutional_trading.ai_scalping.sizing import (
                calculate_scalping_lots,
            )

            scalp_cfg = dc_replace(
                DEFAULT_AI_SCALPING_CONFIG,
                broker_min_lot=live_min,
                broker_lot_step=live_step,
                broker_max_lot=min(live_max, DEFAULT_AI_SCALPING_CONFIG.broker_max_lot)
                if live_max > 0
                else DEFAULT_AI_SCALPING_CONFIG.broker_max_lot,
            )
            ai_payload = (
                self._last_ai_score if isinstance(self._last_ai_score, dict) else {}
            )
            opportunity_score = None
            try:
                if ai_payload.get("opportunity_score") is not None:
                    opportunity_score = int(ai_payload.get("opportunity_score"))
            except (TypeError, ValueError):
                opportunity_score = None
            sniper_blob = ai_payload.get("sniper_entry") or ai_payload.get("sniper")
            sniper_passed = bool(
                isinstance(sniper_blob, dict) and sniper_blob.get("passed")
            )
            session_assess = assess_session(
                str(
                    getattr(
                        snapshot.session.session,
                        "value",
                        snapshot.session.session,
                    )
                ),
                config=scalp_cfg,
            )
            # Prefer filter risk_multiplier when present (same soft policy)
            sess_risk = getattr(snapshot.session, "risk_multiplier", None)
            if sess_risk is None or sess_risk <= 0:
                sess_risk = session_assess.risk_multiplier

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

            # Institutional quality gates — never bypass risk; block weak setups
            if ai_score is not None and ai_score.reject:
                risk_allowed = False
                risk_reasons.append(
                    f"ai_scalping_quality_reject:{ai_score.reject_reason or 'gates'}"
                )
                approved_lots = Decimal("0")

            if risk_allowed and scalp_cfg.portfolio_risk_engine_v2_enabled:
                from app.domain.institutional_trading.ai_scalping.portfolio_risk_engine_v2 import (  # noqa: E501
                    BrokerComplianceSpec,
                    evaluate_portfolio_allocation,
                )

                broker_spec = BrokerComplianceSpec(
                    min_lot=live_min,
                    lot_step=live_step,
                    max_lot=min(live_max, scalp_cfg.broker_max_lot),
                    contract_size=live_cs,
                )
                # Fail closed: open book without position rows cannot validate
                # winner-only pyramiding / symbol exposure accurately.
                if account.open_positions > 0 and not live_positions:
                    risk_allowed = False
                    risk_reasons.append(
                        "open_positions_without_book — PRE v2 fail-closed"
                    )
                    approved_lots = Decimal("0")
                else:
                    alloc = evaluate_portfolio_allocation(
                        account=account,
                        symbol=str(getattr(snapshot, "symbol", "") or ""),
                        stop_distance=stop_distance,
                        positions=live_positions,
                        new_direction=confluence.direction.value,
                        new_confidence=confluence.confidence,
                        entry=entry,
                        atr=account.atr,
                        mid_price=account.mid_price,
                        leverage=account.leverage,
                        risk_pct=cfg.risk_per_trade_pct,
                        session_risk_multiplier=sess_risk,
                        quality_score=(
                            int(ai_score.trade_quality)
                            if ai_score is not None
                            else None
                        ),
                        confidence=(
                            int(ai_score.confidence) if ai_score is not None else None
                        ),
                        liquidity_score=(
                            int(ai_score.liquidity) if ai_score is not None else None
                        ),
                        spread_score=(
                            int(ai_score.spread_score) if ai_score is not None else None
                        ),
                        trend_confidence=(
                            int(ai_score.confidence) if ai_score is not None else None
                        ),
                        quality_reject=(
                            bool(ai_score.reject) if ai_score is not None else False
                        ),
                        opportunity_score=opportunity_score,
                        sniper_passed=sniper_passed,
                        broker=broker_spec,
                        balance=account.balance,
                        used_margin=account.used_margin,
                        floating_pnl=account.floating_pnl,
                        best_open_confidence=account.best_open_confidence,
                        open_directions=account.open_directions,
                        open_entries=account.open_entries,
                        min_entry_distance=min_entry_distance,
                        require_probability_improvement=(
                            scalp_cfg.require_probability_improvement
                            and account.open_positions > 0
                        ),
                        config=scalp_cfg,
                        ite_config=cfg,
                    )
                    self._last_ai_score = self._last_ai_score or {}
                    if isinstance(self._last_ai_score, dict):
                        self._last_ai_score["portfolio_risk_v2"] = alloc.to_dict()
                    # Phase B — incremental portfolio risk visibility (observe only)
                    try:
                        from app.domain.institutional_trading.phase_b import (
                            get_phase_b_plane,
                        )

                        book = alloc.book
                        existing = tuple(
                            str(getattr(p, "symbol", "") or "")
                            for p in (live_positions or ())
                        )
                        get_phase_b_plane().observe_incremental_risk(
                            current_open_risk=float(book.exposure_pct)
                            if book.exposure_pct is not None
                            else None,
                            new_trade_risk=float(cfg.risk_per_trade_pct)
                            if cfg.risk_per_trade_pct is not None
                            else None,
                            max_portfolio_risk=float(
                                getattr(scalp_cfg, "max_daily_exposure_pct", 0) or 0
                            )
                            or None,
                            correlation_score=float(alloc.correlation_score)
                            if alloc.correlation_score is not None
                            else None,
                            symbol=str(getattr(snapshot, "symbol", "") or ""),
                            symbol_exposure=float(alloc.symbol_exposure_pct)
                            if alloc.symbol_exposure_pct is not None
                            else None,
                            directional_exposure=float(
                                alloc.correlated_exposure_pct
                            )
                            if alloc.correlated_exposure_pct is not None
                            else None,
                            existing_symbols=existing,
                            hard_blocked=not bool(alloc.allow),
                            hard_block_reason=alloc.rejection_reason,
                        )
                        raw_reg = None
                        if ai_score is not None:
                            raw_reg = getattr(ai_score, "market_regime", None) or getattr(
                                ai_score, "regime", None
                            )
                        if raw_reg:
                            get_phase_b_plane().observe_regime(str(raw_reg))
                    except Exception:
                        pass
                    if alloc.allow:
                        # Never exceed RiskEngine REDUCE_SIZE / caps — take stricter
                        pre_lots = alloc.approved_lots
                        if risk_engine_lots_cap > 0:
                            approved_lots = min(pre_lots, risk_engine_lots_cap)
                            if approved_lots < pre_lots:
                                risk_reasons.append(
                                    "risk_engine_lot_cap:"
                                    f"pre={pre_lots},cap={risk_engine_lots_cap}"
                                )
                        else:
                            approved_lots = pre_lots
                    else:
                        risk_allowed = False
                        risk_reasons.append(
                            alloc.rejection_reason or "portfolio_risk_engine_v2_reject"
                        )
                        approved_lots = Decimal("0")
                        method = (
                            alloc.sizing.method
                            if alloc.sizing is not None
                            else "portfolio_reject"
                        )
                        if "below_min_lot" in method or (
                            alloc.rejection_reason
                            and "below_min_lot" in alloc.rejection_reason
                        ):
                            sized = (
                                alloc.sizing.to_lot_result()
                                if alloc.sizing is not None
                                else None
                            )
                            if sized is not None:
                                risk_reasons.append(
                                    "below_min_lot:"
                                    f"calculated_lot={sized.calculated_lot},"
                                    f"broker_minimum={sized.broker_min_lot},"
                                    f"account_balance={sized.account_balance},"
                                    f"risk_percentage={sized.risk_percentage}"
                                )
                            try:
                                from app.application.services.cycle_evidence import (
                                    log_trade_rejection,
                                )

                                log_trade_rejection(
                                    reasons=(alloc.rejection_reason or method,),
                                    stage="lot_sizing",
                                    code="below_min_lot",
                                    symbol=str(getattr(snapshot, "symbol", "") or ""),
                                    session=str(
                                        getattr(
                                            snapshot.session.session,
                                            "value",
                                            snapshot.session.session,
                                        )
                                    ),
                                    sizing=alloc.to_dict(),
                                )
                            except Exception:
                                logger.exception("below_min_lot_reject_log_failed")
            elif risk_allowed:
                # Legacy / sizing-v2-only path (PRE v2 disabled)
                portfolio_exp = Decimal("0")
                symbol_exp = Decimal("0")
                correlated_exp = Decimal("0")
                try:
                    from app.domain.institutional_trading.ai_scalping.portfolio_risk import (  # noqa: E501
                        aggregate_portfolio_risk,
                        portfolio_exposure_pct,
                    )

                    risk_snap_pre = aggregate_portfolio_risk(
                        account,
                        config=scalp_cfg,
                        ite_config=cfg,
                    )
                    portfolio_exp = risk_snap_pre.exposure_pct
                    sym = str(getattr(snapshot, "symbol", "") or "")
                    same_sym = sum(
                        1
                        for p in (positions or [])
                        if str(getattr(p, "symbol", "") or "").upper() == sym.upper()
                    )
                    symbol_exp = portfolio_exposure_pct(
                        open_positions=same_sym,
                        risk_per_trade_pct=scalp_cfg.risk_per_trade_pct,
                    )
                    try:
                        from app.domain.institutional_trading.ai_scalping.correlation_book import (  # noqa: E501
                            correlation_group_members,
                            normalize_book_symbol,
                        )

                        members = correlation_group_members(sym)
                        if members:
                            group_u = {normalize_book_symbol(g) for g in members}
                            corr_n = sum(
                                1
                                for p in (positions or [])
                                if normalize_book_symbol(
                                    str(getattr(p, "symbol", "") or "")
                                )
                                in group_u
                            )
                            correlated_exp = portfolio_exposure_pct(
                                open_positions=corr_n,
                                risk_per_trade_pct=scalp_cfg.risk_per_trade_pct,
                            )
                    except Exception:
                        correlated_exp = Decimal("0")
                except Exception:
                    logger.exception("dynamic_sizing_v2_exposure_precheck_failed")

                previous_lot: Decimal | None = None
                real_positions = list(positions or [])
                if real_positions:
                    vols = [
                        Decimal(str(getattr(p, "volume", 0) or 0))
                        for p in real_positions
                        if str(getattr(p, "symbol", "") or "").upper()
                        == str(getattr(snapshot, "symbol", "") or "").upper()
                    ]
                    vols = [v for v in vols if v > 0]
                    if vols:
                        previous_lot = max(vols)

                peak_dd = Decimal("0")
                peak = account.peak_equity
                if peak is not None and peak > 0 and account.equity < peak:
                    peak_dd = (peak - account.equity) / peak * Decimal("100")

                if scalp_cfg.dynamic_sizing_v2_enabled:
                    sized_v2 = calculate_dynamic_lots_v2(
                        equity=account.equity,
                        balance=account.balance or account.equity,
                        free_margin=account.free_margin,
                        stop_distance=stop_distance,
                        atr=account.atr,
                        mid_price=account.mid_price,
                        risk_pct=cfg.risk_per_trade_pct,
                        contract_size=live_cs,
                        min_lot=live_min,
                        lot_step=live_step,
                        max_lot=live_max,
                        session_risk_multiplier=sess_risk,
                        daily_exposure_used_pct=portfolio_exp,
                        portfolio_exposure_pct=portfolio_exp,
                        symbol_open_risk_pct=symbol_exp,
                        daily_loss_pct=daily_dd,
                        max_daily_loss_pct=cfg.max_daily_loss_pct,
                        current_drawdown_pct=peak_dd,
                        consecutive_losses=int(account.consecutive_losses or 0),
                        quality_score=(
                            int(ai_score.trade_quality)
                            if ai_score is not None
                            else None
                        ),
                        confidence=(
                            int(ai_score.confidence) if ai_score is not None else None
                        ),
                        liquidity_score=(
                            int(ai_score.liquidity) if ai_score is not None else None
                        ),
                        spread_score=(
                            int(ai_score.spread_score) if ai_score is not None else None
                        ),
                        trend_confidence=(
                            int(ai_score.confidence) if ai_score is not None else None
                        ),
                        quality_reject=(
                            bool(ai_score.reject) if ai_score is not None else False
                        ),
                        opportunity_score=opportunity_score,
                        sniper_passed=sniper_passed,
                        previous_final_lot=previous_lot,
                        max_margin_usage_pct=scalp_cfg.max_margin_usage_pct,
                        max_symbol_exposure_pct=scalp_cfg.max_symbol_exposure_pct,
                        lot_growth_max_step_pct=scalp_cfg.lot_growth_max_step_pct,
                        tick_size=live_tick,
                        tick_value=live_tick_val,
                        target_risk_usd=getattr(
                            scalp_cfg, "target_risk_per_trade_usd", None
                        ),
                        open_planned_risk_usd=self.risk_engine.aggregate_planned_sl_risk(
                            pos_all
                        )
                        if pos_all
                        else None,
                        max_total_planned_risk_usd=getattr(
                            scalp_cfg, "max_total_planned_risk_usd", None
                        ),
                        config=scalp_cfg,
                    )
                    sized = sized_v2.to_lot_result()
                    sizing_audit = sized_v2.to_dict()
                else:
                    sized = calculate_scalping_lots(
                        equity=account.equity,
                        stop_distance=stop_distance,
                        atr=account.atr,
                        risk_pct=cfg.risk_per_trade_pct,
                        peak_equity=account.peak_equity,
                        compounding_enabled=scalp_cfg.compounding_enabled,
                        contract_size=live_cs,
                        min_lot=live_min,
                        lot_step=live_step,
                        session_risk_multiplier=sess_risk,
                        daily_exposure_used_pct=portfolio_exp,
                        tick_size=live_tick,
                        tick_value=live_tick_val,
                        config=scalp_cfg,
                    )
                    sizing_audit = sized.to_dict()

                if sized.valid:
                    approved_lots = sized.lots
                else:
                    risk_allowed = False
                    risk_reasons.append(sized.reason)
                    if (
                        sized.method == "below_min_lot"
                        or "below_min_lot" in sized.method
                    ):
                        risk_reasons.append(
                            "below_min_lot:"
                            f"calculated_lot={sized.calculated_lot},"
                            f"broker_minimum={sized.broker_min_lot},"
                            f"account_balance={sized.account_balance},"
                            f"risk_percentage={sized.risk_percentage}"
                        )
                        try:
                            from app.application.services.cycle_evidence import (
                                log_trade_rejection,
                            )

                            log_trade_rejection(
                                reasons=(sized.reason,),
                                stage="lot_sizing",
                                code="below_min_lot",
                                symbol=str(getattr(snapshot, "symbol", "") or ""),
                                session=str(
                                    getattr(
                                        snapshot.session.session,
                                        "value",
                                        snapshot.session.session,
                                    )
                                ),
                                sizing=sizing_audit,
                            )
                        except Exception:
                            logger.exception("below_min_lot_reject_log_failed")
                    approved_lots = Decimal("0")

                profits: tuple = ()
                if account.floating_pnl is not None:
                    profits = (account.floating_pnl,)
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
                    require_improvement=(
                        scalp_cfg.require_probability_improvement
                        and account.open_positions > 0
                    ),
                    min_confidence_delta=scalp_cfg.min_confidence_delta_for_add,
                    require_unrealized_profit=account.open_positions > 0,
                    open_profits=profits,
                    same_direction_profits=profits,
                )
                if not add.allow:
                    risk_allowed = False
                    risk_reasons.append(add.reason)
                    approved_lots = Decimal("0")

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

                        blocked_v2, why_v2 = check_portfolio_sizing_limits(
                            open_positions=risk_snap.open_positions,
                            max_open_positions=risk_snap.max_open_positions,
                            daily_loss_pct=risk_snap.daily_loss_pct,
                            max_daily_loss_pct=risk_snap.max_daily_loss_pct,
                            exposure_pct=risk_snap.exposure_pct,
                            max_exposure_pct=risk_snap.max_exposure_pct,
                            margin_usage_pct=None,
                            max_margin_usage_pct=scalp_cfg.max_margin_usage_pct,
                            symbol_exposure_pct=symbol_exp,
                            max_symbol_exposure_pct=scalp_cfg.max_symbol_exposure_pct,
                            correlated_exposure_pct=correlated_exp,
                            max_correlated_exposure_pct=(
                                scalp_cfg.max_correlated_exposure_pct
                            ),
                        )
                        if blocked_v2:
                            risk_allowed = False
                            risk_reasons.append(
                                f"portfolio_sizing_v2_block:{why_v2 or 'limits'}"
                            )
                            approved_lots = Decimal("0")
                    except Exception:
                        logger.exception("portfolio_risk_check_failed")
                        risk_allowed = False
                        risk_reasons.append("portfolio_risk_check_failed")
                        approved_lots = Decimal("0")

        planned_sl_actual: Decimal | None = None
        if (
            risk_allowed
            and approved_lots > 0
            and stop_distance is not None
            and stop_distance > 0
        ):
            from app.domain.institutional_trading.config import (
                MAX_TOTAL_PLANNED_RISK_USD,
            )
            from app.domain.institutional_trading.operations.min_lot_feasibility import (  # noqa: E501
                actual_planned_sl_band_reason,
                format_planned_sl_reject_detail,
                lot_dollar_risk,
            )

            actual = lot_dollar_risk(
                approved_lots,
                stop_distance=stop_distance,
                contract_size=live_cs,
                tick_size=live_tick,
                tick_value=live_tick_val,
            )
            planned_sl_actual = actual
            open_planned = (
                self.risk_engine.aggregate_planned_sl_risk(pos_all)
                if pos_all
                else Decimal("0")
            )
            remaining_agg = MAX_TOTAL_PLANNED_RISK_USD - open_planned
            if remaining_agg < 0:
                remaining_agg = Decimal("0")
            band_reason = actual_planned_sl_band_reason(
                actual,
                remaining_portfolio_risk=remaining_agg,
            )
            if band_reason is not None:
                detail = format_planned_sl_reject_detail(
                    reason=band_reason,
                    symbol=str(getattr(snapshot, "symbol", "") or ""),
                    volume=approved_lots,
                    actual=actual,
                    stop_distance=stop_distance,
                    min_lot=live_min,
                    lot_step=live_step,
                    max_lot=live_max,
                )
                logger.info(
                    "planned_initial_sl_risk_rejected",
                    symbol=str(getattr(snapshot, "symbol", "") or ""),
                    calculated_volume=str(approved_lots),
                    actual_planned_initial_sl_risk=str(actual),
                    initial_sl_distance=str(stop_distance),
                    broker_volume_min=str(live_min),
                    broker_volume_step=str(live_step),
                    broker_volume_max=str(live_max),
                    rejection_reason=band_reason,
                )
                risk_allowed = False
                risk_reasons.append(detail)
                approved_lots = Decimal("0")

        eligibility = PositionEligibilityEngine(config=cfg).evaluate(
            snapshot=snapshot,
            confluence=confluence,
            account=account,
            risk_allowed=risk_allowed,
            risk_reasons=tuple(risk_reasons),
        )

        decision = TradeDecisionEngine(config=cfg).decide(
            snapshot=snapshot,
            confluence=confluence,
            eligibility=eligibility,
            account=account,
            risk_score=assessment.risk_score,
            risk_reasons=tuple(risk_reasons),
            approved_lots=approved_lots if risk_allowed else Decimal("0"),
        )
        return _align_decision_to_structural_targets(
            decision,
            ai_score=(
                self._last_ai_score
                if isinstance(self._last_ai_score, dict)
                else None
            ),
            stop_distance=stop_distance,
            approved_lots=approved_lots if risk_allowed else Decimal("0"),
            actual_sl_risk=planned_sl_actual,
            live_min=live_min,
            live_step=live_step,
            live_max=live_max,
            live_cs=live_cs,
            live_tick=live_tick,
            live_tick_val=live_tick_val,
        )
