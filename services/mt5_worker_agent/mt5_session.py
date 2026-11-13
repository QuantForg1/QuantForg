"""Real MetaTrader5 session helpers for one portable worker slot.

Passwords are never logged. Investor / read-only trade flags fail closed.
This module must only initialize against an isolated portable terminal path.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from services.mt5_worker_agent.paths import assert_worker_terminal_path

logger = logging.getLogger("quantforg.mt5_worker_agent.session")

# MetaTrader5 IPC timeout — documented retry-once, then fail closed.
_IPC_TIMEOUT_CODE = -10005
_IPC_RETRY_SLEEP_SEC = 1.5


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
    market_data_ok: bool = False
    symbols_total: int = 0
    quote_symbol: str = ""
    quote_bid: float | None = None
    trade_mode: int | None = None
    error: str = ""


def _import_mt5() -> Any:
    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError(
            "MetaTrader5 package not available in this Python process"
        ) from exc
    return mt5


def _error_code(err: Any) -> int | None:
    if isinstance(err, tuple) and err:
        try:
            return int(err[0])
        except (TypeError, ValueError):
            return None
    return None


def initialize_portable(terminal_exe: Path | str) -> bool:
    path = assert_worker_terminal_path(terminal_exe)
    mt5 = _import_mt5()
    ok, err = _initialize_with_ipc_retry(mt5, path)
    logger.info(
        "mt5_portable_initialize ok=%s path=%s last_error=%s",
        ok,
        path,
        err,
    )
    return ok


def _initialize_with_ipc_retry(mt5: Any, path: Path) -> tuple[bool, Any]:
    """Initialize once; on IPC timeout (-10005) shutdown and retry exactly once."""
    ok = bool(mt5.initialize(path=str(path)))
    err = mt5.last_error()
    if ok or _error_code(err) != _IPC_TIMEOUT_CODE:
        return ok, err
    logger.warning(
        "mt5_ipc_timeout path=%s last_error=%s — single retry after shutdown",
        path,
        err,
    )
    try:
        mt5.shutdown()
    except Exception:
        logger.exception("mt5_ipc_retry_shutdown_failed")
    time.sleep(_IPC_RETRY_SLEEP_SEC)
    ok = bool(mt5.initialize(path=str(path)))
    err = mt5.last_error()
    if not ok and _error_code(err) == _IPC_TIMEOUT_CODE:
        logger.error(
            "mt5_ipc_timeout_persisted path=%s last_error=%s — fail closed",
            path,
            err,
        )
    return ok, err


def shutdown() -> None:
    try:
        mt5 = _import_mt5()
        mt5.shutdown()
    except Exception:
        logger.exception("mt5_shutdown_failed")


def probe_market_data(mt5: Any) -> tuple[bool, int, str, float | None]:
    """Best-effort market connectivity check — never fabricates quotes."""
    symbols = mt5.symbols_get()
    total = len(symbols) if symbols is not None else 0
    if total <= 0:
        return False, 0, "", None
    # Prefer common FX majors when present; otherwise first visible symbol.
    preferred = ("EURUSD", "EURUSDm", "EURUSD.a", "XAUUSD", "GBPUSD")
    names = [str(getattr(s, "name", "") or "") for s in symbols]
    pick = ""
    for cand in preferred:
        if cand in names:
            pick = cand
            break
    if not pick:
        pick = names[0]
    if pick:
        mt5.symbol_select(pick, True)
        tick = mt5.symbol_info_tick(pick)
        if tick is not None and float(getattr(tick, "bid", 0) or 0) > 0:
            return True, total, pick, float(tick.bid)
    # Symbols exist but no live tick (weekend / market closed) — still connectivity.
    return total > 0, total, pick, None


def authenticate_and_verify(
    *,
    terminal_exe: Path | str,
    login: int,
    password: str,
    server: str,
) -> Mt5VerifyResult:
    """Login on the isolated terminal and verify trade permissions + market data.

    Never logs ``password``.
    """
    _ = password  # present for call signature clarity; not logged
    if not password.strip():
        return Mt5VerifyResult(ok=False, trade_allowed=False, error="password_required")
    path = assert_worker_terminal_path(terminal_exe)
    mt5 = _import_mt5()
    init_ok, init_err = _initialize_with_ipc_retry(mt5, path)
    if not init_ok:
        return Mt5VerifyResult(
            ok=False,
            trade_allowed=False,
            error=f"initialize_failed:{init_err}",
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
        trade_mode_raw = getattr(info, "trade_mode", None)
        trade_mode: int | None
        try:
            trade_mode = int(trade_mode_raw) if trade_mode_raw is not None else None
        except (TypeError, ValueError):
            trade_mode = None
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
                trade_mode=trade_mode,
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
                trade_mode=trade_mode,
                error="tradeapi_disabled",
            )
        market_ok, sym_total, quote_sym, quote_bid = probe_market_data(mt5)
        logger.info(
            "mt5_verify_ok login=%s server=%s trade_allowed=%s trade_expert=%s "
            "trade_mode=%s market_data_ok=%s symbols=%s",
            int(info.login),
            str(info.server or ""),
            trade_allowed,
            trade_expert,
            trade_mode,
            market_ok,
            sym_total,
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
            market_data_ok=market_ok,
            symbols_total=sym_total,
            quote_symbol=quote_sym,
            quote_bid=quote_bid,
            trade_mode=trade_mode,
        )
    finally:
        # Leave terminal process running; detach Python IPC.
        try:
            mt5.shutdown()
        except Exception:
            logger.exception("mt5_detach_shutdown_failed")


def reject_invalid_credentials(
    *,
    terminal_exe: Path | str,
    login: int,
    password: str,
    server: str,
) -> Mt5VerifyResult:
    """Explicit negative test helper — expects login failure."""
    result = authenticate_and_verify(
        terminal_exe=terminal_exe,
        login=login,
        password=password,
        server=server,
    )
    if result.ok:
        return Mt5VerifyResult(
            ok=False,
            trade_allowed=False,
            login=result.login,
            server=result.server,
            error="unexpected_success_on_invalid_credentials",
        )
    return result
