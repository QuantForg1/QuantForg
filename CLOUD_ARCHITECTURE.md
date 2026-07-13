# Cloud Architecture — QuantForg v1

Distributed layout: **Cloud control plane** (Railway/API) + **Windows MT5 Gateways** (broker terminal hosts).

## Principles

- Existing QuantForg APIs unchanged (`/api/v1/mt5`, intelligence, execution, etc.).
- MT5 Gateway REST surface unchanged (`services/mt5_gateway`).
- Broker credentials **never** stored in Railway.
- Gateways authenticate to the cloud with a **gateway token** + **nonce** (replay protection).

## Components

```
┌────────────────────────────┐         ┌──────────────────────────────┐
│ QuantForg Cloud (Railway)  │         │ Windows VPS / bare metal     │
│  API + Gateway Manager     │◄───────►│  MT5 Gateway process         │
│  /gateway-manager/*        │  token  │  MetaTrader 5 terminal       │
│  Cloud Ops UI              │  nonce  │  broker session (in-memory)  │
└────────────────────────────┘         └──────────────────────────────┘
```

## Gateway Manager

Additive API prefix: `/api/v1/gateway-manager`

| Capability | Mechanism |
|------------|-----------|
| Register / discover | `POST/GET /gateways` |
| Health / heartbeat | Agent `POST /agents/heartbeat` + HA refresh |
| Online/offline | Heartbeat timeout → offline |
| Version compatibility | Compatible version set in manager |
| Routing | Broker + region + health + failover |
| Metrics | Reported on heartbeat (CPU/mem/latency/…) |
| Security | Token hash, rotation, IP allowlist, nonce, rate limit |

## Data plane vs control plane

| Plane | Owns |
|-------|------|
| Control (cloud) | Registry, routing, HA, ops dashboard |
| Data (gateway) | Live MT5 quotes/candles/positions/history |

## UI

`/cloud-ops` — Cloud Operations dashboard (additive; does not redesign existing pages).

## Related docs

- `GATEWAY_DEPLOYMENT.md`
- `HIGH_AVAILABILITY.md`
- `MT5_GATEWAY.md`
