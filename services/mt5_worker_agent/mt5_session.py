"""Real MetaTrader5 session helpers for one portable worker slot.

Passwords are never logged. Investor / read-only trade flags fail closed.
This module must only initialize against an isolated portable terminal path.

Important: ``mt5.initialize(path=...)`` without login/password/server reuses the
terminal's last saved account. A stale DEMO account in a portable slot then
fails with ``(-6, Authorization failed)`` before ``login()`` is reached.
Always pass the intended credentials into ``initialize`` for worker verify.
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
_DEFAULT_INIT_TIMEOUT_MS = 120_000


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


def clear_portable_saved_login(terminal_exe: Path | str) -> bool:
    """Clear saved portable account state (never logs secrets).

    Leftover DEMO rows in ``common.ini`` / ``accounts.dat`` make a warm portable
    terminal auto-authorize the wrong account. ``initialize(login=...)`` then
    returns True while ``account_info`` still shows the stale DEMO session.
    """
    root = assert_worker_terminal_path(terminal_exe).parent
    changed = False
    for rel in ("config", "Config"):
        accounts = root / rel / "accounts.dat"
        if accounts.is_file():
            backup = accounts.with_suffix(".dat.bak_qf")
            try:
                if backup.exists():
                    backup.unlink()
                accounts.replace(backup)
                changed = True
                logger.info("quarantined_portable_accounts_dat path=%s", accounts)
            except OSError:
                logger.exception("quarantine_accounts_dat_failed")
    candidates = [
        root / "config" / "common.ini",
        root / "Config" / "common.ini",
    ]
    ini = next((p for p in candidates if p.is_file()), None)
    if ini is None:
        return changed
    try:
        text = ini.read_text(encoding="utf-16")
    except UnicodeError:
        text = ini.read_text(encoding="utf-8", errors="replace")
    out: list[str] = []
    for line in text.splitlines():
        key = line.split("=", 1)[0].strip().lower() if "=" in line else ""
        if key in {"login", "server", "password", "certpassword"}:
            prefix = line.split("=", 1)[0]
            replacement = "0" if key == "login" else ""
            new_line = f"{prefix}={replacement}"
            if new_line != line:
                changed = True
            out.append(new_line)
        else:
            out.append(line)
    payload = "\n".join(out) + ("\n" if text.endswith("\n") else "")
    try:
        ini.write_text(payload, encoding="utf-16")
    except OSError:
        ini.write_text(payload, encoding="utf-8")
    logger.info("cleared_portable_saved_login path=%s changed=%s", ini, changed)
    return changed


def initialize_portable(terminal_exe: Path | str) -> bool:
    """Connect IPC only (no account). Prefer authenticate_and_verify for login."""
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


def _initialize_with_ipc_retry(
    mt5: Any,
    path: Path,
    *,
    login: int | None = None,
    password: str | None = None,
    server: str | None = None,
    timeout_ms: int = _DEFAULT_INIT_TIMEOUT_MS,
) -> tuple[bool, Any]:
    """Initialize once; on IPC timeout (-10005) shutdown and retry exactly once.

    When login/password/server are provided they are passed to ``initialize`` so
    the portable terminal does not reuse a stale saved account (which surfaces
    as authorization failure -6 before ``login()``).
    """

    def _call() -> bool:
        kwargs: dict[str, Any] = {
            "path": str(path),
            "portable": True,
            "timeout": int(timeout_ms),
        }
        if login is not None and password and server:
            kwargs["login"] = int(login)
            kwargs["password"] = password
            kwargs["server"] = server.strip()
        return bool(mt5.initialize(**kwargs))

    ok = _call()
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
    ok = _call()
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
    if not password.strip():
        return Mt5VerifyResult(ok=False, trade_allowed=False, error="password_required")
    if not str(server).strip():
        return Mt5VerifyResult(ok=False, trade_allowed=False, error="server_required")
    path = assert_worker_terminal_path(terminal_exe)
    try:
        clear_portable_saved_login(path)
    except Exception:
        logger.exception("clear_portable_saved_login_failed")
    mt5 = _import_mt5()
    init_ok, init_err = _initialize_with_ipc_retry(
        mt5,
        path,
        login=int(login),
        password=password,
        server=server.strip(),
    )
    if not init_ok:
        return Mt5VerifyResult(
            ok=False,
            trade_allowed=False,
            error=f"initialize_failed:{init_err}",
        )
    try:
        # After attach, confirm account. If initialize ignored login kwargs (warm
        # terminal with a prior session), attempt a single explicit login().
        info = mt5.account_info()
        if info is None:
            time.sleep(1.0)
            info = mt5.account_info()
        actual_login = int(getattr(info, "login", 0) or 0) if info is not None else 0
        if info is None or actual_login != int(login):
            logger.warning(
                "mt5_post_initialize_login_required expected_suffix=***%s actual_suffix=***%s",
                str(int(login))[-4:],
                str(actual_login)[-4:] if actual_login else "none",
            )
            logged_in = bool(
                mt5.login(login=int(login), password=password, server=server.strip())
            )
            if not logged_in:
                return Mt5VerifyResult(
                    ok=False,
                    trade_allowed=False,
                    login=actual_login or None,
                    server=str(getattr(info, "server", "") or "") if info else "",
                    error=f"login_failed:{mt5.last_error()}",
                )
            info = mt5.account_info()
            if info is None:
                return Mt5VerifyResult(
                    ok=False,
                    trade_allowed=False,
                    error=f"account_info_unavailable_after_login:{mt5.last_error()}",
                )
            actual_login = int(getattr(info, "login", 0) or 0)
            if actual_login != int(login):
                return Mt5VerifyResult(
                    ok=False,
                    trade_allowed=False,
                    login=actual_login or None,
                    server=str(getattr(info, "server", "") or ""),
                    error=(
                        "login_account_mismatch:"
                        f"expected_login_suffix=***{str(int(login))[-4:]} "
                        f"actual_login_suffix=***{str(actual_login)[-4:]}"
                    ),
                )
        term = mt5.terminal_info()
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
