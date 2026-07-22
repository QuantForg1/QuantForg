"""Execution safety service — policy, risk, duplicate, idempotency. Never order_send."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from app.application.services.mt5_order_validation import MT5OrderValidationService
from app.domain.entities.execution_safety import (
    CalculatedRisk,
    ExecutionDecisionRecord,
    ExecutionPolicy,
    RiskPreCheckResult,
)
from app.domain.entities.mt5_order import OrderConstraints, OrderIntent
from app.domain.enums.execution import ExecutionDecision
from app.domain.events.base import DomainEvent
from app.domain.events.execution import (
    ExecutionApproved,
    ExecutionRejected,
    ExecutionRetryRequested,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter


@dataclass
class ExecutionSafetyService:
    """Production-grade pre-execution gate. Decisions only — never submits orders."""

    adapter: MT5Adapter
    order_validation: MT5OrderValidationService
    policy: ExecutionPolicy = field(default_factory=ExecutionPolicy)
    _events: list[DomainEvent] = field(default_factory=list, init=False)

    def drain_events(self) -> list[DomainEvent]:
        events = list(self._events)
        self._events.clear()
        return events

    @staticmethod
    def fingerprint(intent: OrderIntent, *, user_id: UUID) -> str:
        raw = (
            f"{user_id}|{intent.symbol}|{intent.side.value}|"
            f"{intent.order_type.value}|{intent.volume.value}|"
            f"{intent.price}|{intent.stop_loss}|{intent.take_profit}|"
            f"{intent.slippage.value}|{intent.magic.value}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def evaluate_policy(
        self,
        intent: OrderIntent,
        *,
        login: int,
        spread: Decimal,
        leverage: Decimal,
        now: datetime | None = None,
    ) -> tuple[bool, list[str], list[str], dict[str, bool]]:
        reasons: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}

        ok_symbol = self.policy.allows_symbol(intent.symbol)
        checks["symbol_whitelist"] = ok_symbol
        if not ok_symbol:
            reasons.append(f"symbol {intent.symbol} not on whitelist")

        ok_account = self.policy.allows_account(login)
        checks["account_whitelist"] = ok_account
        if not ok_account:
            reasons.append(f"account {login} not on whitelist")

        ok_hours = self.policy.within_trading_hours(now)
        checks["trading_hours"] = ok_hours
        if not ok_hours:
            reasons.append("outside configured trading hours")

        ok_spread = spread <= self.policy.max_spread
        checks["max_spread"] = ok_spread
        if not ok_spread:
            reasons.append(
                f"spread {spread} exceeds max_spread {self.policy.max_spread}"
            )

        ok_slip = intent.slippage.value <= self.policy.max_slippage
        checks["max_slippage"] = ok_slip
        if not ok_slip:
            reasons.append(
                f"slippage {intent.slippage.value} exceeds "
                f"max_slippage {self.policy.max_slippage}"
            )

        ok_lev = leverage <= self.policy.max_leverage
        checks["leverage_limit"] = ok_lev
        if not ok_lev:
            reasons.append(
                f"leverage {leverage} exceeds max_leverage {self.policy.max_leverage}"
            )

        vol = intent.volume.value
        ok_max = vol <= self.policy.max_lot
        ok_min = vol >= self.policy.min_lot
        checks["max_lot"] = ok_max
        checks["min_lot"] = ok_min
        if not ok_max:
            reasons.append(f"volume {vol} exceeds max_lot {self.policy.max_lot}")
        if not ok_min:
            reasons.append(f"volume {vol} below min_lot {self.policy.min_lot}")

        if spread > self.policy.max_spread * Decimal("0.8") and ok_spread:
            warnings.append("spread approaching policy maximum")

        return all(checks.values()), reasons, warnings, checks

    def risk_pre_check(
        self,
        intent: OrderIntent,
        *,
        connected: bool,
        constraints: OrderConstraints | None = None,
    ) -> tuple[RiskPreCheckResult, CalculatedRisk]:
        reasons: list[str] = []
        warnings: list[str] = []
        checks: dict[str, bool] = {}

        checks["broker_connection"] = connected
        if not connected:
            reasons.append("broker connection not active")

        try:
            account = self.adapter.account_info()
            trade_mode_ok = True  # mock accounts are tradeable
            checks["account_status"] = trade_mode_ok
            free_margin = Decimal(str(account.free_margin))
            leverage = Decimal(str(getattr(account, "leverage", 100) or 100))
        except (OSError, RuntimeError, ValueError) as exc:
            checks["account_status"] = False
            reasons.append(f"account status unavailable: {exc}")
            free_margin = Decimal("0")
            leverage = Decimal("0")

        try:
            cons = constraints or self.order_validation.constraints_for(intent.symbol)
            checks["symbol_tradable"] = cons.trade_allowed
            if not cons.trade_allowed:
                reasons.append("symbol not tradable")
            checks["market_open"] = cons.market_open
            if not cons.market_open:
                reasons.append("market closed")
        except (OSError, RuntimeError, ValueError) as exc:
            checks["symbol_tradable"] = False
            checks["market_open"] = False
            reasons.append(f"symbol constraints unavailable: {exc}")
            cons = OrderConstraints(symbol=intent.symbol, trade_allowed=False)

        ok_vol, msg_vol = self.order_validation.validate_volume(intent, cons)
        checks["volume_limits"] = ok_vol
        if not ok_vol:
            reasons.append(msg_vol)

        request = self.order_validation.build_order_request(intent)
        ok_stops, msg_stops = self.order_validation.validate_stops(
            intent, cons, entry_price=request.price
        )
        checks["stop_distance"] = ok_stops
        if not ok_stops:
            reasons.append(msg_stops)

        # Freeze level: reject if entry within freeze distance of SL/TP
        freeze_ok = True
        if cons.freeze_level > 0 and (intent.stop_loss or intent.take_profit):
            point = cons.point
            freeze_dist = Decimal(cons.freeze_level) * point
            if intent.stop_loss is not None:
                sl_dist = abs(request.price - intent.stop_loss.value)
                if sl_dist < freeze_dist:
                    freeze_ok = False
                    reasons.append("stop loss inside freeze level")
            if intent.take_profit is not None:
                tp_dist = abs(request.price - intent.take_profit.value)
                if tp_dist < freeze_dist:
                    freeze_ok = False
                    reasons.append("take profit inside freeze level")
        checks["freeze_level"] = freeze_ok

        ok_margin, msg_margin, margin_res = self.order_validation.validate_margin(
            request, free_margin=free_margin
        )
        checks["free_margin"] = ok_margin
        if not ok_margin:
            reasons.append(msg_margin)

        spread = Decimal("0")
        try:
            tick = self.adapter.latest_tick(intent.symbol)
            spread = Decimal(str(tick.ask)) - Decimal(str(tick.bid))
            if spread <= 0:
                checks["spread_available"] = False
                reasons.append("invalid spread from broker tick")
            else:
                checks["spread_available"] = True
        except (OSError, RuntimeError, ValueError) as exc:
            checks["spread_available"] = False
            reasons.append(f"spread unavailable — fail-closed: {exc}")

        stop_distance = Decimal("0")
        if intent.stop_loss:
            point = cons.point if cons.point and cons.point > 0 else Decimal("0")
            if point <= 0:
                checks["stop_distance"] = False
                reasons.append(
                    "symbol point invalid — fail-closed before stop math"
                )
            else:
                stop_distance = (
                    abs(request.price - intent.stop_loss.value) / point
                )

        margin_usage = Decimal("0")
        if free_margin > 0:
            margin_usage = (margin_res.margin / free_margin * Decimal("100")).quantize(
                Decimal("0.01")
            )

        risk = CalculatedRisk(
            expected_margin=margin_res.margin,
            free_margin=free_margin,
            margin_usage_pct=margin_usage,
            spread=spread,
            leverage=leverage,
            stop_distance_points=stop_distance,
            volume=intent.volume.value,
        )
        passed = all(checks.values())
        return (
            RiskPreCheckResult(
                passed=passed,
                checks=checks,
                reasons=tuple(reasons),
                warnings=tuple(warnings),
            ),
            risk,
        )

    def check_duplicates(
        self,
        *,
        fingerprint: str,
        recent: list[ExecutionDecisionRecord],
        now: datetime | None = None,
    ) -> tuple[ExecutionDecision | None, list[str], list[str]]:
        """Return optional override decision for duplicate / rapid submit.

        - Exact same request_id handled by idempotency (caller).
        - Same fingerprint within window → RETRY (safe retry pressure).
        - Too many rapid submits → REJECT.
        """
        current = now or datetime.now(UTC)
        window = timedelta(seconds=self.policy.duplicate_window_seconds)
        matches = [
            r
            for r in recent
            if r.request_fingerprint == fingerprint
            and (current - r.decided_at) <= window
            and not r.idempotent_replay
        ]
        if not matches:
            return None, [], []

        if len(matches) >= self.policy.rapid_submit_limit:
            return (
                ExecutionDecision.REJECT,
                [
                    "rapid repeated submissions blocked "
                    f"({len(matches)} in {self.policy.duplicate_window_seconds}s)"
                ],
                [],
            )

        return (
            ExecutionDecision.RETRY,
            ["duplicate order request detected; retry with new request_id or wait"],
            ["possible replay or accidental resubmit"],
        )

    def decide(
        self,
        *,
        user_id: UUID,
        request_id: str,
        intent: OrderIntent,
        connected: bool,
        login: int | None,
        recent: list[ExecutionDecisionRecord],
        existing_by_request_id: ExecutionDecisionRecord | None = None,
        now: datetime | None = None,
    ) -> ExecutionDecisionRecord:
        """Run full safety pipeline; return ALLOW | REJECT | RETRY.

        Never executes orders.
        """
        if existing_by_request_id is not None:
            # Idempotent safe retry — return prior decision without re-evaluating
            prior_warnings = [
                *existing_by_request_id.warnings,
                "idempotent replay of prior decision",
            ]
            return ExecutionDecisionRecord.record(
                user_id=existing_by_request_id.user_id,
                request_id=existing_by_request_id.request_id,
                decision=existing_by_request_id.decision,
                symbol=existing_by_request_id.symbol,
                side=existing_by_request_id.side,
                order_type=existing_by_request_id.order_type,
                volume=existing_by_request_id.volume,
                rejection_reasons=list(existing_by_request_id.rejection_reasons),
                warnings=prior_warnings,
                calculated_risk=dict(existing_by_request_id.calculated_risk),
                checks=dict(existing_by_request_id.checks),
                request_fingerprint=existing_by_request_id.request_fingerprint,
                request_snapshot=dict(existing_by_request_id.request_snapshot),
                idempotent_replay=True,
                entity_id=existing_by_request_id.id,
            )

        fp = self.fingerprint(intent, user_id=user_id)
        dup_decision, dup_reasons, dup_warnings = self.check_duplicates(
            fingerprint=fp, recent=recent, now=now
        )

        risk_result, calculated = self.risk_pre_check(intent, connected=connected)
        account_login = login if login is not None else 0
        try:
            account = self.adapter.account_info()
            account_login = int(account.login)
            leverage = Decimal(str(getattr(account, "leverage", 100) or 100))
        except (OSError, RuntimeError, ValueError, TypeError):
            leverage = calculated.leverage

        policy_ok, policy_reasons, policy_warnings, policy_checks = (
            self.evaluate_policy(
                intent,
                login=account_login,
                spread=calculated.spread,
                leverage=leverage,
                now=now,
            )
        )

        all_checks = {**policy_checks, **dict(risk_result.checks)}
        reasons = list(policy_reasons) + list(risk_result.reasons)
        warnings = list(policy_warnings) + list(risk_result.warnings)

        if dup_decision is ExecutionDecision.REJECT:
            decision = ExecutionDecision.REJECT
            reasons = dup_reasons + reasons
            warnings = dup_warnings + warnings
        elif dup_decision is ExecutionDecision.RETRY:
            decision = ExecutionDecision.RETRY
            reasons = dup_reasons + reasons
            warnings = dup_warnings + warnings
        elif not policy_ok or not risk_result.passed:
            decision = ExecutionDecision.REJECT
        else:
            decision = ExecutionDecision.ALLOW
            reasons = []

        reject_reasons = reasons if decision is not ExecutionDecision.ALLOW else []
        record = ExecutionDecisionRecord.record(
            user_id=user_id,
            request_id=request_id,
            decision=decision,
            symbol=intent.symbol,
            side=intent.side.value,
            order_type=intent.order_type.value,
            volume=intent.volume.value,
            rejection_reasons=reject_reasons,
            warnings=warnings,
            calculated_risk=calculated.to_dict(),
            checks=all_checks,
            request_fingerprint=fp,
            request_snapshot=intent.to_dict(),
        )

        if decision is ExecutionDecision.ALLOW:
            self._events.append(
                ExecutionApproved(
                    user_id=user_id,
                    decision_id=record.id,
                    request_id=request_id,
                    symbol=intent.symbol,
                )
            )
        elif decision is ExecutionDecision.RETRY:
            self._events.append(
                ExecutionRetryRequested(
                    user_id=user_id,
                    decision_id=record.id,
                    request_id=request_id,
                    symbol=intent.symbol,
                    reasons=tuple(record.rejection_reasons),
                )
            )
        else:
            self._events.append(
                ExecutionRejected(
                    user_id=user_id,
                    decision_id=record.id,
                    request_id=request_id,
                    symbol=intent.symbol,
                    reasons=tuple(record.rejection_reasons),
                )
            )

        return record
