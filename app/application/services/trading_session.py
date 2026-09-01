"""Resolve the authenticated user's trading session from existing runtime pieces.

Does not create a second engine, gateway, or scanner. Traders may start/stop
the robot for their own live connection via CONTROL_OWN_ROBOT. Owner/admin
global ITE ops remain on the existing control plane.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, replace
from typing import Any
from uuid import UUID

from app.application.services.account_execution_gate import (
    ACCOUNT_SESSION_MISMATCH,
    bind_execution_account,
    bound_execution_account,
    classify_account_session,
)
from app.application.services.institutional_ite_runtime import get_ite_runtime
from app.application.services.mt5_session_guard import ensure_live_mt5_session_for_user
from app.domain.exceptions.auth import AuthorizationError
from app.domain.exceptions.base import ConflictError, NotFoundError, ValidationError
from app.domain.institutional_trading.operations.control_plane import (
    PermissionDenied,
    get_control_plane,
)
from app.domain.institutional_trading.operations.models import OperatorIdentity
from app.domain.trading.trading_context import (
    TradingContext,
    mask_broker_login,
    mask_broker_server,
)
from app.infrastructure.brokers.mt5.adapter import MT5Adapter
from core.logging import get_logger

logger = get_logger(__name__)


def _ux_state(
    *,
    owned: bool,
    session_code: str,
    robot: str,
    catalogue_unavailable: bool,
) -> str:
    if session_code == ACCOUNT_SESSION_MISMATCH:
        return "SESSION_MISMATCH"
    if not owned:
        return "NO_BROKER"
    if robot == "Running":
        return "ROBOT_RUNNING"
    if robot == "Paused":
        return "ROBOT_PAUSED"
    if robot == "Error":
        return "ATTENTION"
    if catalogue_unavailable:
        return "CATALOGUE_UNAVAILABLE"
    return "ROBOT_READY"


def _live_trading_session_fields() -> dict[str, Any]:
    """Backend live-trading controller is authoritative for order submission."""
    try:
        from app.domain.institutional_trading.live_trading_control import (
            get_live_trading_controller,
            orders_may_submit,
            public_authorization_state,
        )

        state = get_live_trading_controller().snapshot_state()
        may_submit = orders_may_submit(state)
        return {
            "live_trading_state": state,
            "orders_may_submit": may_submit,
            "live_authorization": public_authorization_state(
                state, orders_may_submit_flag=may_submit
            ),
        }
    except Exception:
        return {
            "live_trading_state": "UNAVAILABLE",
            "orders_may_submit": False,
            "live_authorization": "LIVE_DISABLED",
        }


def _robot_status(
    *,
    owned: bool,
    run_state: str,
    runtime_user: UUID | None,
    user_id: UUID,
) -> str:
    if not owned:
        return "Stopped"
    if runtime_user is not None and runtime_user != user_id:
        return "Stopped"
    state = (run_state or "off").strip().lower()
    if state == "running":
        return "Running"
    if state == "paused":
        return "Paused"
    if state in {"error", "fault"}:
        return "Error"
    if owned:
        return "Stopped"
    return "Stopped"


def resolve_trading_context(
    *,
    user_id: UUID,
    connection: Any | None,
    run_state: str = "off",
    trading_enabled: bool = False,
    runtime_user_id: UUID | None = None,
) -> TradingContext:
    owned = connection is not None and bool(getattr(connection, "connected", False))
    login = int(getattr(connection, "login", 0) or 0) if connection is not None else 0
    server = (
        str(getattr(connection, "server", "") or "") if connection is not None else ""
    )
    conn_id = getattr(connection, "id", None) if connection is not None else None
    robot = _robot_status(
        owned=owned,
        run_state=run_state,
        runtime_user=runtime_user_id,
        user_id=user_id,
    )
    if not owned:
        connection_status = "NOT_CONNECTED"
    elif robot == "Running":
        connection_status = "RUNNING"
    elif robot == "Error":
        connection_status = "DEGRADED"
    else:
        connection_status = "CONNECTED"
    return TradingContext(
        authenticated_user_id=user_id,
        broker_connection_id=conn_id if isinstance(conn_id, UUID) else None,
        broker_account_id=mask_broker_login(login) if owned else "",
        broker_server=mask_broker_server(server) if owned else "",
        connection_status=connection_status,
        robot_status=robot,
        trading_enabled=bool(trading_enabled) and owned and robot == "Running",
        execution_permitted=owned and robot == "Running",
    )


@dataclass(frozen=True, slots=True)
class GetTradingSessionUseCase:
    uow_factory: Any
    adapter: MT5Adapter

    async def execute(self, *, user_id: UUID) -> dict[str, Any]:
        try:
            connection = await asyncio.wait_for(
                ensure_live_mt5_session_for_user(
                    self.uow_factory, self.adapter, user_id
                ),
                timeout=4.0,
            )
        except TimeoutError:
            logger.warning(
                "trading_session_ensure_timeout",
                user_id=str(user_id),
            )
            connection = None
        except Exception as exc:
            logger.warning(
                "trading_session_ensure_failed",
                user_id=str(user_id),
                error=str(exc),
            )
            connection = None
        plane = get_control_plane()
        bound_user, _bound_login = bound_execution_account()
        ctx = resolve_trading_context(
            user_id=user_id,
            connection=connection,
            run_state=str(getattr(plane, "auto_trading_run_state", "off") or "off"),
            trading_enabled=bool(getattr(plane, "auto_trading_enabled", False)),
            runtime_user_id=bound_user,
        )
        balance = None
        equity = None
        margin = None
        free_margin = None
        currency = ""
        leverage = None
        live_login = 0
        owned_login = int(getattr(connection, "login", 0) or 0) if connection else 0
        session_code = "NOT_CONNECTED"
        if connection is not None and connection.connected:
            try:
                try:
                    info = await asyncio.wait_for(
                        asyncio.to_thread(self.adapter.account_info),
                        timeout=3.0,
                    )
                except TimeoutError:
                    logger.info(
                        "trading_session_account_probe_timeout",
                        user_id=str(user_id),
                    )
                    info = None
                if info is None:
                    raise RuntimeError("account_info_unavailable")
                live_login = int(getattr(info, "login", 0) or 0)
                if live_login > 1 and owned_login > 1 and live_login == owned_login:
                    balance = str(getattr(info, "balance", "") or "")
                    equity = str(getattr(info, "equity", "") or "")
                    margin = str(getattr(info, "margin", "") or "")
                    free_margin = str(getattr(info, "free_margin", "") or "")
                    currency = str(getattr(info, "currency", "") or "")
                    lev = getattr(info, "leverage", None)
                    leverage = int(lev) if lev is not None else None
            except Exception:
                logger.info(
                    "trading_session_account_probe_failed",
                    user_id=str(user_id),
                )
            session_code = classify_account_session(
                user_id=user_id,
                owned_login=owned_login,
                live_login=live_login,
            )
        if session_code == ACCOUNT_SESSION_MISMATCH:
            ctx = replace(
                ctx,
                connection_status="DEGRADED",
                robot_status="Stopped",
                trading_enabled=False,
                execution_permitted=False,
            )
        catalogue_source = None
        catalogue_unavailable = True
        catalogue_last_error = None
        execution_universe_mode = None
        if ctx.connected and session_code != ACCOUNT_SESSION_MISMATCH:
            try:
                from app.domain.market_universe.broker_catalogue import (
                    discover_live_catalogue,
                )
                from app.domain.market_universe.constants import (
                    CATALOGUE_LIVE_BROKER,
                )
                from app.domain.trading.execution_universe import (
                    execution_universe_diagnostics,
                )

                # Markets / Signals research catalogue — not the gold-only
                # execution lock. Execution mode is reported separately.
                # Cap catalogue probing so a slow MT5 listing cannot stall
                # the whole trading-session endpoint (dashboard/signals).
                try:
                    research = await asyncio.wait_for(
                        asyncio.to_thread(discover_live_catalogue, self.adapter),
                        timeout=2.5,
                    )
                except TimeoutError:
                    research = {
                        "catalogue_source": "UNAVAILABLE",
                        "error": "catalogue_diagnostics_timeout",
                    }
                catalogue_source = str(research.get("catalogue_source") or "")
                catalogue_unavailable = catalogue_source != CATALOGUE_LIVE_BROKER
                catalogue_last_error = research.get("error")
                exec_diag = execution_universe_diagnostics(mt5_adapter=self.adapter)
                execution_universe_mode = exec_diag.get("execution_universe_mode")
            except Exception:
                catalogue_source = "UNAVAILABLE"
                catalogue_unavailable = True
                catalogue_last_error = "catalogue_diagnostics_failed"
        owned = connection is not None and bool(
            getattr(connection, "connected", False)
        )
        ux = _ux_state(
            owned=owned,
            session_code=session_code,
            robot=ctx.robot_status,
            catalogue_unavailable=catalogue_unavailable if owned else True,
        )
        last_verified = None
        if connection is not None:
            stamp = getattr(connection, "last_heartbeat_at", None) or getattr(
                connection, "updated_at", None
            )
            if stamp is not None:
                last_verified = (
                    stamp.isoformat() if hasattr(stamp, "isoformat") else str(stamp)
                )
        account_unavailable = bool(
            owned
            and session_code != ACCOUNT_SESSION_MISMATCH
            and balance is None
        )
        if session_code == ACCOUNT_SESSION_MISMATCH:
            robot_blocked_reason = ACCOUNT_SESSION_MISMATCH
        elif not owned:
            robot_blocked_reason = "BROKER_NOT_CONNECTED"
        else:
            robot_blocked_reason = None
        logger.info(
            "trading_session_status",
            user_id=str(user_id),
            broker_connection_id=str(ctx.broker_connection_id or ""),
            connection_status=ctx.connection_status,
            robot_status=ctx.robot_status,
            session_code=session_code,
        )
        lt_fields = _live_trading_session_fields()
        return {
            "broker": "Connected" if ctx.connected else "Disconnected",
            "account": ctx.broker_account_id or "—",
            "server": ctx.broker_server or "—",
            "connection": (
                "Healthy"
                if ctx.connection_status in {"CONNECTED", "RUNNING"}
                and session_code != ACCOUNT_SESSION_MISMATCH
                else "Disconnected"
                if ctx.connection_status == "NOT_CONNECTED"
                else "Degraded"
            ),
            "robot": ctx.robot_status,
            "trading": (
                "Enabled"
                if ctx.trading_enabled and lt_fields["orders_may_submit"]
                else "Disabled"
            ),
            "live_trading_state": lt_fields["live_trading_state"],
            "live_authorization": (
                lt_fields.get("live_authorization") or "LIVE_DISABLED"
            ),
            "orders_may_submit": bool(
                lt_fields["orders_may_submit"]
                and ctx.execution_permitted
                and session_code != ACCOUNT_SESSION_MISMATCH
            ),
            "connection_status": ctx.connection_status,
            "execution_permitted": ctx.execution_permitted
            and session_code != ACCOUNT_SESSION_MISMATCH,
            "broker_connection_id": str(ctx.broker_connection_id)
            if ctx.broker_connection_id
            else None,
            "balance": balance,
            "equity": equity,
            "margin": margin,
            "free_margin": free_margin,
            "currency": currency,
            "leverage": leverage,
            "ux_state": ux,
            "session_code": session_code,
            "catalogue_source": catalogue_source,
            "catalogue_unavailable": catalogue_unavailable,
            "catalogue_last_error": catalogue_last_error,
            "execution_universe_mode": execution_universe_mode,
            "account_unavailable": account_unavailable,
            "last_verified": last_verified,
            "robot_blocked_reason": robot_blocked_reason,
            "concurrent_live_sessions_supported": False,
            "authenticated": True,
            "owned": bool(owned and session_code != ACCOUNT_SESSION_MISMATCH),
            "ownership": (
                "owned"
                if owned and session_code != ACCOUNT_SESSION_MISMATCH
                else "none"
            ),
        }


@dataclass(frozen=True, slots=True)
class ControlTradingRobotUseCase:
    uow_factory: Any
    adapter: MT5Adapter

    async def execute(
        self,
        *,
        user_id: UUID,
        role: str,
        display_name: str,
        action: str,
        ip: str = "",
        user_agent: str = "",
    ) -> dict[str, Any]:
        connection = await ensure_live_mt5_session_for_user(
            self.uow_factory, self.adapter, user_id
        )
        if connection is None or not connection.connected:
            raise NotFoundError(
                "No active broker connection for this account",
                code="BROKER_NOT_CONNECTED",
                details={"reason": "not_connected"},
            )
        action_norm = action.strip().lower()
        run_state = {"start": "running", "pause": "paused", "stop": "off"}.get(
            action_norm
        )
        if run_state is None:
            raise ValidationError(
                "Unknown robot action",
                details={"action": action},
            )
        bound_user, _bound_login = bound_execution_account()
        if bound_user is not None and bound_user != user_id:
            raise ConflictError(
                "Your trading session needs to be reconnected",
                code="account_session_mismatch",
                details={"reason": ACCOUNT_SESSION_MISMATCH},
            )
        operator = OperatorIdentity(
            user_id=user_id,
            role=str(role or "").strip().lower(),
            display_name=display_name or str(user_id),
            ip=ip or None,
            user_agent=user_agent or None,
        )
        plane = get_control_plane()
        try:
            plane.set_owned_account_run_state(
                operator,
                run_state=run_state,
                reason=f"trading_session_robot_{action_norm}",
            )
        except PermissionDenied as exc:
            logger.warning(
                "trading_robot_control_denied",
                user_id=str(user_id),
                action=action_norm,
            )
            raise AuthorizationError(
                "Insufficient role for robot control",
                code="insufficient_role",
                details={"action": action_norm, "user_id": str(user_id)},
            ) from exc
        runtime = get_ite_runtime()
        if runtime is not None and action_norm == "start":
            runtime.user_id = user_id
        if action_norm == "start":
            bind_execution_account(user_id=user_id, login=int(connection.login or 0))
        logger.info(
            "trading_robot_control",
            user_id=str(user_id),
            action=action_norm,
            broker_connection_id=str(getattr(connection, "id", "")),
        )
        return await GetTradingSessionUseCase(
            uow_factory=self.uow_factory, adapter=self.adapter
        ).execute(user_id=user_id)
