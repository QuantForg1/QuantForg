# QuantForg MT5 Gateway

Dedicated **Windows** process that owns the live MetaTrader 5 terminal runtime.

The QuantForg Railway/API process does **not** hold broker passwords. Existing QuantForg APIs (`/api/v1/mt5`, Strategy Engine, Portfolio Intelligence, Execution Intelligence) are **unchanged**.

## Responsibilities

| Area | Gateway support |
|------|-----------------|
| MT5 terminal management | `POST /session/connect`, `POST /session/disconnect` |
| Heartbeat | `GET /heartbeat` + background loop |
| Auto reconnect | In-memory credentials + reconnect policy |
| Account sync | `GET /account` |
| Quotes | `GET /quotes/{symbol}` |
| Candles | `GET /candles/{symbol}` |
| Positions | `GET /positions` |
| Orders | `GET /orders` |
| History | `GET /history/orders`, `GET /history/deals` |
| Diagnostics | `GET /diagnostics` |
| Health | `GET /health` |

## Communication

- **REST** — primary surface (this document)
- **WebSocket (optional)** — `WS /ws?token=<gateway_token>` heartbeat stream (`MT5_GATEWAY_ENABLE_WEBSOCKET=true`)
- **Health** — `GET /health` (open when `MT5_GATEWAY_ALLOW_UNAUTHENTICATED_HEALTH=true`)

## Authentication

Shared **gateway token** (not Supabase user auth):

```http
Authorization: Bearer <MT5_GATEWAY_TOKEN>
```

or

```http
X-Gateway-Token: <MT5_GATEWAY_TOKEN>
```

Generate a strong random token on the Windows host. Store it only in the gateway’s local `.env`.

## Credentials policy

| Secret | Railway | Windows Gateway |
|--------|---------|-----------------|
| Broker login / password / server | **Never** | In-memory after `POST /session/connect` only |
| `MT5_GATEWAY_TOKEN` | Optional (if API later calls gateway) | **Required** locally |
| `MT5_TERMINAL_PATH` | No | Optional path to `terminal64.exe` |

Broker passwords are **not** written to disk by the gateway and are **never** returned in JSON responses.

## Run (Windows)

```powershell
# 1. Install MetaTrader 5 terminal + MetaTrader5 Python package
pip install MetaTrader5

# 2. Configure local .env on the Windows VPS
# MT5_GATEWAY_TOKEN=<strong-random>
# MT5_GATEWAY_HOST=0.0.0.0
# MT5_GATEWAY_PORT=8765
# MT5_TERMINAL_PATH=C:\Program Files\MetaTrader 5\terminal64.exe

# 3. Start gateway
quantforg-mt5-gateway
# or: python -m services.mt5_gateway.main
```

Connect a session:

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
  main.py        # FastAPI app + entrypoint
  runtime.py     # terminal, heartbeat, reconnect
  routers.py     # REST
  websocket.py   # optional WS
  auth.py        # gateway token
  settings.py    # env
```

## Relation to QuantForg API

- QuantForg Cloud/Railway continues to expose existing `/api/v1/*` routes.
- This gateway is a **separate** Windows service for live MT5 IPC.
- Future backend integration can call the gateway over HTTPS with the gateway token — **without** storing broker credentials in Railway — and without changing current public API contracts.

## Security notes

- Bind to a private network / VPN / SSH tunnel in production.
- Rotate `MT5_GATEWAY_TOKEN` regularly.
- Do not commit broker passwords or gateway tokens.
- Keep `EXECUTION_ENABLED` / order_send policy on the QuantForg side; this gateway v1 is read + session oriented.
