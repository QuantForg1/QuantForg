"""Risk Management Engine — evaluate before Execution Gateway. Never order_send."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_DOWN, Decimal
from uuid import UUID

from app.domain.entities.mt5_portfolio import AccountSnapshot, MT5Position
from app.domain.entities.risk_engine import (
    DrawdownState,
    ExposureBreakdown,
    PositionSizeResult,
    RiskAssessment,
    RiskEngineConfig,
    RiskRuleResult,
    contract_size_for_symbol,
)
from app.domain.enums.risk import (
    PositionSizingMethod,
    RiskDecision,
    RiskScoreBand,
)
from app.domain.events.base import DomainEvent
from app.domain.events.risk import RiskApproved, RiskReduced, RiskRejected

# Simplified FX correlation groups for correlation risk.
_CORRELATION_GROUPS: dict[str, frozenset[str]] = {
    "usd_majors": frozenset({"EURUSD", "GBPUSD", "AUDUSD", "NZDUSD"}),
    "usd_jpy": frozenset({"USDJPY", "EURJPY", "GBPJPY"}),
    "metals": frozenset({"XAUUSD", "XAGUSD"}),
    "crypto": frozenset({"BTCUSD", "ETHUSD"}),
}

_ASSET_CLASS: dict[str, str] = {
    "EURUSD": "fx",
    "GBPUSD": "fx",
    "USDJPY": "fx",
    "AUDUSD": "fx",
    "NZDUSD": "fx",
    "EURJPY": "fx",
    "GBPJPY": "fx",
    "XAUUSD": "metal",
    "XAGUSD": "metal",
    "BTCUSD": "crypto",
    "ETHUSD": "crypto",
}


@dataclass(frozen=True, slots=True)
class RiskCheckInput:
    """Normalized input for a risk evaluation (no broker send)."""

    user_id: UUID
    request_id: str
    symbol: str
    side: str  # buy | sell
    requested_lots: Decimal | None = None
    stop_loss_distance: Decimal | None = None  # absolute price distance
    atr: Decimal | None = None
    sizing_method: PositionSizingMethod = PositionSizingMethod.PERCENTAGE_RISK
    entry_price: Decimal = Decimal("1")
    # Institutional extensions (Phase B) — optional; ignored when None / unset
    consecutive_losses: int = 0
    cooldown_active: bool = False
    cooldown_remaining_minutes: int = 0
    spread: Decimal | None = None
    session_allowed: bool | None = None
    session_name: str = ""


@dataclass
class RiskEngine:
    """Centralized pre-trade risk gate. Decisions only — never executes."""

    config: RiskEngineConfig = field(default_factory=RiskEngineConfig)
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    def _contract_size(self, symbol: str) -> Decimal:
        return contract_size_for_symbol(symbol, default=self.config.contract_size)

    @staticmethod
    def _account_leverage(account: AccountSnapshot, *, fallback: Decimal) -> Decimal:
        lev = Decimal(int(account.leverage)) if account.leverage else Decimal("0")
        return lev if lev > 0 else fallback

    # -- 1. Position sizing --------------------------------------------------

    def size_position(
        self,
        *,
        equity: Decimal,
        method: PositionSizingMethod,
        requested_lots: Decimal | None,
        stop_distance: Decimal | None,
        atr: Decimal | None,
        entry_price: Decimal,
        contract_size: Decimal | None = None,
    ) -> PositionSizeResult:
        cfg = self.config
        cs = contract_size if contract_size is not None else cfg.contract_size
        stop = stop_distance or Decimal("0")
        if method is PositionSizingMethod.FIXED_LOT:
            lots = requested_lots if requested_lots is not None else cfg.fixed_lot
            dollar = lots * stop * cs
        elif method is PositionSizingMethod.FIXED_DOLLAR_RISK:
            risk_budget = cfg.fixed_dollar_risk
            if stop <= 0:
                lots = cfg.min_lot
            else:
                lots = (risk_budget / (stop * cs)).quantize(
                    cfg.lot_step, rounding=ROUND_DOWN
                )
            dollar = risk_budget
        elif method is PositionSizingMethod.ATR_BASED:
            atr_val = atr if atr is not None and atr > 0 else stop
            if atr_val <= 0:
                atr_val = entry_price * Decimal("0.001")
            risk_budget = equity * (cfg.max_risk_per_trade_pct / Decimal("100"))
            distance = atr_val * cfg.atr_multiplier
            lots = (risk_budget / (distance * cs)).quantize(
                cfg.lot_step, rounding=ROUND_DOWN
            )
            stop = distance
            dollar = risk_budget
        else:  # PERCENTAGE_RISK
            risk_budget = equity * (cfg.max_risk_per_trade_pct / Decimal("100"))
            if stop <= 0:
                stop = entry_price * Decimal("0.001")
            lots = (risk_budget / (stop * cs)).quantize(
                cfg.lot_step, rounding=ROUND_DOWN
            )
            dollar = risk_budget
            if requested_lots is not None and requested_lots > 0:
                # Prefer smaller of calculated vs requested
                lots = min(lots, requested_lots)

        if lots < cfg.min_lot:
            lots = cfg.min_lot
        capped = lots > cfg.max_lot
        approved = min(lots, cfg.max_lot)
        requested = approved if requested_lots is None else requested_lots
        return PositionSizeResult(
            method=method,
            requested_lots=requested,
            approved_lots=approved,
            capped=capped or (requested > approved),
            dollar_risk=dollar.quantize(Decimal("0.01")),
            stop_distance=stop,
        )

    # -- 2. Exposure ---------------------------------------------------------

    def calculate_exposure(
        self,
        positions: list[MT5Position],
        *,
        equity: Decimal,
        proposed_symbol: str,
        proposed_side: str,
        proposed_lots: Decimal,
        entry_price: Decimal,
        leverage: Decimal | None = None,
    ) -> ExposureBreakdown:
        by_symbol: dict[str, Decimal] = {}
        by_class: dict[str, Decimal] = {}
        long_exp = Decimal("0")
        short_exp = Decimal("0")
        lev = leverage if leverage and leverage > 0 else self.config.exposure_leverage

        def _margin_exposure(
            volume: Decimal, price: Decimal, *, symbol: str
        ) -> Decimal:
            # Estimate used margin at account leverage (not full notional).
            return (volume * price * self._contract_size(symbol) / lev).quantize(
                Decimal("0.01")
            )

        for pos in positions:
            notion = _margin_exposure(pos.volume, pos.open_price, symbol=pos.symbol)
            by_symbol[pos.symbol] = by_symbol.get(pos.symbol, Decimal("0")) + notion
            cls = _ASSET_CLASS.get(pos.symbol, "other")
            by_class[cls] = by_class.get(cls, Decimal("0")) + notion
            if pos.side == "buy":
                long_exp += notion
            else:
                short_exp += notion

        sym = proposed_symbol.strip().upper()
        proposed = _margin_exposure(proposed_lots, entry_price, symbol=sym)
        by_symbol[sym] = by_symbol.get(sym, Decimal("0")) + proposed
        cls = _ASSET_CLASS.get(sym, "other")
        by_class[cls] = by_class.get(cls, Decimal("0")) + proposed
        if proposed_side == "buy":
            long_exp += proposed
        else:
            short_exp += proposed

        total = long_exp + short_exp
        _ = equity
        return ExposureBreakdown(
            by_symbol=by_symbol,
            by_asset_class=by_class,
            total=total,
            long_exposure=long_exp,
            short_exposure=short_exp,
        )

    def exposure_limits_ok(
        self, exposure: ExposureBreakdown, *, equity: Decimal, symbol: str
    ) -> tuple[bool, list[str], list[str], dict[str, Decimal]]:
        reasons: list[str] = []
        warnings: list[str] = []
        metrics: dict[str, Decimal] = {
            "symbol_pct": Decimal("0"),
            "class_pct": Decimal("0"),
            "total_pct": Decimal("0"),
        }
        if equity <= 0:
            return (
                False,
                ["equity must be positive for exposure checks"],
                warnings,
                metrics,
            )

        def _pct(notional: Decimal) -> Decimal:
            return (notional / equity * Decimal("100")).quantize(Decimal("0.01"))

        sym = symbol.strip().upper()
        sym_pct = _pct(exposure.by_symbol.get(sym, Decimal("0")))
        metrics["symbol_pct"] = sym_pct
        if sym_pct > self.config.max_symbol_exposure_pct:
            reasons.append(
                f"symbol exposure {sym_pct}% exceeds "
                f"{self.config.max_symbol_exposure_pct}%"
            )
        elif sym_pct > self.config.max_symbol_exposure_pct * Decimal("0.8"):
            warnings.append("symbol exposure approaching limit")

        cls = _ASSET_CLASS.get(sym, "other")
        class_pct = _pct(exposure.by_asset_class.get(cls, Decimal("0")))
        metrics["class_pct"] = class_pct
        if class_pct > self.config.max_asset_class_exposure_pct:
            reasons.append(
                f"asset class exposure {class_pct}% exceeds "
                f"{self.config.max_asset_class_exposure_pct}%"
            )

        total_pct = _pct(exposure.total)
        metrics["total_pct"] = total_pct
        if total_pct > self.config.max_total_exposure_pct:
            reasons.append(
                f"total exposure {total_pct}% exceeds "
                f"{self.config.max_total_exposure_pct}%"
            )

        return len(reasons) == 0, reasons, warnings, metrics

    def _rule(
        self,
        *,
        rule_id: str,
        name: str,
        status: str,
        current: str,
        threshold: str,
        reason: str = "",
        suggested_action: str = "",
    ) -> RiskRuleResult:
        return RiskRuleResult(
            id=rule_id,
            name=name,
            status=status,
            current=current,
            threshold=threshold,
            reason=reason,
            suggested_action=suggested_action,
        )

    @staticmethod
    def _limit_status(
        current: Decimal,
        limit: Decimal,
        *,
        warn_ratio: Decimal = Decimal("0.8"),
    ) -> str:
        if limit <= 0:
            return "n/a"
        if current > limit:
            return "fail"
        if current >= limit * warn_ratio:
            return "warn"
        return "pass"

    def _build_rules(
        self,
        *,
        check: RiskCheckInput,
        account: AccountSnapshot,
        size: PositionSizeResult,
        drawdown: DrawdownState,
        exp_metrics: dict[str, Decimal],
        corr_pct: Decimal,
        open_count: int,
        contract_size: Decimal,
        leverage: Decimal,
        checks: dict[str, bool],
        proposed_margin: Decimal,
    ) -> list[RiskRuleResult]:
        cfg = self.config
        rules: list[RiskRuleResult] = []

        def action_for(status: str, reduce: str, stop: str) -> str:
            if status == "fail":
                return stop
            if status == "warn":
                return reduce
            if status == "n/a":
                return "Not available — supply live input or enable gate"
            return "No action required"

        # --- Loss / drawdown ---
        daily_st = self._limit_status(drawdown.daily_loss_pct, cfg.max_daily_loss_pct)
        rules.append(
            self._rule(
                rule_id="daily_loss",
                name="Daily Loss",
                status=daily_st,
                current=f"{drawdown.daily_loss_pct}%",
                threshold=f"{cfg.max_daily_loss_pct}%",
                reason=(
                    f"daily loss {drawdown.daily_loss_pct}% vs max "
                    f"{cfg.max_daily_loss_pct}%"
                ),
                suggested_action=action_for(
                    daily_st,
                    "Reduce size or pause new risk for the session",
                    "Halt new entries until daily loss recovers",
                ),
            )
        )
        weekly_st = self._limit_status(
            drawdown.weekly_loss_pct, cfg.max_weekly_loss_pct
        )
        rules.append(
            self._rule(
                rule_id="weekly_loss",
                name="Weekly Loss",
                status=weekly_st,
                current=f"{drawdown.weekly_loss_pct}%",
                threshold=f"{cfg.max_weekly_loss_pct}%",
                reason=(
                    f"weekly loss {drawdown.weekly_loss_pct}% vs max "
                    f"{cfg.max_weekly_loss_pct}%"
                ),
                suggested_action=action_for(
                    weekly_st,
                    "Cut risk until weekly P/L improves",
                    "Block new risk — weekly loss limit breached",
                ),
            )
        )
        monthly_st = self._limit_status(
            drawdown.monthly_loss_pct, cfg.max_monthly_loss_pct
        )
        rules.append(
            self._rule(
                rule_id="monthly_loss",
                name="Monthly Loss",
                status=monthly_st,
                current=f"{drawdown.monthly_loss_pct}%",
                threshold=f"{cfg.max_monthly_loss_pct}%",
                reason=(
                    f"monthly loss {drawdown.monthly_loss_pct}% vs max "
                    f"{cfg.max_monthly_loss_pct}%"
                ),
                suggested_action=action_for(
                    monthly_st,
                    "Lower frequency and size",
                    "Stop trading for the month — monthly loss breached",
                ),
            )
        )
        dd_st = self._limit_status(drawdown.current_drawdown_pct, cfg.max_drawdown_pct)
        rules.append(
            self._rule(
                rule_id="max_drawdown",
                name="Max Drawdown",
                status=dd_st,
                current=f"{drawdown.current_drawdown_pct}%",
                threshold=f"{cfg.max_drawdown_pct}%",
                reason=(
                    f"drawdown {drawdown.current_drawdown_pct}% from peak "
                    f"{drawdown.peak_equity}"
                ),
                suggested_action=action_for(
                    dd_st,
                    "De-risk open book; avoid adding exposure",
                    "Equity protection — reject new risk",
                ),
            )
        )

        risk_pct = (
            (size.dollar_risk / drawdown.equity * Decimal("100")).quantize(
                Decimal("0.01")
            )
            if drawdown.equity > 0
            else Decimal("0")
        )
        risk_st = self._limit_status(risk_pct, cfg.max_risk_per_trade_pct)
        rules.append(
            self._rule(
                rule_id="max_risk",
                name="Max Risk Per Trade",
                status=risk_st,
                current=f"{risk_pct}%",
                threshold=f"{cfg.max_risk_per_trade_pct}%",
                reason=f"dollar risk {size.dollar_risk} on equity {drawdown.equity}",
                suggested_action=action_for(
                    risk_st,
                    "Tighten stop or reduce lots",
                    "Reject — risk per trade exceeds policy",
                ),
            )
        )

        # --- Margin (live account) ---
        free = account.free_margin
        used = account.margin
        equity = account.equity if account.equity > 0 else drawdown.equity
        margin_level = account.margin_level
        margin_req_pct = (
            (proposed_margin / equity * Decimal("100")).quantize(Decimal("0.01"))
            if equity > 0
            else Decimal("0")
        )
        margin_ok = proposed_margin <= free if free >= 0 else True
        margin_st = "pass" if margin_ok else "fail"
        if margin_ok and free > 0 and proposed_margin >= free * Decimal("0.8"):
            margin_st = "warn"
        rules.append(
            self._rule(
                rule_id="margin_requirement",
                name="Margin Requirement",
                status=margin_st,
                current=f"{proposed_margin} ({margin_req_pct}% equity)",
                threshold=f"≤ free margin {free}",
                reason=f"proposed margin {proposed_margin}; free {free}; used {used}",
                suggested_action=action_for(
                    margin_st,
                    "Reduce volume to preserve free margin",
                    "Reject — insufficient free margin for this order",
                ),
            )
        )
        free_st = "pass" if free > 0 else ("fail" if equity > 0 else "n/a")
        if free_st == "pass" and equity > 0 and free < equity * Decimal("0.2"):
            free_st = "warn"
        rules.append(
            self._rule(
                rule_id="free_margin",
                name="Free Margin",
                status=free_st,
                current=str(free),
                threshold="> 0 (warn < 20% equity)",
                reason=f"free margin {free} / equity {equity}",
                suggested_action=action_for(
                    free_st,
                    "Close or reduce positions to free margin",
                    "No free margin — cannot add risk",
                ),
            )
        )
        if margin_level > 0:
            ml_st = (
                "fail"
                if margin_level < 100
                else ("warn" if margin_level < 200 else "pass")
            )
            rules.append(
                self._rule(
                    rule_id="margin_level",
                    name="Margin Level",
                    status=ml_st,
                    current=f"{margin_level}%",
                    threshold="≥ 200% preferred · ≥ 100% required",
                    reason=f"broker margin level {margin_level}%",
                    suggested_action=action_for(
                        ml_st,
                        "Reduce exposure before margin call zone",
                        "Margin level critical — reject new entries",
                    ),
                )
            )
        else:
            rules.append(
                self._rule(
                    rule_id="margin_level",
                    name="Margin Level",
                    status="n/a",
                    current="Not available",
                    threshold="≥ 200% preferred",
                    reason="No open margin / broker did not report margin level",
                    suggested_action="Not available",
                )
            )

        # --- Exposure ---
        sym_pct = exp_metrics.get("symbol_pct", Decimal("0"))
        sym_st = self._limit_status(sym_pct, cfg.max_symbol_exposure_pct)
        rules.append(
            self._rule(
                rule_id="symbol_exposure",
                name="Symbol Exposure",
                status=sym_st,
                current=f"{sym_pct}%",
                threshold=f"{cfg.max_symbol_exposure_pct}%",
                reason=f"{check.symbol} margin exposure vs equity",
                suggested_action=action_for(
                    sym_st,
                    "Reduce size on this symbol",
                    "Reject — symbol exposure limit breached",
                ),
            )
        )
        class_pct = exp_metrics.get("class_pct", Decimal("0"))
        class_st = self._limit_status(class_pct, cfg.max_asset_class_exposure_pct)
        rules.append(
            self._rule(
                rule_id="asset_class_exposure",
                name="Asset Exposure",
                status=class_st,
                current=f"{class_pct}%",
                threshold=f"{cfg.max_asset_class_exposure_pct}%",
                reason="Asset-class margin exposure vs equity",
                suggested_action=action_for(
                    class_st,
                    "Diversify or reduce class exposure",
                    "Reject — asset-class exposure limit breached",
                ),
            )
        )
        corr_active = corr_pct > 0 or check.symbol.upper() in {
            "XAUUSD",
            "XAGUSD",
            "EURUSD",
            "GBPUSD",
        }
        if corr_active:
            corr_st = self._limit_status(corr_pct, cfg.max_correlated_exposure_pct)
        else:
            corr_st = "n/a"
        rules.append(
            self._rule(
                rule_id="correlation",
                name="Correlation Exposure",
                status=corr_st,
                current=f"{corr_pct}%" if corr_st != "n/a" else "Not available",
                threshold=f"{cfg.max_correlated_exposure_pct}%",
                reason="Correlated group margin vs equity",
                suggested_action=action_for(
                    corr_st,
                    "Avoid stacking correlated symbols",
                    "Reject — correlated exposure limit breached",
                ),
            )
        )
        total_pct = exp_metrics.get("total_pct", Decimal("0"))
        total_st = self._limit_status(total_pct, cfg.max_total_exposure_pct)
        rules.append(
            self._rule(
                rule_id="total_exposure",
                name="Total Exposure",
                status=total_st,
                current=f"{total_pct}%",
                threshold=f"{cfg.max_total_exposure_pct}%",
                reason=f"contract_size={contract_size} leverage={leverage}",
                suggested_action=action_for(
                    total_st,
                    "Reduce overall book size",
                    "Reject — total exposure limit breached",
                ),
            )
        )
        open_st = "pass" if checks.get("open_positions", True) else "fail"
        if open_st == "pass" and open_count >= max(1, cfg.max_open_positions - 1):
            open_st = "warn"
        rules.append(
            self._rule(
                rule_id="open_positions",
                name="Open Positions",
                status=open_st,
                current=str(open_count),
                threshold=f"< {cfg.max_open_positions}",
                reason=f"{open_count} open vs max {cfg.max_open_positions}",
                suggested_action=action_for(
                    open_st,
                    "Close a position before adding risk",
                    "Reject — max open positions reached",
                ),
            )
        )

        # --- Market microstructure ---
        if check.spread is None:
            rules.append(
                self._rule(
                    rule_id="spread",
                    name="Spread",
                    status="n/a",
                    current="Not available",
                    threshold=str(cfg.max_spread),
                    reason="Spread not supplied on this risk check",
                    suggested_action="Not available",
                )
            )
        else:
            spread_st = (
                "fail"
                if cfg.enforce_spread and check.spread > cfg.max_spread
                else (
                    "warn"
                    if cfg.enforce_spread
                    and check.spread > cfg.max_spread * Decimal("0.8")
                    else "pass"
                )
            )
            rules.append(
                self._rule(
                    rule_id="spread",
                    name="Spread",
                    status=spread_st,
                    current=str(check.spread),
                    threshold=str(cfg.max_spread),
                    reason=f"live spread {check.spread}",
                    suggested_action=action_for(
                        spread_st,
                        "Wait for tighter spread",
                        "Reject — spread exceeds max",
                    ),
                )
            )

        if check.atr is None:
            rules.append(
                self._rule(
                    rule_id="atr",
                    name="ATR",
                    status="n/a",
                    current="Not available",
                    threshold=f"max {cfg.max_atr_pct_of_price}% of price",
                    reason="ATR not supplied on this risk check",
                    suggested_action="Not available",
                )
            )
        else:
            atr_st = "pass"
            atr_detail = str(check.atr)
            if (
                cfg.enforce_atr
                and check.entry_price > 0
                and cfg.max_atr_pct_of_price > 0
            ):
                atr_pct = (check.atr / check.entry_price) * Decimal("100")
                atr_detail = f"{atr_pct.quantize(Decimal('0.01'))}%"
                atr_st = self._limit_status(atr_pct, cfg.max_atr_pct_of_price)
            rules.append(
                self._rule(
                    rule_id="atr",
                    name="ATR",
                    status=atr_st,
                    current=atr_detail,
                    threshold=f"{cfg.max_atr_pct_of_price}%",
                    reason="ATR as % of entry price",
                    suggested_action=action_for(
                        atr_st,
                        "Widen stops or cut size in high ATR",
                        "Reject — volatility outside policy",
                    ),
                )
            )

        if check.session_allowed is None:
            rules.append(
                self._rule(
                    rule_id="session",
                    name="Session",
                    status="n/a",
                    current="Not available",
                    threshold="Allowed session when enforced",
                    reason="Session gate not evaluated on this check",
                    suggested_action="Not available",
                )
            )
        else:
            sess_st = "pass" if check.session_allowed else "fail"
            rules.append(
                self._rule(
                    rule_id="session",
                    name="Session",
                    status=sess_st,
                    current=check.session_name or str(check.session_allowed),
                    threshold="allowed session",
                    reason="Session restriction gate",
                    suggested_action=action_for(
                        sess_st,
                        "Wait for London/NY window",
                        "Reject — session restricted",
                    ),
                )
            )

        streak_st = (
            "fail"
            if check.consecutive_losses >= cfg.max_consecutive_losses > 0
            else (
                "warn"
                if check.consecutive_losses >= max(1, cfg.max_consecutive_losses - 1)
                else "pass"
            )
        )
        rules.append(
            self._rule(
                rule_id="loss_streak",
                name="Consecutive Losses",
                status=streak_st,
                current=str(check.consecutive_losses),
                threshold=f"< {cfg.max_consecutive_losses}",
                reason="Loss streak gate",
                suggested_action=action_for(
                    streak_st,
                    "Reduce size after consecutive losses",
                    "Reject — loss streak at policy max",
                ),
            )
        )
        cool_st = "fail" if check.cooldown_active else "pass"
        rules.append(
            self._rule(
                rule_id="cooldown",
                name="Cooldown",
                status=cool_st,
                current="active" if check.cooldown_active else "clear",
                threshold=f"{cfg.cooldown_minutes_after_loss_streak}m after streak",
                reason="Post-streak cooldown",
                suggested_action=action_for(
                    cool_st,
                    "Wait out cooldown",
                    "Reject — cooldown active",
                ),
            )
        )

        # ITE / AI — honest N/A on this HTTP path (never invent)
        rules.append(
            self._rule(
                rule_id="news",
                name="News",
                status="n/a",
                current="Not available",
                threshold="±30m when news_protection_enabled",
                reason="ITE news gate is not part of HTTP /risk/check",
                suggested_action="Not available",
            )
        )
        rules.append(
            self._rule(
                rule_id="confluence",
                name="Confluence Score",
                status="n/a",
                current="Not available",
                threshold="80/100 (ITE)",
                reason="ITE confluence has no public HTTP surface yet",
                suggested_action="Not available",
            )
        )
        rules.append(
            self._rule(
                rule_id="ai_confidence",
                name="AI Confidence",
                status="n/a",
                current="Not available",
                threshold="See AI Decision Card (live strategy)",
                reason=(
                    "AI confidence is sourced from strategy/quant-ai APIs, "
                    "not risk engine"
                ),
                suggested_action="Not available",
            )
        )
        return rules

    # -- 3. Drawdown protection ----------------------------------------------

    def evaluate_drawdown(
        self,
        account: AccountSnapshot,
        *,
        peak_equity: Decimal | None = None,
        daily_pnl: Decimal = Decimal("0"),
        weekly_pnl: Decimal = Decimal("0"),
        monthly_pnl: Decimal = Decimal("0"),
    ) -> tuple[DrawdownState, list[str], list[str]]:
        equity = account.equity
        peak = (
            peak_equity
            if peak_equity and peak_equity > 0
            else max(equity, account.balance)
        )
        dd = Decimal("0")
        if peak > 0 and equity < peak:
            dd = ((peak - equity) / peak * Decimal("100")).quantize(Decimal("0.01"))

        def _loss_pct(pnl: Decimal) -> Decimal:
            base = account.balance if account.balance > 0 else equity
            if base <= 0 or pnl >= 0:
                return Decimal("0")
            return ((-pnl) / base * Decimal("100")).quantize(Decimal("0.01"))

        daily = _loss_pct(daily_pnl)
        weekly = _loss_pct(weekly_pnl)
        monthly = _loss_pct(monthly_pnl)
        protected = dd < self.config.max_drawdown_pct

        state = DrawdownState(
            equity=equity,
            peak_equity=peak,
            current_drawdown_pct=dd,
            daily_loss_pct=daily,
            weekly_loss_pct=weekly,
            monthly_loss_pct=monthly,
            equity_protected=protected,
        )
        reasons: list[str] = []
        warnings: list[str] = []
        if daily > self.config.max_daily_loss_pct:
            reasons.append(
                f"daily loss {daily}% exceeds {self.config.max_daily_loss_pct}%"
            )
        if weekly > self.config.max_weekly_loss_pct:
            reasons.append(
                f"weekly loss {weekly}% exceeds {self.config.max_weekly_loss_pct}%"
            )
        if monthly > self.config.max_monthly_loss_pct:
            reasons.append(
                f"monthly loss {monthly}% exceeds {self.config.max_monthly_loss_pct}%"
            )
        if dd >= self.config.max_drawdown_pct:
            reasons.append(
                f"max drawdown {dd}% reaches {self.config.max_drawdown_pct}%"
            )
            protected = False
        elif dd >= self.config.max_drawdown_pct * Decimal("0.8"):
            warnings.append("drawdown approaching equity protection limit")
        return (
            DrawdownState(
                equity=state.equity,
                peak_equity=state.peak_equity,
                current_drawdown_pct=state.current_drawdown_pct,
                daily_loss_pct=state.daily_loss_pct,
                weekly_loss_pct=state.weekly_loss_pct,
                monthly_loss_pct=state.monthly_loss_pct,
                equity_protected=protected and len(reasons) == 0,
            ),
            reasons,
            warnings,
        )

    # -- 4. Correlation ------------------------------------------------------

    def correlation_risk_ok(
        self,
        positions: list[MT5Position],
        *,
        symbol: str,
        proposed_lots: Decimal,
        entry_price: Decimal,
        equity: Decimal,
        leverage: Decimal | None = None,
    ) -> tuple[bool, list[str], list[str], Decimal]:
        reasons: list[str] = []
        warnings: list[str] = []
        sym = symbol.strip().upper()
        group = next(
            (name for name, members in _CORRELATION_GROUPS.items() if sym in members),
            None,
        )
        if group is None or equity <= 0:
            return True, reasons, warnings, Decimal("0")

        lev = leverage if leverage and leverage > 0 else self.config.exposure_leverage
        members = _CORRELATION_GROUPS[group]
        correlated_notional = Decimal("0")
        for pos in positions:
            if pos.symbol in members:
                correlated_notional += (
                    pos.volume * pos.open_price * self._contract_size(pos.symbol) / lev
                )
        correlated_notional += (
            proposed_lots * entry_price * self._contract_size(sym) / lev
        )
        pct = (correlated_notional / equity * Decimal("100")).quantize(Decimal("0.01"))
        if pct > self.config.max_correlated_exposure_pct:
            reasons.append(
                f"correlated exposure in {group} at {pct}% exceeds "
                f"{self.config.max_correlated_exposure_pct}%"
            )
        elif pct > self.config.max_correlated_exposure_pct * Decimal("0.8"):
            warnings.append(f"correlated exposure in {group} approaching limit")
        return len(reasons) == 0, reasons, warnings, pct

    # -- 5. Risk score -------------------------------------------------------

    @staticmethod
    def score_to_band(score: int) -> RiskScoreBand:
        if score >= 85:
            return RiskScoreBand.BLOCKED
        if score >= 65:
            return RiskScoreBand.HIGH
        if score >= 35:
            return RiskScoreBand.MEDIUM
        return RiskScoreBand.LOW

    def compute_risk_score(
        self,
        *,
        exposure_ok: bool,
        drawdown_ok: bool,
        correlation_ok: bool,
        size: PositionSizeResult,
        open_positions: int,
        drawdown: DrawdownState,
    ) -> int:
        score = 10
        if size.capped:
            score += 15
        if not exposure_ok:
            score += 30
        if not drawdown_ok:
            score += 35
        if not correlation_ok:
            score += 25
        if open_positions >= self.config.max_open_positions:
            score += 40
        elif open_positions >= self.config.max_open_positions - 1:
            score += 15
        score += min(20, int(drawdown.current_drawdown_pct))
        return max(0, min(100, score))

    def _institutional_gates(self, check: RiskCheckInput) -> tuple[bool, list[str]]:
        """Consecutive losses, cooldown, session, spread, ATR volatility filters."""
        cfg = self.config
        reasons: list[str] = []

        if check.consecutive_losses >= cfg.max_consecutive_losses > 0:
            reasons.append(
                f"consecutive losses {check.consecutive_losses} "
                f"at/above max {cfg.max_consecutive_losses}"
            )
        if check.cooldown_active:
            reasons.append(
                "cooldown active"
                + (
                    f" ({check.cooldown_remaining_minutes}m remaining)"
                    if check.cooldown_remaining_minutes > 0
                    else ""
                )
            )
        if cfg.enforce_session and check.session_allowed is False:
            reasons.append(
                "session restricted"
                + (f" ({check.session_name})" if check.session_name else "")
            )
        if (
            cfg.enforce_spread
            and check.spread is not None
            and cfg.max_spread > 0
            and check.spread > cfg.max_spread
        ):
            reasons.append(f"spread {check.spread} exceeds max {cfg.max_spread}")
        if cfg.enforce_atr and check.atr is not None and check.entry_price > 0:
            atr = check.atr
            if cfg.min_atr > 0 and atr < cfg.min_atr:
                reasons.append(f"ATR {atr} below minimum {cfg.min_atr}")
            if cfg.max_atr > 0 and atr > cfg.max_atr:
                reasons.append(f"ATR {atr} above maximum {cfg.max_atr}")
            if cfg.max_atr_pct_of_price > 0:
                atr_pct = (atr / check.entry_price) * Decimal("100")
                if atr_pct > cfg.max_atr_pct_of_price:
                    reasons.append(
                        f"ATR {atr_pct:.2f}% of price exceeds "
                        f"max {cfg.max_atr_pct_of_price}%"
                    )

        return (len(reasons) == 0, reasons)

    # -- 6. Full evaluate ----------------------------------------------------

    def evaluate(
        self,
        check: RiskCheckInput,
        *,
        account: AccountSnapshot,
        positions: list[MT5Position],
        peak_equity: Decimal | None = None,
        daily_pnl: Decimal = Decimal("0"),
        weekly_pnl: Decimal = Decimal("0"),
        monthly_pnl: Decimal = Decimal("0"),
    ) -> RiskAssessment:
        """Run full risk pipeline. Returns ALLOW | REDUCE_SIZE | REJECT only."""
        reasons: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}
        contract_size = self._contract_size(check.symbol)
        leverage = self._account_leverage(
            account, fallback=self.config.exposure_leverage
        )

        size = self.size_position(
            equity=account.equity,
            method=check.sizing_method,
            requested_lots=check.requested_lots,
            stop_distance=check.stop_loss_distance,
            atr=check.atr,
            entry_price=check.entry_price,
            contract_size=contract_size,
        )
        checks["position_sizing"] = size.approved_lots >= self.config.min_lot

        open_count = len(positions)
        checks["open_positions"] = open_count < self.config.max_open_positions
        if not checks["open_positions"]:
            reasons.append(
                f"open positions {open_count} at max {self.config.max_open_positions}"
            )

        exposure = self.calculate_exposure(
            positions,
            equity=account.equity,
            proposed_symbol=check.symbol,
            proposed_side=check.side,
            proposed_lots=size.approved_lots,
            entry_price=check.entry_price,
            leverage=leverage,
        )
        exp_ok, exp_reasons, exp_warn, exp_metrics = self.exposure_limits_ok(
            exposure, equity=account.equity, symbol=check.symbol
        )
        checks["exposure"] = exp_ok
        reasons.extend(exp_reasons)
        warnings.extend(exp_warn)

        drawdown, dd_reasons, dd_warn = self.evaluate_drawdown(
            account,
            peak_equity=peak_equity,
            daily_pnl=daily_pnl,
            weekly_pnl=weekly_pnl,
            monthly_pnl=monthly_pnl,
        )
        dd_ok = len(dd_reasons) == 0
        checks["drawdown"] = dd_ok
        reasons.extend(dd_reasons)
        warnings.extend(dd_warn)

        corr_ok, corr_reasons, corr_warn, corr_pct = self.correlation_risk_ok(
            positions,
            symbol=check.symbol,
            proposed_lots=size.approved_lots,
            entry_price=check.entry_price,
            equity=account.equity,
            leverage=leverage,
        )
        checks["correlation"] = corr_ok
        reasons.extend(corr_reasons)
        warnings.extend(corr_warn)

        # --- Institutional extensions (Phase B) ---
        inst_ok, inst_reasons = self._institutional_gates(check)
        checks["institutional"] = inst_ok
        if not inst_ok:
            reasons.extend(inst_reasons)

        score = self.compute_risk_score(
            exposure_ok=exp_ok,
            drawdown_ok=dd_ok,
            correlation_ok=corr_ok,
            size=size,
            open_positions=open_count,
            drawdown=drawdown,
        )
        if not inst_ok:
            score = min(100, score + 40)
        band = self.score_to_band(score)

        approved = size.approved_lots
        decision = RiskDecision.ALLOW

        if (
            band is RiskScoreBand.BLOCKED
            or not dd_ok
            or not checks["open_positions"]
            or not inst_ok
        ):
            decision = RiskDecision.REJECT
            approved = Decimal("0")
        elif not exp_ok or not corr_ok or size.capped or band is RiskScoreBand.HIGH:
            decision = RiskDecision.REDUCE_SIZE
            # Halve size on reduce, still respect min/max
            reduced = (approved / Decimal("2")).quantize(
                self.config.lot_step, rounding=ROUND_DOWN
            )
            if reduced < self.config.min_lot:
                if not exp_ok or not corr_ok:
                    decision = RiskDecision.REJECT
                    approved = Decimal("0")
                else:
                    approved = self.config.min_lot
            else:
                approved = reduced
                if size.requested_lots > approved:
                    reasons.append(
                        f"size reduced from {size.requested_lots} to {approved} lots"
                    )
        elif size.requested_lots > size.approved_lots:
            decision = RiskDecision.REDUCE_SIZE
            reasons.append(
                f"size capped from {size.requested_lots} to {size.approved_lots} lots"
            )
            approved = size.approved_lots

        proposed_margin = (
            size.approved_lots * check.entry_price * contract_size / leverage
        ).quantize(Decimal("0.01"))
        rule_rows = self._build_rules(
            check=check,
            account=account,
            size=size,
            drawdown=drawdown,
            exp_metrics=exp_metrics,
            corr_pct=corr_pct,
            open_count=open_count,
            contract_size=contract_size,
            leverage=leverage,
            checks=checks,
            proposed_margin=proposed_margin,
        )
        rules_payload = [r.to_dict() for r in rule_rows]

        assessment = RiskAssessment.record(
            user_id=check.user_id,
            request_id=check.request_id,
            symbol=check.symbol,
            side=check.side,
            decision=decision,
            risk_score=score,
            risk_band=band,
            approved_lots=approved,
            requested_lots=size.requested_lots,
            sizing_method=size.method.value,
            warnings=warnings,
            reasons=reasons if decision is not RiskDecision.ALLOW else [],
            exposure=exposure.to_dict(),
            drawdown=drawdown.to_dict(),
            checks=checks,
            rules=rules_payload,
            request_snapshot={
                "symbol": check.symbol,
                "side": check.side,
                "requested_lots": (
                    str(check.requested_lots) if check.requested_lots else None
                ),
                "sizing_method": check.sizing_method.value,
                "entry_price": str(check.entry_price),
                "stop_loss_distance": (
                    str(check.stop_loss_distance) if check.stop_loss_distance else None
                ),
                "atr": str(check.atr) if check.atr else None,
                "consecutive_losses": check.consecutive_losses,
                "cooldown_active": check.cooldown_active,
                "spread": str(check.spread) if check.spread is not None else None,
                "session_allowed": check.session_allowed,
                "session_name": check.session_name,
                "contract_size": str(contract_size),
                "leverage": str(leverage),
                "rules": rules_payload,
            },
        )

        if decision is RiskDecision.ALLOW:
            self._events.append(
                RiskApproved(
                    user_id=check.user_id,
                    assessment_id=assessment.id,
                    request_id=check.request_id,
                    symbol=check.symbol,
                    risk_score=score,
                    approved_lots=str(approved),
                )
            )
        elif decision is RiskDecision.REDUCE_SIZE:
            self._events.append(
                RiskReduced(
                    user_id=check.user_id,
                    assessment_id=assessment.id,
                    request_id=check.request_id,
                    symbol=check.symbol,
                    risk_score=score,
                    requested_lots=str(size.requested_lots),
                    approved_lots=str(approved),
                    reasons=tuple(assessment.reasons),
                )
            )
        else:
            self._events.append(
                RiskRejected(
                    user_id=check.user_id,
                    assessment_id=assessment.id,
                    request_id=check.request_id,
                    symbol=check.symbol,
                    risk_score=score,
                    reasons=tuple(assessment.reasons),
                )
            )
        return assessment
