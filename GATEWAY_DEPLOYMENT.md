# Gateway Deployment Guide

Deploy Windows MT5 Gateways and register them with QuantForg Cloud.

## Prerequisites

- Windows host with MetaTrader 5 terminal
- Python 3.13 + `MetaTrader5` package
- QuantForg repo checkout
- Strong `MT5_GATEWAY_TOKEN` (from Cloud registration response)

## 1. Register in Cloud

```bash
curl -X POST "$API/api/v1/gateway-manager/gateways" \
  -H "Authorization: Bearer $USER_JWT" \
  -H "Content-Type: application/json" \
  -d '{
    "hostname": "win-mt5-1.internal",
    "broker": "exness",
    "region": "eu-west",
    "version": "1.0.0",
    "base_url": "https://win-mt5-1.internal:8765",
    "ip_allowlist": ["203.0.113.10"]
  }'
```

Save `gateway_id` and `gateway_token` from the response.  
**Never** put the token or broker passwords in Railway.

## 2. Windows host

```powershell
cd C:\QuantForg
# create venv, install deps
$env:MT5_GATEWAY_TOKEN="<from registration>"
$env:MT5_GATEWAY_HOST="0.0.0.0"
$env:MT5_GATEWAY_PORT="8765"
$env:MT5_TERMINAL_PATH="C:\Program Files\MetaTrader 5\terminal64.exe"
quantforg-mt5-gateway
```

Or install as a service — see `deploy/mt5_gateway/windows-service.ps1`.

## 3. Connect broker session (on gateway)

```bash
curl -X POST https://win-mt5-1.internal:8765/session/connect \
  -H "Authorization: Bearer $MT5_GATEWAY_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"login":123456,"password":"...","server":"Exness-MT5"}'
```

## 4. Heartbeat agent (mutual auth)

Gateway agents POST to cloud:

```bash
curl -X POST "$API/api/v1/gateway-manager/agents/heartbeat" \
  -H "Content-Type: application/json" \
  -d "{
    \"gateway_id\": \"$GATEWAY_ID\",
    \"token\": \"$MT5_GATEWAY_TOKEN\",
    \"nonce\": \"$(uuidgen)\",
    \"latency_ms\": 12.5,
    \"metrics\": {
      \"cpu_percent\": 11,
      \"memory_percent\": 42,
      \"heartbeat_ms\": 12.5,
      \"quotes_per_sec\": 3.2,
      \"orders_per_sec\": 0,
      \"history_sync_ok\": true,
      \"reconnect_count\": 0,
      \"connected_users\": 1
    },
    \"status\": \"online\"
  }"
```

## 5. Docker / systemd

- `deploy/mt5_gateway/Dockerfile`
- `deploy/mt5_gateway/docker-compose.yml`
- `deploy/mt5_gateway/quantforg-mt5-gateway.service`

## 6. Token rotation

```bash
curl -X POST "$API/api/v1/gateway-manager/gateways/$GATEWAY_ID/rotate-token" \
  -H "Authorization: Bearer $USER_JWT"
```

Update Windows `MT5_GATEWAY_TOKEN` immediately.

## Security checklist

- [ ] IP allowlist set for each gateway  
- [ ] Gateway token only on Windows host  
- [ ] Broker passwords only via `/session/connect` (memory)  
- [ ] Unique nonce per heartbeat  
- [ ] Private network / VPN / mTLS terminator in front of gateway  

## Operator UI

Cloud Operations: `/cloud-ops`
