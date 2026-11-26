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
import re
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


_WINDOWS_PS = r"""
Add-Type @"
using System; using System.Text; using System.Collections.Generic;
using System.Runtime.InteropServices;
public class QfW {
  public delegate bool EP(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] public static extern bool EnumWindows(EP p, IntPtr l);
  [DllImport("user32.dll")] public static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] public static extern int GetWindowThreadProcessId(IntPtr h, out int pid);
  [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
  public static string[] For(int pid) {
    var r = new List<string>();
    EnumWindows((h, l) => { int p; GetWindowThreadProcessId(h, out p);
      if (p == pid && IsWindowVisible(h)) { var sb = new StringBuilder(256);
        GetWindowText(h, sb, 256); if (sb.Length > 0) r.Add(sb.ToString()); }
      return true; }, IntPtr.Zero);
    return r.ToArray(); } }
"@
$t = '__TARGET__'
Get-CimInstance Win32_Process -Filter "Name='terminal64.exe'" |
  Where-Object { $_.ExecutablePath -and $_.ExecutablePath.ToLower() -eq $t } |
  ForEach-Object { [QfW]::For([int]$_.ProcessId) }
"""


def redact_window_titles(titles: list[str]) -> list[str]:
    """Keep dialog/window text, drop account numbers (4+ digit runs)."""
    import re

    return [re.sub(r"\d{4,}", "***", t.strip())[:120] for t in titles if t.strip()]


def describe_terminal_windows(path: Path) -> list[str]:
    """Visible window titles of the slot terminal (redacted) for diagnostics.

    Shows modal dialogs (login failed, server not found, terms) that make the
    Python API time out. Read-only; never raises.
    """
    import subprocess

    target = str(path).lower().replace("'", "''")
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-NonInteractive",
                "-Command",
                _WINDOWS_PS.replace("__TARGET__", target),
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except Exception:
        return []
    return redact_window_titles(out.stdout.splitlines())


_REDACT_NUMBERS = re.compile(r"\d{6,}")
_REDACT_SECRETS = re.compile(r"(?i)(/?password|pass|secret)[=: ]+\S+")


def redact_diag_line(line: str) -> str:
    """Account numbers become ***last4; any password-looking value is dropped."""
    text = _REDACT_SECRETS.sub(r"\1=***", line.strip())
    text = _REDACT_NUMBERS.sub(lambda m: "***" + m.group(0)[-4:], text)
    return text[:240]


def slot_journal_tail(terminal_exe: Path | str, lines: int = 14) -> list[str]:
    """Last lines of the slot terminal's own journal (redacted), for diagnosis.

    The journal says what the terminal itself is doing (authorized, server
    unreachable, DLL/permission prompts) when the Python API times out.
    Read-only; never raises.
    """
    try:
        logs = Path(terminal_exe).parent / "Logs"
        files = sorted(logs.glob("*.log"), key=lambda f: f.stat().st_mtime)
        if not files:
            return []
        raw = files[-1].read_bytes()[-24_000:]
        text = raw.decode("utf-16-le", errors="replace")
        if text.count("\x00") > len(text) // 4:
            text = raw.decode("utf-8", errors="replace")
        rows = [ln for ln in text.splitlines() if ln.strip()]
        return [redact_diag_line(ln) for ln in rows[-lines:]]
    except Exception:
        return []


def describe_slot_processes(path: Path) -> list[str]:
    """Session / elevation of this Python process and the slot terminal(s)."""
    import ctypes
    import os
    import subprocess

    info: list[str] = []
    try:
        sess = ctypes.c_ulong(0)
        ctypes.windll.kernel32.ProcessIdToSessionId(  # type: ignore[attr-defined]
            os.getpid(), ctypes.byref(sess)
        )
        admin = bool(ctypes.windll.shell32.IsUserAnAdmin())  # type: ignore[attr-defined]
        info.append(f"python pid={os.getpid()} session={sess.value} admin={admin}")
    except Exception:
        info.append("python session/admin unknown")
    target = str(path).lower().replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
        f"Where-Object {{ $_.ExecutablePath -and $_.ExecutablePath.ToLower() -eq '{target}' }} | "
        'ForEach-Object { "terminal pid=$($_.ProcessId) session=$($_.SessionId) '
        'started=$($_.CreationDate) cmd=$($_.CommandLine)" }'
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        rows = [redact_diag_line(r) for r in out.stdout.splitlines() if r.strip()]
        info.extend(rows or ["no slot terminal process running"])
    except Exception:
        info.append("terminal process query failed")
    return info


def log_ladder_diagnostics(path: Path) -> None:
    logger.warning("mt5_terminal_windows titles=%s", describe_terminal_windows(path))
    logger.warning("mt5_slot_processes %s", describe_slot_processes(path))
    for row in slot_journal_tail(path):
        logger.warning("mt5_slot_journal %s", row)


