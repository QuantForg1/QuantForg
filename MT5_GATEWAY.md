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

```powershell
# 1. Install MetaTrader 5 terminal + MetaTrader5 Python package
pip install MetaTrader5

# 2. Copy deploy/mt5_gateway/gateway.env.example → set MT5_GATEWAY_TOKEN
#    Prefer MT5_GATEWAY_AUTO_ATTACH=true when the XM terminal stays logged in

# 3. Start gateway (from repo root so .env is found)
quantforg-mt5-gateway
# or: python -m services.mt5_gateway.main
```

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
