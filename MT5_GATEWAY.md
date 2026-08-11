# QuantForg MT5 Gateway

Dedicated **Windows** process that owns the live MetaTrader 5 terminal runtime.

The QuantForg Railway/API process does **not** hold broker passwords. Existing QuantForg APIs (`/api/v1/mt5`, Strategy Engine, Portfolio Intelligence, Execution Intelligence) are **unchanged**.

## Responsibilities

| Area | Gateway support |
|------|-----------------|
| Attach existing session | `POST /session/attach` (terminal already logged in; no password) |
| Explicit login | `POST /session/connect` (login / password / server) |
| Disconnect | `POST /session/disconnect` |
| Auto-attach (optional) | `MT5_GATEWAY_AUTO_ATTACH=true` on startup |
| Heartbeat | `GET /heartbeat` + background loop |
| Auto reconnect | Password reconnect when connected; initialize+account probe when attached |
| Account sync | `GET /account` |
| Quotes | `GET /quotes/{symbol}` (symbol_select before tick) |
| Candles | `GET /candles/{symbol}` |
| Positions | `GET /positions` |
| Orders | `GET /orders` |
| History | `GET /history/orders`, `GET /history/deals` |
| Diagnostics | `GET /diagnostics` |
| Health | `GET /health` |

## Communication

- **REST** — primary surface (this document)
- **WebSocket (optional)** — `WS /ws?token=<gateway_token>` heartbeat stream (`MT5_GATEWAY_ENABLE_WEBSOCKET=true`)
- **Health** — `GET /health` (no token; includes `token_configured` + setup hint)

## Authentication

Shared **gateway token** (not Supabase user auth):

```http
Authorization: Bearer <MT5_GATEWAY_TOKEN>
```

or

```http
X-Gateway-Token: <MT5_GATEWAY_TOKEN>
```

Generate a strong random token on the Windows host. Store it only in the gateway’s local `.env` (see `deploy/mt5_gateway/gateway.env.example`).

## Credentials policy

| Secret | Railway | Windows Gateway |
|--------|---------|-----------------|
| Broker login / password / server | **Never** | Only after `POST /session/connect` (in-memory). **Not** collected on `/session/attach` |
| `MT5_GATEWAY_TOKEN` | Optional (Gateway Manager hash; callers) | **Required** locally |
| `MT5_TERMINAL_PATH` | No | Optional path to `terminal64.exe` |

Broker passwords are **not** written to disk by the gateway and are **never** returned in JSON responses.

## Session modes

| Mode | How | Password in RAM? |
|------|-----|------------------|
| `connected` | `POST /session/connect` | Yes (reconnect login) |
| `attached` | `POST /session/attach` or auto-attach | No — terminal already authenticated |

## Run (Windows)

QuantForg requires **Python 3.13** via the Poetry project venv (`.venv`).  
Do **not** use bare `py -m` / global Python 3.14 — that environment does not include project dependencies (`uvicorn`, etc.).

### Production (recommended) — survives terminal close

Interactive `start_gateway.ps1` dies when the PowerShell window closes. Production uses a **Hidden** child process + supervisor + optional Task Scheduler:

```powershell
# One-shot: start Hidden gateway, verify /health/live, exit supervisor
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\supervise_gateway.ps1 -Once

# Persistent: supervise loop (auto-restart on crash / unresponsive /health/live)
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\supervise_gateway.ps1

# Register ONLOGON Scheduled Task (run elevated once)
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\install_gateway_task.ps1
```

Supervisor logs: `docs/production/reports/gateway_supervisor/`.  
Stop: create `docs/production/reports/gateway_supervisor/STOP`.

Watchdog restarts only when the process dies or `/health/live` fails repeatedly — **not** when a single quote/candle is slow.

### Interactive / debug

```powershell
# From repo root
py -3.13 --version
py -3.13 -m poetry --version
py -3.13 -m poetry install

# Foreground (skips if :8765 already live) — dies when the window closes
powershell -ExecutionPolicy Bypass -File deploy\mt5_gateway\start_gateway.ps1

# Or start directly with the project interpreter:
.\.venv\Scripts\python.exe -m services.mt5_gateway.main
```

Ensure `MT5_GATEWAY_TOKEN` is set in the Windows host `.env` (see `deploy/mt5_gateway/gateway.env.example`).  
Prefer `MT5_GATEWAY_AUTO_ATTACH=true` when the terminal stays logged in.

### Health endpoints

| Path | Behavior |
|------|----------|
| `GET /health/live` | Process liveness only — no MetaTrader5, no ops lock |
| `GET /health` | Fast readiness; MT5 probe bounded (~450ms); degraded MT5 still HTTP 200 |

Market-data handlers use bounded concurrency, in-flight dedupe, and hard MT5 timeouts (`MT5_MARKET_DATA_TIMEOUT_SECONDS`, `MT5_MAX_CONCURRENT_MARKET_REQUESTS`).

### Prefer attach when already logged into XM

```bash
curl -X POST http://127.0.0.1:8765/session/attach \
  -H "Authorization: Bearer $MT5_GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{}'
```

### Explicit login (when terminal is not logged in)

```bash
curl -X POST http://windows-host:8765/session/connect \
  -H "Authorization: Bearer $MT5_GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"login":123456,"password":"...","server":"Broker-MT5"}'
```

## Endpoints

| Method | Path | Auth |
|--------|------|------|
| GET | `/health` | optional |
| GET | `/diagnostics` | token |
| POST | `/session/connect` | token |
| POST | `/session/attach` | token |
| POST | `/session/disconnect` | token |
| GET | `/session/status` | token |
| GET | `/heartbeat` | token |
| GET | `/account` | token |
| GET | `/symbols` | token |
| GET | `/quotes/{symbol}` | token |
| GET | `/candles/{symbol}?timeframe=H1&count=100` | token |
| GET | `/positions` | token |
| GET | `/orders` | token |
| GET | `/history/orders` | token |
| GET | `/history/deals` | token |
| WS | `/ws?token=...` | token |

## Package layout

```
services/mt5_gateway/
  main.py        # FastAPI app + entrypoint + optional auto-attach
  runtime.py     # terminal, attach/connect, heartbeat, reconnect
  routers.py     # REST
  websocket.py   # optional WS
  auth.py        # gateway token
  settings.py    # env
  schemas.py     # ConnectRequest / AttachRequest
```

## Relation to QuantForg API

- QuantForg Cloud/Railway continues to expose existing `/api/v1/*` routes.
- This gateway is a **separate** Windows service for live MT5 IPC.
- Backend integration can call the gateway over HTTPS with the gateway token — **without** storing broker credentials in Railway — and without changing current public API contracts.

## Security notes

- Bind to a private network / VPN / SSH tunnel in production.
- Rotate `MT5_GATEWAY_TOKEN` regularly.
- Do not commit broker passwords or gateway tokens.
- Keep `EXECUTION_ENABLED` / order_send policy on the QuantForg side; this gateway remains read + session oriented.
- Production default: `MT5_GATEWAY_AUTO_ATTACH=false`. Enable only on private Windows hosts with an operator-managed terminal.
