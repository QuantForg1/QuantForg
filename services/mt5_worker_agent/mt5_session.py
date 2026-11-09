"""Real MetaTrader5 session helpers for one portable worker slot.

Passwords are never logged. Investor / read-only trade flags fail closed.
This module must only initialize against an isolated portable terminal path.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.mt5_worker_agent.paths import assert_worker_terminal_path

logger = logging.getLogger("quantforg.mt5_worker_agent.session")


@dataclass(frozen=True, slots=True)
class Mt5VerifyResult:
    ok: bool
    trade_allowed: bool
    login: int | None = None
    server: str = ""
    name: str = ""
    balance: float | None = None
    equity: float | None = None
    currency: str = ""
    error: str = ""


def _import_mt5() -> Any:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError(
            "MetaTrader5 package not available in this Python process"
        ) from exc
    return mt5


def initialize_portable(terminal_exe: Path | str) -> bool:
    path = assert_worker_terminal_path(terminal_exe)
    mt5 = _import_mt5()
    ok = bool(mt5.initialize(path=str(path)))
    err = mt5.last_error()
    logger.info(
        "mt5_portable_initialize ok=%s path=%s last_error=%s",
        ok,
        path,
        err,
    )
    return ok


def shutdown() -> None:
    try:
        mt5 = _import_mt5()
        mt5.shutdown()
    except Exception:
        logger.exception("mt5_shutdown_failed")


def authenticate_and_verify(
    *,
    terminal_exe: Path | str,
    login: int,
    password: str,
    server: str,
) -> Mt5VerifyResult:
    """Login on the isolated terminal and verify trade permissions.

    Never logs ``password``.
    """
    _ = password  # present for call signature clarity; not logged
    if not password.strip():
        return Mt5VerifyResult(ok=False, trade_allowed=False, error="password_required")
    path = assert_worker_terminal_path(terminal_exe)
    mt5 = _import_mt5()
    if not bool(mt5.initialize(path=str(path))):
        return Mt5VerifyResult(
            ok=False,
            trade_allowed=False,
            error=f"initialize_failed:{mt5.last_error()}",
        )
    try:
        logged_in = bool(
            mt5.login(login=int(login), password=password, server=server.strip())
        )
        if not logged_in:
            return Mt5VerifyResult(
                ok=False,
                trade_allowed=False,
                error=f"login_failed:{mt5.last_error()}",
            )
        info = mt5.account_info()
        term = mt5.terminal_info()
        if info is None:
            return Mt5VerifyResult(
                ok=False, trade_allowed=False, error="account_info_unavailable"
            )
        trade_allowed = bool(getattr(info, "trade_allowed", False))
        trade_expert = bool(getattr(info, "trade_expert", True))
        # Investor / read-only style accounts typically have trade_allowed False.
        if not trade_allowed:
            return Mt5VerifyResult(
                ok=False,
                trade_allowed=False,
                login=int(getattr(info, "login", login) or login),
                server=str(getattr(info, "server", server) or server),
                name=str(getattr(info, "name", "") or ""),
                error="investor_or_readonly_credentials_rejected",
            )
        if (
            term is not None
            and hasattr(term, "tradeapi_disabled")
            and bool(term.tradeapi_disabled)
        ):
            return Mt5VerifyResult(
                ok=False,
                trade_allowed=False,
                login=int(info.login),
                server=str(info.server or server),
                error="tradeapi_disabled",
            )
        logger.info(
            "mt5_verify_ok login=%s server=%s trade_allowed=%s trade_expert=%s",
            int(info.login),
            str(info.server or ""),
            trade_allowed,
            trade_expert,
        )
        return Mt5VerifyResult(
            ok=True,
            trade_allowed=True,
            login=int(info.login),
            server=str(info.server or server),
            name=str(info.name or ""),
            balance=float(info.balance),
            equity=float(info.equity),
            currency=str(getattr(info, "currency", "") or ""),
        )
    finally:
        # Leave terminal process running; detach Python IPC.
        try:
            mt5.shutdown()
        except Exception:
            logger.exception("mt5_detach_shutdown_failed")
