"""Application service for QuantForg AI Trading Robot V1."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from app.domain.ai_trading_robot import RobotEvaluateInput, RobotV1Orchestrator
from app.domain.ai_trading_robot.config import DEFAULT_ROBOT_CONFIG, RobotV1Config
from app.domain.ai_trading_robot.journal_intelligence import JournalTradeView


def _dec(value: Any, default: str = "0") -> Decimal:
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal(default)


class AiTradingRobotService:
    """Thin application facade — evaluate / status / reports only."""

    def __init__(self, config: RobotV1Config | None = None) -> None:
        self._robot = RobotV1Orchestrator(config or DEFAULT_ROBOT_CONFIG)

    def status(self) -> dict[str, object]:
        return self._robot.status()

    def evaluate(self, payload: dict[str, Any]) -> dict[str, object]:
        journal_raw = payload.get("journal_trades") or []
        journal: list[JournalTradeView] = []
        if isinstance(journal_raw, list):
            for row in journal_raw:
                if not isinstance(row, dict):
                    continue
                journal.append(
                    JournalTradeView(
                        symbol=str(row.get("symbol") or "XAUUSD"),
                        side=str(row.get("side") or "buy"),
                        pnl=_dec(row.get("pnl") or row.get("profit")),
                        session=(
                            str(row["session"]) if row.get("session") else None
                        ),
                        strategy_id=(
                            str(row["strategy_id"])
                            if row.get("strategy_id")
                            else None
                        ),
                        r_multiple=(
                            _dec(row["r_multiple"])
                            if row.get("r_multiple") is not None
                            else None
                        ),
                        exit_reason=(
                            str(row["exit_reason"])
                            if row.get("exit_reason")
                            else None
                        ),
                    )
                )

        closed_raw = payload.get("closed_pnls") or []
        closed_pnls: tuple[Decimal, ...] = ()
        if isinstance(closed_raw, list):
            closed_pnls = tuple(_dec(x) for x in closed_raw)
        r_raw = payload.get("r_multiples") or []
        r_multiples: tuple[Decimal, ...] = ()
        if isinstance(r_raw, list):
            r_multiples = tuple(_dec(x) for x in r_raw)

        risk = payload.get("risk_engine_passed")
        safety = payload.get("safety_engine_passed")
        risk_bool = None if risk is None else bool(risk)
        safety_bool = None if safety is None else bool(safety)

        inp = RobotEvaluateInput(
            side=str(payload.get("side") or "buy"),
            signal_present=bool(payload.get("signal_present", True)),
            strategy_id=str(payload.get("strategy_id") or "default"),
            strategy_valid=bool(payload.get("strategy_valid", True)),
            technique=(
                str(payload["technique"]) if payload.get("technique") else None
            ),
            equity=_dec(payload.get("equity"), "10000"),
            stop_distance=_dec(payload.get("stop_distance"), "5"),
            spread=(
                _dec(payload["spread"])
                if payload.get("spread") is not None
                else None
            ),
            atr=_dec(payload["atr"]) if payload.get("atr") is not None else None,
            price=(
                _dec(payload["price"])
                if payload.get("price") is not None
                else None
            ),
            daily_drawdown_pct=_dec(payload.get("daily_drawdown_pct")),
            consecutive_losses=int(payload.get("consecutive_losses") or 0),
            cooldown_active=bool(payload.get("cooldown_active", False)),
            confluence=(
                _dec(payload["confluence"])
                if payload.get("confluence") is not None
                else None
            ),
            trade_quality=(
                _dec(payload["trade_quality"])
                if payload.get("trade_quality") is not None
                else None
            ),
            structure_bias_aligned=(
                bool(payload["structure_bias_aligned"])
                if payload.get("structure_bias_aligned") is not None
                else None
            ),
            closed_pnls=closed_pnls,
            r_multiples=r_multiples,
            journal_trades=tuple(journal),
            open_side=(
                str(payload["open_side"]) if payload.get("open_side") else None
            ),
            open_unrealized_pnl=(
                _dec(payload["open_unrealized_pnl"])
                if payload.get("open_unrealized_pnl") is not None
                else None
            ),
            risk_engine_passed=risk_bool,
            safety_engine_passed=safety_bool,
        )
        return self._robot.evaluate(inp).to_dict()

    def self_analysis(self, payload: dict[str, Any] | None = None) -> dict[str, object]:
        body = payload or {}
        journal_raw = body.get("journal_trades") or []
        journal: list[JournalTradeView] = []
        if isinstance(journal_raw, list):
            for row in journal_raw:
                if not isinstance(row, dict):
                    continue
                journal.append(
                    JournalTradeView(
                        symbol=str(row.get("symbol") or "XAUUSD"),
                        side=str(row.get("side") or "buy"),
                        pnl=_dec(row.get("pnl") or row.get("profit")),
                        session=(
                            str(row["session"]) if row.get("session") else None
                        ),
                        strategy_id=(
                            str(row["strategy_id"])
                            if row.get("strategy_id")
                            else None
                        ),
                    )
                )
        closed_raw = body.get("closed_pnls") or []
        closed = [_dec(x) for x in closed_raw] if isinstance(closed_raw, list) else []
        report = self._robot.self_analysis(
            journal_trades=journal,
            closed_pnls=closed,
            strategy_id=str(body.get("strategy_id") or "default"),
        )
        return report.to_dict()
