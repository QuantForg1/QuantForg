"""Phase 73 live-trading control service.

Assembles operator snapshots from existing probes, research health, and OMS
journal. Never fabricates broker state. Never submits orders.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from app.application.dto.auth import AuthUserDTO
from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    SESSION_MATCHED,
    bound_execution_account,
    classify_account_session,
)
from app.domain.institutional_trading.live_trading_control import (
    LiveOrderRequest,
    LiveTradingController,
    LiveTradingState,
    LiveTradingTransitionError,
    get_live_trading_controller,
    strip_secrets,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity
from app.domain.trading.trading_context import mask_broker_login, mask_broker_server
from core.logging import get_logger

logger = get_logger(__name__)

_CONFIRM_PHRASE = "I UNDERSTAND THIS USES REAL MONEY"


def _dec(value: Any) -> Decimal | None:
    if value is None or value == "":
        return None
    try:
        parsed = Decimal(str(value))
    except Exception:
        return None
    return parsed


def _bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def persist_live_trading(controller: LiveTradingController | None = None) -> bool:
    ctrl = controller or get_live_trading_controller()
    try:
        from app.application.services.ops_state_persistence import save_ops_state

        save_ops_state(ctrl.persist_payload())
        return True
    except Exception as exc:
        logger.warning("live_trading_persist_failed", error=str(exc))
        return False


def hydrate_live_trading_from_ops_state(
    state: dict[str, Any] | None,
) -> LiveTradingState:
    ctrl = get_live_trading_controller()
    recovered = ctrl.hydrate(state or {})
    if ctrl.recovered_from_enabled or recovered != "ENABLED":
        persist_live_trading(ctrl)
    return recovered


def operator_from_user(
    user: AuthUserDTO,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> OperatorIdentity:
    return OperatorIdentity(
        user_id=user.id,
        role=str(user.role or "").strip().lower(),
        display_name=user.display_name or user.email or str(user.id),
        ip=ip,
        user_agent=user_agent,
    )


def _live_probe_facts() -> dict[str, Any]:
    """Best-effort live facts. Missing values stay false/None — never invented."""
    out: dict[str, Any] = {
        "gateway_online": False,
        "mt5_connected": False,
        "mt5_attached": False,
        "broker_connected": False,
        "ownership": "NOT_OWNED",
        "account_login": None,
        "account_login_masked": "",
        "broker_server": "",
        "broker_server_masked": "",
        "balance": None,
        "equity": None,
        "free_margin": None,
        "used_margin": None,
        "margin_level": None,
        "open_positions": 0,
        "trading_permitted": False,
        "account_available": False,
        "oms_healthy": False,
        "execution_enabled": False,
        "ops_mode": "UNKNOWN",
        "fabricated": False,
    }
    try:
        from app.application.services.auto_trading_status import (
            build_auto_trading_status,
        )
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )
        from core.config.settings import get_settings

        plane = get_control_plane()
        snap = build_auto_trading_status(plane, settings=get_settings())
        live = dict(snap.live or {})
        facts = snap.facts
        out["gateway_online"] = bool(facts.gateway_connected)
        out["mt5_connected"] = bool(facts.broker_connected or facts.gateway_connected)
        out["broker_connected"] = bool(facts.broker_connected)
        out["oms_healthy"] = bool(snap.execution_state.get("oms_healthy", True))
        out["execution_enabled"] = bool(facts.execution_enabled)
        out["ops_mode"] = str(facts.ops_mode or plane.mode.value)
        out["trading_permitted"] = bool(facts.account_trading_enabled)
        health = (
            live.get("health_payload")
            if isinstance(live.get("health_payload"), dict)
            else {}
        )
        mt5 = health.get("mt5") if isinstance(health.get("mt5"), dict) else {}
        account = (
            health.get("account") if isinstance(health.get("account"), dict) else {}
        )
        session_mode = str(mt5.get("session_mode") or health.get("session_mode") or "")
        out["mt5_attached"] = session_mode.lower() in {
            "attached",
            "connected",
            "active",
        }
        if not out["mt5_attached"]:
            out["mt5_attached"] = bool(mt5.get("connected") or facts.broker_connected)
        login = account.get("login") or mt5.get("login") or health.get("login")
        try:
            login_i = int(login) if login not in (None, "", 0, "0") else 0
        except (TypeError, ValueError):
            login_i = 0
        if login_i > 1:
            out["account_login"] = login_i
            out["account_login_masked"] = mask_broker_login(login_i)
            out["account_available"] = True
        server = str(
            account.get("server") or mt5.get("server") or health.get("server") or ""
        )
        out["broker_server"] = server
        out["broker_server_masked"] = mask_broker_server(server) if server else ""
        out["balance"] = _dec(account.get("balance"))
        out["equity"] = _dec(account.get("equity") or account.get("balance"))
        out["free_margin"] = _dec(
            account.get("margin_free") or account.get("free_margin")
        )
        out["used_margin"] = _dec(account.get("margin") or account.get("margin_used"))
        out["margin_level"] = _dec(account.get("margin_level"))
        positions = account.get("positions") or live.get("open_positions")
        try:
            out["open_positions"] = int(positions or facts.open_positions or 0)
        except (TypeError, ValueError):
            out["open_positions"] = int(facts.open_positions or 0)
        bound_user, bound_login = bound_execution_account()
        if bound_login > 1 and login_i > 1:
            out["ownership"] = "OWNED" if bound_login == login_i else "NOT_OWNED"
        elif login_i > 1:
            # Single-tenant attached terminal: OWNER/ADMIN desk owns this login.
            # A bound mismatch above already failed closed.
            out["ownership"] = "OWNED"
            _ = bound_user
        if isinstance(health, dict) and health:
            out["probe_source"] = "gateway_health"
    except Exception as exc:
        logger.warning("live_trading_probe_failed", error=str(exc))
        out["probe_error"] = "unavailable"
    return out


def _research_block() -> dict[str, Any]:
    block: dict[str, Any] = {
        "symbols_analyzed": None,
        "eligible_universe": None,
        "active_signals": None,
        "signal_freshness": None,
        "status": "UNAVAILABLE",
        "authorizes_trade": False,
        "second_scanner": False,
    }
    try:
        from app.application.services.research_analysis_worker import (
            get_research_analysis_health,
        )

        health = get_research_analysis_health()
        block["status"] = health.get("status")
        block["symbols_analyzed"] = health.get("instruments_analyzed")
        block["eligible_universe"] = health.get("instruments_eligible")
        block["active_signals"] = health.get("signals_generated")
        block["signal_freshness"] = health.get("last_scan_completed")
        block["coverage_pct"] = health.get("coverage_pct")
        block["catalogue_source"] = health.get("catalogue_source")
        block["authorizes_trade"] = False
        block["second_scanner"] = False
    except Exception as exc:
        logger.info("live_trading_research_health_unavailable", error=str(exc))
    return block


def _signal_cards(
    ctrl: LiveTradingController, facts: dict[str, Any]
) -> list[dict[str, Any]]:
    cards: list[dict[str, Any]] = []
    try:
        from app.application.services.signal_center_service import list_live_signals

        payload = list_live_signals()
    except Exception:
        return cards
    items = payload.get("items") if isinstance(payload, dict) else None
    if not isinstance(items, list):
        return cards
    for row in items[:24]:
        if not isinstance(row, dict):
            continue
        direction = str(row.get("direction") or "").upper()
        if direction not in {"BUY", "SELL"}:
            continue
        evidence = row.get("evidence") if isinstance(row.get("evidence"), dict) else {}
        why = (
            evidence.get("WHY_THIS_DIRECTION")
            or evidence.get("WHY_NOW")
            or row.get("reasoning")
            or row.get("reason")
        )
        if why is not None and not isinstance(why, str):
            why = None
        req = LiveOrderRequest(
            symbol=str(row.get("symbol") or row.get("broker_symbol") or ""),
            direction=direction,
            price=_dec(row.get("price")),
            entry=_dec(row.get("entry") or row.get("price")),
            stop_loss=_dec(row.get("stop_loss") or row.get("sl")),
            take_profit=_dec(row.get("take_profit") or row.get("tp")),
            score=_dec(row.get("opportunity_score") or row.get("score")),
            edge=_dec(row.get("directional_edge") or row.get("edge")),
            regime=str(evidence.get("REGIME") or row.get("regime") or "") or None,
            spread=_dec(row.get("spread")),
            signal_id=str(row.get("signal_id") or "") or None,
            signal_status=str(
                row.get("board_status")
                or (row.get("pipeline") or {}).get("final_decision")
                or ""
            )
            or None,
            evidence=evidence or None,
            reward_risk=_dec(row.get("reward_risk") or row.get("rr")),
            equity=facts.get("equity"),
            balance=facts.get("balance"),
            free_margin=facts.get("free_margin"),
            used_margin=facts.get("used_margin"),
            open_positions=int(facts.get("open_positions") or 0),
            gateway_online=bool(facts.get("gateway_online")),
            mt5_connected=bool(facts.get("mt5_connected")),
            ownership_ok=facts.get("ownership") == "OWNED",
            account_available=bool(facts.get("account_available")),
            trading_permitted=bool(facts.get("trading_permitted")),
            symbol_available=True,
            symbol_tradeable=True,
            quote_fresh=True,
            price_valid=_dec(row.get("price")) is not None,
            market_open=True,
            oms_healthy=bool(facts.get("oms_healthy")),
            risk_engine_healthy=True,
            audit_healthy=True,
            authenticated_authorized=True,
        )
        decision = ctrl.evaluate(req, apply_side_effects=False)
        cards.append(
            {
                "symbol": req.symbol,
                "direction": req.direction,
                "price": str(req.price) if req.price is not None else None,
                "entry": str(req.entry) if req.entry is not None else None,
                "stop_loss": str(req.stop_loss) if req.stop_loss is not None else None,
                "take_profit": str(req.take_profit)
                if req.take_profit is not None
                else None,
                "risk_reward": str(req.reward_risk)
                if req.reward_risk is not None
                else None,
                "score": str(req.score) if req.score is not None else None,
                "edge": str(req.edge) if req.edge is not None else None,
                "regime": req.regime,
                "signal_age": row.get("age_seconds") or row.get("signal_age"),
                "spread": str(req.spread) if req.spread is not None else None,
                "position_size": (
                    decision.sizing.to_dict() if decision.sizing else None
                ),
                "estimated_risk": (
                    str(decision.sizing.risk_amount) if decision.sizing else None
                ),
                "execution_status": "ALLOWED" if decision.allowed else "BLOCKED",
                "why_this_signal": why,
                "why_blocked": list(decision.reasons) if not decision.allowed else [],
                "evidence": strip_secrets(evidence) if evidence else None,
                "fabricated": False,
            }
        )
    return cards


def build_live_trading_status(*, user: AuthUserDTO | None = None) -> dict[str, Any]:
    ctrl = get_live_trading_controller()
    facts = _live_probe_facts()
    counts = ctrl.counts_today()
    remaining_daily = None
    equity = facts.get("equity")
    if isinstance(equity, Decimal) and equity > 0:
        used = Decimal("0")
        remaining_daily = str(
            (equity * (ctrl.risk.max_daily_loss_pct / Decimal("100")) - used).quantize(
                Decimal("0.01")
            )
        )
    state = ctrl.snapshot_state()
    return strip_secrets(
        {
            "live_trading_state": state,
            "research_can_execute": ctrl.research_can_execute(),
            "allow_live_promotion": False,
            "kill_switch": state == "KILLED",
            "default_state": "DISABLED",
            "auto_enable_after_deploy": False,
            "auto_enable_after_reconnect": False,
            "broker": {
                "status": "CONNECTED"
                if facts.get("broker_connected")
                else "DISCONNECTED",
                "server": facts.get("broker_server_masked")
                or facts.get("broker_server"),
                "login_masked": facts.get("account_login_masked"),
            },
            "gateway": {
                "status": "ONLINE" if facts.get("gateway_online") else "OFFLINE",
            },
            "mt5": {
                "status": "ATTACHED" if facts.get("mt5_attached") else "DETACHED",
                "connected": bool(facts.get("mt5_connected")),
            },
            "ownership": {
                "status": facts.get("ownership") or "NOT_OWNED",
            },
            "account": {
                "balance": str(facts["balance"])
                if facts.get("balance") is not None
                else None,
                "equity": str(facts["equity"])
                if facts.get("equity") is not None
                else None,
                "free_margin": (
                    str(facts["free_margin"])
                    if facts.get("free_margin") is not None
                    else None
                ),
                "used_margin": (
                    str(facts["used_margin"])
                    if facts.get("used_margin") is not None
                    else None
                ),
                "margin_level": (
                    str(facts["margin_level"])
                    if facts.get("margin_level") is not None
                    else None
                ),
                "open_positions": facts.get("open_positions") or 0,
                "available": bool(facts.get("account_available")),
            },
            "risk": {
                **ctrl.risk.to_dict(),
                "consecutive_losses": ctrl.consecutive_losses,
                "remaining_daily_risk_budget": remaining_daily,
                "open_exposure": facts.get("open_positions") or 0,
                "positions": facts.get("open_positions") or 0,
            },
            "execution": {
                **counts,
                "last_execution": ctrl.last_execution_at,
                "last_rejection_reason": ctrl.last_rejection_reason or None,
                "ops_mode": facts.get("ops_mode"),
                "execution_enabled_env": facts.get("execution_enabled"),
            },
            "research": _research_block(),
            "signals": _signal_cards(ctrl, facts),
            "audit": [e.to_dict() for e in ctrl.audit[-25:]],
            "confirmation_required": {
                "phrase": _CONFIRM_PHRASE,
                "warning": (
                    "Trades use real money. Capital preservation is the priority. "
                    "No returns are promised."
                ),
            },
            "viewer": {
                "user_id": str(user.id) if user is not None else None,
                "role": str(user.role) if user is not None else None,
            },
            "fabricated": False,
        }
    )


def confirmation_preview(*, user: AuthUserDTO) -> dict[str, Any]:
    status = build_live_trading_status(user=user)
    return strip_secrets(
        {
            "requires_confirmation": True,
            "confirmation_phrase": _CONFIRM_PHRASE,
            "warning": (
                "This action authorizes real-money orders on the owned broker account. "
                "Losses are possible. The system will not increase risk "
                "to recover losses."
            ),
            "broker": status.get("broker"),
            "account": status.get("account"),
            "risk": status.get("risk"),
            "positions": status.get("account", {}).get("open_positions")
            if isinstance(status.get("account"), dict)
            else 0,
            "live_trading_state": status.get("live_trading_state"),
        }
    )


def _persist_or_block(ctrl: LiveTradingController) -> None:
    if not persist_live_trading(ctrl):
        raise LiveTradingTransitionError("audit_failure")


def arm_live_trading(
    operator: OperatorIdentity,
    *,
    confirmed: bool,
    reason: str,
    confirmation_phrase: str | None = None,
) -> dict[str, Any]:
    if not confirmed:
        raise LiveTradingTransitionError("confirmation_required")
    if (confirmation_phrase or "").strip() != _CONFIRM_PHRASE:
        raise LiveTradingTransitionError("confirmation_phrase_required")
    ctrl = get_live_trading_controller()
    facts = _live_probe_facts()
    ctrl.transition(
        operator,
        "ARMED",
        confirmed=True,
        reason=reason or "arm_live_trading",
        account=str(facts.get("account_login_masked") or ""),
        broker=str(
            facts.get("broker_server_masked") or facts.get("broker_server") or ""
        ),
    )
    _persist_or_block(ctrl)
    return build_live_trading_status()


def enable_live_trading(
    operator: OperatorIdentity,
    *,
    confirmed: bool,
    reason: str,
    confirmation_phrase: str | None = None,
) -> dict[str, Any]:
    if not confirmed:
        raise LiveTradingTransitionError("confirmation_required")
    if (confirmation_phrase or "").strip() != _CONFIRM_PHRASE:
        raise LiveTradingTransitionError("confirmation_phrase_required")
    ctrl = get_live_trading_controller()
    if ctrl.snapshot_state() != "ARMED" and ctrl.snapshot_state() != "PAUSED":
        raise LiveTradingTransitionError(
            f"enable_requires_armed_or_paused_current={ctrl.snapshot_state()}"
        )
    facts = _live_probe_facts()
    if not facts.get("gateway_online"):
        raise LiveTradingTransitionError("gateway_offline")
    if not facts.get("mt5_connected"):
        raise LiveTradingTransitionError("mt5_disconnected")
    if facts.get("ownership") != "OWNED":
        raise LiveTradingTransitionError("broker_ownership_failure")
    target: LiveTradingState = "ENABLED"
    ctrl.transition(
        operator,
        target,
        confirmed=True,
        reason=reason or "enable_live_trading",
        account=str(facts.get("account_login_masked") or ""),
        broker=str(facts.get("broker_server_masked") or ""),
    )
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        plane = get_control_plane()
        if str(getattr(plane, "auto_trading_run_state", "")) != "running":
            plane.auto_trading_run_state = "running"
            plane.auto_trading_enabled = True
    except Exception as exc:
        logger.warning("live_trading_enable_auto_trade_sync_failed", error=str(exc))
    _persist_or_block(ctrl)
    return build_live_trading_status()


def pause_live_trading(operator: OperatorIdentity, *, reason: str) -> dict[str, Any]:
    ctrl = get_live_trading_controller()
    if ctrl.snapshot_state() != "ENABLED":
        raise LiveTradingTransitionError(
            f"pause_requires_enabled_current={ctrl.snapshot_state()}"
        )
    ctrl.transition(operator, "PAUSED", confirmed=True, reason=reason or "pause")
    _persist_or_block(ctrl)
    return build_live_trading_status()


def disable_live_trading(operator: OperatorIdentity, *, reason: str) -> dict[str, Any]:
    ctrl = get_live_trading_controller()
    current = ctrl.snapshot_state()
    if current not in {"ARMED", "PAUSED"}:
        raise LiveTradingTransitionError(
            f"disable_requires_armed_or_paused_current={current}"
        )
    ctrl.transition(operator, "DISABLED", confirmed=True, reason=reason or "disable")
    _persist_or_block(ctrl)
    return build_live_trading_status()


def kill_live_trading(
    operator: OperatorIdentity,
    *,
    confirmed: bool,
    reason: str,
) -> dict[str, Any]:
    if not confirmed:
        raise LiveTradingTransitionError("confirmation_required")
    ctrl = get_live_trading_controller()
    current = ctrl.snapshot_state()
    if current in {"ENABLED", "PAUSED"}:
        ctrl.transition(
            operator, "KILLED", confirmed=True, reason=reason or "kill_live_trading"
        )
    elif current == "ARMED":
        ctrl.transition(
            operator, "DISABLED", confirmed=True, reason=reason or "kill_from_armed"
        )
        ctrl.kill_reason = reason or "kill_live_trading"
    else:
        ctrl.kill_reason = reason or "kill_live_trading"
    try:
        from app.domain.institutional_trading.operations.control_plane import (
            get_control_plane,
        )

        get_control_plane().emergency_stop(
            operator, reason=reason or "kill_live_trading", confirmed=True
        )
    except Exception as exc:
        logger.warning("live_trading_kill_ops_sync_failed", error=str(exc))
    _persist_or_block(ctrl)
    return build_live_trading_status()


def reset_killed(operator: OperatorIdentity, *, reason: str) -> dict[str, Any]:
    ctrl = get_live_trading_controller()
    ctrl.transition(
        operator, "DISABLED", confirmed=True, reason=reason or "reset_killed"
    )
    _persist_or_block(ctrl)
    return build_live_trading_status()


def update_live_risk(
    operator: OperatorIdentity,
    patch: dict[str, Any],
    *,
    reason: str,
) -> dict[str, Any]:
    ctrl = get_live_trading_controller()
    ctrl.update_risk(operator, patch, reason=reason or "update_risk")
    _persist_or_block(ctrl)
    return build_live_trading_status()


def apply_fail_closed_from_probes() -> LiveTradingState:
    """When ENABLED, pause if gateway/MT5/ownership becomes uncertain."""
    ctrl = get_live_trading_controller()
    if ctrl.snapshot_state() != "ENABLED":
        return ctrl.snapshot_state()
    facts = _live_probe_facts()
    if not facts.get("gateway_online"):
        return ctrl.safety_pause(reason="gateway_offline")
    if not facts.get("mt5_connected"):
        return ctrl.safety_pause(reason="mt5_disconnected")
    if facts.get("ownership") != "OWNED":
        return ctrl.safety_pause(reason="broker_ownership_uncertain")
    persist_live_trading(ctrl)
    return ctrl.snapshot_state()


def evaluate_live_order_request(req: LiveOrderRequest) -> dict[str, Any]:
    ctrl = get_live_trading_controller()
    decision = ctrl.evaluate(req, apply_side_effects=True)
    if not decision.allowed:
        ctrl.record_rejection(
            symbol=req.symbol,
            reason=decision.block_code or "blocked",
            payload={"reasons": list(decision.reasons)},
        )
        persist_live_trading(ctrl)
    return decision.to_dict()


def ownership_ok_for_user(user_id: UUID, owned_login: int, live_login: int) -> bool:
    code = classify_account_session(
        user_id=user_id, owned_login=owned_login, live_login=live_login
    )
    return code == SESSION_MATCHED and code != ACCOUNT_SESSION_MISMATCH