def _initialize_with_ipc_retry(
    mt5: Any,
    path: Path,
    *,
    login: int | None = None,
    password: str | None = None,
    server: str | None = None,
    timeout_ms: int = _DEFAULT_INIT_TIMEOUT_MS,
    retry: bool = True,
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
    if ok or _error_code(err) != _IPC_TIMEOUT_CODE or not retry:
        return ok, err
    logger.warning(
        "mt5_ipc_timeout path=%s last_error=%s — single retry after shutdown",
        path,
        err,
    )
    logger.warning("mt5_terminal_windows titles=%s", describe_terminal_windows(path))
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


_STARTUP_INI = "qf_startup.ini"


def _startup_ini_path(path: Path) -> Path:
    return path.parent / "config" / _STARTUP_INI


def remove_startup_ini(terminal_exe: Path | str) -> None:
    """Delete the one-shot login config (it holds the password)."""
    ini = _startup_ini_path(Path(terminal_exe))
    try:
        if ini.exists():
            ini.write_text("", encoding="utf-16")
            ini.unlink()
    except OSError:
        logger.exception("startup_ini_remove_failed")


def launch_logged_in(
    path: Path,
    *,
    login: int,
    password: str,
    server: str,
    settle_seconds: float = 90.0,
) -> bool:
    """Start the slot terminal already logged in, so no Login dialog blocks IPC.

    A terminal without a saved account opens a modal Login window on start;
    while it is open the Python API cannot attach (IPC send failed/timeout).
    Starting with ``/config:`` credentials logs in directly. The config file
    exists only until the terminal has read it.
    """
    import subprocess

    ini = _startup_ini_path(path)
    ini.parent.mkdir(parents=True, exist_ok=True)
    ini.write_text(
        "[Common]\n"
        f"Login={int(login)}\n"
        f"Password={password}\n"
        f"Server={server.strip()}\n"
        "KeepPrivate=1\n"
        "NewsEnable=0\n"
        "[Experts]\n"
        "AllowLiveTrading=1\n"
        "AllowDllImport=0\n"
        "Enabled=1\n",
        encoding="utf-16",
    )
    try:
        subprocess.Popen(  # noqa: S603
            [str(path), "/portable", f"/config:{ini}"],
            close_fds=True,
        )
    except OSError:
        logger.exception("slot_terminal_launch_failed path=%s", path)
        remove_startup_ini(path)
        return False
    # The terminal reads the config at start; remove it as soon as it is up.
    deadline = time.time() + max(5.0, settle_seconds)
    time.sleep(5.0)
    remove_startup_ini(path)
    while time.time() < deadline:
        time.sleep(2.0)
        if _terminal_running(path):
            return True
    return _terminal_running(path)


def _terminal_running(path: Path) -> bool:
    import subprocess

    target = str(path).lower()
    try:
        out = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
                "Select-Object -ExpandProperty ExecutablePath",
            ],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return any(line.strip().lower() == target for line in out.splitlines())


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


_LADDER_TIMEOUT_MS = 180_000
_LOGIN_TIMEOUT_MS = 120_000
_LOGIN_WAIT_SEC = 120.0


def _wait_for_login(
    mt5: Any, login: int, *, wait_seconds: float = _LOGIN_WAIT_SEC
) -> bool:
    """Poll account_info until the terminal reports the expected login."""
    deadline = time.time() + wait_seconds
    while time.time() < deadline:
        time.sleep(3.0)
        try:
            info = mt5.account_info()
        except Exception:
            continue
        if info is not None and int(getattr(info, "login", 0) or 0) == login:
            logger.info("mt5_login_completed_late suffix=***%s", str(login)[-4:])
            return True
    return False


