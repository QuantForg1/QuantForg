# Weltrade Integration — QuantForg v1.0

Production v1 supports **Weltrade MT5 only** in the product UX while preserving the multi-broker domain framework for later enablement.

## Architecture

```
Browser (/broker)
    │  JWT
    ▼
Railway API (/api/v1/weltrade/*, /api/v1/mt5/*, /api/v1/execution/*)
    │  Bearer MT5_GATEWAY_CALLER_TOKEN
    ▼
Windows MT5 Gateway (services/mt5_gateway — unchanged REST)
    │  MetaTrader5 IPC
    ▼
MetaTrader 5 terminal → Weltrade
```

The browser **never** calls the gateway or MT5 directly.

## Gateway

Unchanged surface: `/session/connect`, `/session/attach`, `/account`, `/quotes`, `/positions`, …  
See `MT5_GATEWAY.md`.

Railway selects the live path when:

- `MT5_GATEWAY_BASE_URL` is set (Windows gateway URL)
- `MT5_GATEWAY_CALLER_TOKEN` matches host `MT5_GATEWAY_TOKEN`

Otherwise the in-process mock MT5 client remains (CI / local without gateway).

## Connection

1. User opens `/broker`
2. `POST /api/v1/weltrade/connect`
3. API checks gateway `/health`
4. Prefers `POST /session/attach` (terminal already logged in)
5. Else `POST /session/connect` with login/password/server
6. Synchronizes account, positions, orders, history via gateway reads
7. Existing `/mt5/*`, portfolio, and execution APIs use the same adapter

Servers (auto by account type):

| Type | Default |
|------|---------|
| Demo | `Weltrade-Demo` |
| Live | `Weltrade-MT5` |

## Security

| Secret | Browser | Railway | Gateway memory |
|--------|---------|---------|----------------|
| Weltrade password | Never persisted (form only) | Never stored — redacted after forward | Yes after connect |
| Gateway token | No | `MT5_GATEWAY_CALLER_TOKEN` (caller auth only) | `MT5_GATEWAY_TOKEN` |
| Supabase / DB | No broker passwords | No broker passwords | — |

“Remember this account (local gateway only)” does **not** use `localStorage` / `sessionStorage`.

## Trading Flow

Buy / Sell / Close / Modify / Pending Orders / History use **existing** APIs:

- `POST /api/v1/execution/submit` (gated by `EXECUTION_ENABLED`)
- Portfolio / positions / orders routes

No duplicated execution logic. Gateway v1 remains session + market-data oriented; `EXECUTION_ENABLED` stays authoritative.

## Realtime

`/broker` uses the existing `RealtimeEngine` / `useBrokerStatusStream`. No extra polling loops beyond React Query invalidation after connect.

## Recovery

- **Reconnect** → `/weltrade/reconnect` → gateway attach / passwordless reconnect
- **Disconnect** → gateway `/session/disconnect`
- Heartbeat / auto-reconnect remain on the Windows gateway process

## Deployment

### Windows host

1. MT5 logged into Weltrade
2. `MT5_GATEWAY_TOKEN=<strong>`
3. Optional `MT5_GATEWAY_AUTO_ATTACH=true`
4. `quantforg-mt5-gateway`

### Railway

```env
MT5_GATEWAY_BASE_URL=https://your-windows-gateway:8765
MT5_GATEWAY_CALLER_TOKEN=<same as Windows MT5_GATEWAY_TOKEN>
EXECUTION_ENABLED=false
```

Reachability: private network / VPN / tunnel to the Windows host. Never put Weltrade passwords in Railway.

## API (additive)

| Method | Path |
|--------|------|
| GET | `/api/v1/weltrade/profile` |
| GET | `/api/v1/weltrade/health` |
| GET | `/api/v1/weltrade/dashboard` |
| POST | `/api/v1/weltrade/connect` |
| POST | `/api/v1/weltrade/attach` |
| POST | `/api/v1/weltrade/disconnect` |
| POST | `/api/v1/weltrade/reconnect` |

Existing `/api/v1/mt5` and broker-framework routes remain for compatibility; product UX is Weltrade-first via `/broker`.
