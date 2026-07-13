# Broker Connectivity Framework

Additive venue abstraction over QuantForg’s live MT5 integration. Future brokers register as adapters that return structured `unsupported` — **never** simulated market connectivity.

**Preserves:** Strategy Engine, Execution Intelligence, Portfolio Intelligence, `/mt5`, `/brokers`, auth, security, DB schema, `EXECUTION_ENABLED`.

## Adapter contract (`BrokerConnectivityPort`)

| Capability | Purpose |
|------------|---------|
| Connect / Disconnect | Session lifecycle |
| Health / Heartbeat | Connection + latency probe |
| Balances / Positions / Orders | Account & book reads |
| History | Deals / historical orders |
| Symbols / Quotes / Candles | Market metadata & bars |
| Trading | Gate report only — never `order_send` |
| Capabilities | Declared profile / matrix row |

Uniform result:

```json
{
  "status": "ok | unsupported | unavailable | error",
  "capability": "health",
  "platform": "mt5",
  "data": {},
  "reason": "",
  "latency_ms": 12.3
}
```

## Implementations

| Platform | Status |
|----------|--------|
| MetaTrader 5 | **Live** — wraps existing `MT5Adapter` |
| cTrader, Interactive Brokers, Binance, Bybit, OKX, OANDA, FXCM, Alpaca | Stub — `status=unsupported` |

Existing `BrokerAdapterPort` and placeholder adapters are unchanged. Intelligence market-data providers (e.g. Binance public data) are **not** broker connectivity.

## Capability matrix

Declared fields: supported order types, margin, leverage, netting/hedging, market data, history, streaming.

Source: `app/domain/broker_connectivity/matrix.py`  
API: `GET /broker-connectivity/matrix`  
UI: `/broker-connectivity`

## Diagnostics

- Adapter latency / heartbeat / failure history (MT5)
- Capability presence checks
- Optional `ConnectionHealthMonitor` + `AutomaticReconnectManager` snapshots from DI

API: `GET /broker-connectivity/diagnostics`

## APIs (`/api/v1/broker-connectivity`)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/dashboard` | Catalog + matrix + diagnostics |
| GET | `/catalog` | Registered adapters |
| GET | `/matrix` | Capability matrix |
| GET | `/diagnostics` | Latency, heartbeat, reconnect, failures |
| GET | `/{platform}/capabilities` | Declared profile |
| GET | `/{platform}/health` | Health probe |
| GET | `/{platform}/heartbeat` | Heartbeat / ping |
| POST | `/invoke` | Invoke any capability |
| POST | `/{platform}/trading` | Trading gate probe (no orders) |

## Trading rule

Connectivity Framework **never** enables live trading and **never** calls `order_send`. Trading capability reports `EXECUTION_ENABLED` and points to `POST /execution/submit`.

## Related

- Live MT5: `/mt5/*`
- Broker accounts: `/brokers`, `/broker-accounts`, `/broker-connections`
- Execution: `/execution/*`, Execution Intelligence
- Docs: `EXECUTION_INTELLIGENCE.md`, `PORTFOLIO_INTELLIGENCE.md`, `STRATEGY_ENGINE.md`