def kill_slot_terminals(path: Path) -> None:
    """Stop only terminals whose executable is exactly this slot's terminal64.exe."""
    import subprocess

    target = str(path).lower().replace("'", "''")
    script = (
        "Get-CimInstance Win32_Process -Filter \"Name='terminal64.exe'\" | "
        f"Where-Object {{ $_.ExecutablePath -and $_.ExecutablePath.ToLower() -eq '{target}' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force }"
    )
    try:
        subprocess.run(  # noqa: S603
            ["powershell", "-NoProfile", "-Command", script],  # noqa: S607
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        logger.exception("kill_slot_terminals_failed path=%s", path)
    time.sleep(2.0)


def disable_internal_mcp(terminal_exe: Path | str) -> bool:
    """Disable the terminal's built-in MCP servers for this slot.

    Builds 6090+ bind ``127.0.0.1:22346`` for MCP; every terminal on the PC
    shares loopback, so a slot starting while the LIVE terminal runs logs
    ``MCP bind error ... (10048)``. The slot never needs MCP, so it is turned
    off in the slot's own ``Config/assistant.ini`` (LIVE is never touched).
    """
    root = assert_worker_terminal_path(terminal_exe).parent
    cfg = root / "Config"
    if not cfg.is_dir() and (root / "config").is_dir():
        cfg = root / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    ini = cfg / "assistant.ini"
    text = ""
    if ini.is_file():
        try:
            text = ini.read_text(encoding="utf-16")
        except UnicodeError:
            text = ini.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    for section in ("MCP.MetaTrader", "MCP.MetaEditor"):
        header = f"[{section}]"
        try:
            i = next(n for n, ln in enumerate(lines) if ln.strip() == header)
        except StopIteration:
            lines += ["", header, "Enable=0"]
            continue
        j = i + 1
        while j < len(lines) and not lines[j].strip().startswith("["):
            if lines[j].split("=", 1)[0].strip().lower() == "enable":
                lines[j] = "Enable=0"
                break
            j += 1
        else:
            lines.insert(i + 1, "Enable=0")
            continue
        if j >= len(lines) or lines[j].strip().startswith("["):
            lines.insert(i + 1, "Enable=0")
    payload = "\n".join(lines).strip("\n") + "\n"
    if payload == text:
        return False
    try:
        ini.write_text(payload, encoding="utf-16")
    except OSError:
        logger.exception("disable_internal_mcp_failed path=%s", ini)
        return False
    logger.info("disabled_internal_mcp path=%s", ini)
    return True


def initialize_with_ladder(
    mt5: Any,
    path: Path,
    *,
    login: int,
    password: str,
    server: str,
) -> tuple[bool, Any]:
    """Attach to the slot terminal, trying both supported start modes from a clean slate.

    1. Let ``mt5.initialize`` launch the terminal itself with credentials.
    2. If IPC still times out, restart the terminal pre-logged-in via /config and
       attach without credentials.
    A hung terminal is killed between attempts so the next cycle never inherits it.
    """
    kill_slot_terminals(path)
    disable_internal_mcp(path)
    ok, err = _initialize_with_ipc_retry(
        mt5,
        path,
        login=login,
        password=password,
        server=server,
        timeout_ms=_LADDER_TIMEOUT_MS,
        retry=False,
    )
    if ok or _error_code(err) != _IPC_TIMEOUT_CODE:
        return ok, err
    logger.warning("mt5_ladder step=python_launch failed err=%s", err)
    log_ladder_diagnostics(path)
    try:
        mt5.shutdown()
    except Exception:
        logger.exception("mt5_ladder_shutdown_failed")
    kill_slot_terminals(path)
    launch_logged_in(path, login=login, password=password, server=server)
    ok, err = _initialize_with_ipc_retry(
        mt5, path, timeout_ms=_LADDER_TIMEOUT_MS, retry=False
    )
    if ok:
        return ok, err
    logger.error("mt5_ladder step=prelaunch_attach failed err=%s", err)
    log_ladder_diagnostics(path)
    try:
        mt5.shutdown()
    except Exception:
        logger.exception("mt5_ladder_shutdown_failed")
    kill_slot_terminals(path)
    return ok, err


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
    init_ok, init_err = initialize_with_ladder(
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
                "mt5_post_initialize_login_required "
                "expected_suffix=***%s actual_suffix=***%s",
                str(int(login))[-4:],
                str(actual_login)[-4:] if actual_login else "none",
            )
            logged_in = bool(
                mt5.login(
                    login=int(login),
                    password=password,
                    server=server.strip(),
                    timeout=_LOGIN_TIMEOUT_MS,
                )
            )
            if not logged_in and _error_code(mt5.last_error()) == _IPC_TIMEOUT_CODE:
                # The terminal may still be completing the login; wait for the
                # session to switch instead of calling it a failure.
                logged_in = _wait_for_login(mt5, int(login))
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
        # Authenticated session with trading disabled — common for unfunded LIVE
        # accounts and investor passwords. Do not claim trade_allowed; classify
        # neutrally so owner attestation can record FUNDING_REQUIRED without
        # inventing investor vs master.
        if not trade_allowed:
            return Mt5VerifyResult(
                ok=False,
                trade_allowed=False,
                login=int(getattr(info, "login", login) or login),
                server=str(getattr(info, "server", server) or server),
                name=str(getattr(info, "name", "") or ""),
                balance=float(getattr(info, "balance", 0) or 0),
                equity=float(getattr(info, "equity", 0) or 0),
                currency=str(getattr(info, "currency", "") or ""),
                trade_mode=trade_mode,
                error="authenticated_trading_not_enabled",
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
