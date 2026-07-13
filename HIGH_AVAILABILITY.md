# High Availability — MT5 Gateways

## Failure detection

- Gateways must heartbeat to `/gateway-manager/agents/heartbeat`.
- `POST /gateway-manager/ha/refresh` (or dashboard load) marks gateways **offline** when `last_seen` exceeds timeout (default 30s).

## Automatic reconnect

- **Terminal reconnect** remains on the Windows MT5 Gateway (`MT5_RECONNECT_*` settings) — unchanged API.
- **Cloud routing** avoids offline gateways and prefers lowest latency online peers.

## Gateway replacement

```bash
curl -X POST "$API/api/v1/gateway-manager/gateways/$OLD_ID/replace" \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{"hostname":"win-mt5-2.internal","base_url":"https://win-mt5-2.internal:8765"}'
```

Old gateway → `draining`; new gateway registered with fresh token.

## Graceful degradation

Routing order:

1. Online + broker + region match  
2. Online + broker match (any region)  
3. Degraded broker match (failover)  
4. Any registered broker gateway (unhealthy — last resort)  
5. `no_gateway_registered`

## Metrics used for HA decisions

Per gateway (from heartbeats):

- latency / heartbeat ms  
- reconnect_count  
- quotes/sec, orders/sec  
- history_sync_ok  
- cpu / memory (observability)  
- connected_users  

Missing metrics are treated as unknown — never invented.
