"""Live Auto Trading certification service — probes facts; never fabricates fills."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from threading import Lock
from typing import Any

from app.domain.institutional_trading.auto_trading import AutoTradeLiveFacts
from app.domain.institutional_trading.live_certification import (
    DEMO_CERT_MAX_POSITIONS,
    DEMO_CERT_VOLUME,
    LiveCertificationReport,
    LiveTradeEvidence,
    build_stage_results,
    certify_or_stop,
    evaluate_live_cert_checklist,
)
from app.domain.institutional_trading.operations.control_plane import (
    OperationsControlPlane,
    get_control_plane,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity
from core.config.settings import get_settings
from core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class LiveAutoTradeCertificationService:
    """Operator-facing certification. Never auto-switches SHADOW→LIVE."""

    plane: OperationsControlPlane = field(default_factory=get_control_plane)
    _last_report: LiveCertificationReport | None = field(default=None, repr=False)
    _lock: Lock = field(default_factory=Lock, repr=False)

    def checklist_from_facts(
        self,
        facts: AutoTradeLiveFacts,
        *,
        mt5_logged_in: bool = False,
        exposure_pass: bool = False,
        drawdown_pass: bool = False,
        account_is_demo: bool = False,
    ) -> dict[str, Any]:
        policy = self.plane.auto_trade_policy()
        result = evaluate_live_cert_checklist(
            facts=facts,
            policy=policy,
            mt5_logged_in=mt5_logged_in,
            exposure_pass=exposure_pass,
            drawdown_pass=drawdown_pass,
            account_is_demo=account_is_demo,
        )
        return result.to_dict()

    def probe_local_environment(self) -> dict[str, Any]:
        """Read-only environment probe — no order_send."""
        settings = get_settings()
        gateway = bool((getattr(settings, "mt5_gateway_base_url", None) or "").strip())
        execution = bool(getattr(settings, "execution_enabled", False))
        health = self.plane.health.latest()
        facts = AutoTradeLiveFacts(
            gateway_connected=bool(health and health.gateway_available) and gateway,
            broker_connected=bool(health and health.mt5_connected),
            market_data_live=False,
            risk_engine_pass=False,
            account_trading_enabled=False,
            mt5_autotrading_enabled=False,
            symbol_tradable=False,
            margin_available=False,
            no_broker_restrictions=False,
            open_positions=0,
            session="off_hours",
            spread=None,
            news_blocked=False,
            daily_loss_exceeded=self.plane.daily_loss_exceeded,
            emergency_stop=self.plane.kill_switch_armed,
            ops_mode=self.plane.mode.value,
            execution_enabled=execution,
        )
        checklist = evaluate_live_cert_checklist(
            facts=facts,
            policy=self.plane.auto_trade_policy(),
            mt5_logged_in=False,
            exposure_pass=False,
            drawdown_pass=False,
            account_is_demo=False,
        )
        return {
            "mt5_gateway_configured": gateway,
            "execution_enabled": execution,
            "ops_mode": self.plane.mode.value,
            "auto_trading_enabled": self.plane.auto_trading_enabled,
            "kill_switch": self.plane.kill_switch_armed,
            "demo_volume": str(DEMO_CERT_VOLUME),
            "demo_max_positions": DEMO_CERT_MAX_POSITIONS,
            "checklist": checklist.to_dict(),
            "can_attempt_broker_trade": False,
            "blocker": (
                None
                if checklist.ready
                else ("; ".join(checklist.failed_reasons) or "Live conditions failed")
            ),
            "mode_policy": {
                "shadow_to_live": "operator_only",
                "never_automatic": True,
            },
        }

    def run_certification_attempt(
        self,
        operator: OperatorIdentity,
        *,
        facts: AutoTradeLiveFacts,
        mt5_logged_in: bool,
        exposure_pass: bool,
        drawdown_pass: bool,
        account_is_demo: bool,
        trade: LiveTradeEvidence | None,
        stage_completed: dict[str, bool] | None = None,
        reason: str = "live auto trading certification attempt",
    ) -> LiveCertificationReport:
        """Attempt certification. Never fabricates fills. Never auto-switches mode."""
        checklist = evaluate_live_cert_checklist(
            facts=facts,
            policy=self.plane.auto_trade_policy(),
            mt5_logged_in=mt5_logged_in,
            exposure_pass=exposure_pass,
            drawdown_pass=drawdown_pass,
            account_is_demo=account_is_demo,
        )
        stages = build_stage_results(completed=stage_completed or {})
        report = certify_or_stop(checklist=checklist, stages=stages, trade=trade)

        if not report.certified:
            disabled = False
            if self.plane.auto_trading_enabled:
                try:
                    self.plane.update_auto_trade_controls(
                        operator,
                        enabled=False,
                        reason=(
                            "certification failure — auto trading disabled: "
                            f"{report.failure_reason or reason}"
                        ),
                    )
                    disabled = True
                except Exception as exc:
                    logger.exception(
                        "certification_disable_auto_trading_failed", error=str(exc)
                    )
            report = replace(
                report,
                auto_trading_disabled_on_failure=(
                    report.auto_trading_disabled_on_failure or disabled
                ),
                mode_auto_switched=False,
            )
            self.plane.audit.record(
                operator=operator,
                action="live_auto_trade_certification_failed",
                old_value="",
                new_value=report.status,
                reason=report.failure_reason or reason,
                now=datetime.now(UTC),
            )
        else:
            self.plane.audit.record(
                operator=operator,
                action="live_auto_trade_certification_passed",
                old_value="",
                new_value=str(report.id),
                reason=reason,
                now=datetime.now(UTC),
            )

        with self._lock:
            self._last_report = report
        return report

    def last_report(self) -> LiveCertificationReport | None:
        with self._lock:
            return self._last_report


_SERVICE: LiveAutoTradeCertificationService | None = None
_SERVICE_LOCK = Lock()


def get_live_cert_service() -> LiveAutoTradeCertificationService:
    global _SERVICE
    with _SERVICE_LOCK:
        if _SERVICE is None:
            _SERVICE = LiveAutoTradeCertificationService()
        return _SERVICE


def reset_live_cert_service_for_tests() -> LiveAutoTradeCertificationService:
    global _SERVICE
    with _SERVICE_LOCK:
        _SERVICE = LiveAutoTradeCertificationService()
        return _SERVICE
