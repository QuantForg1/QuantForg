# Windows Gateway Recovery (RC1 Infra)

Cloud agents **cannot** execute this. Run elevated on the Windows VPS only.

## Goal

- `http://127.0.0.1:8765/health` → HTTP 200  
- `https://gateway.quantforg.com/health` → HTTP 200 (no Cloudflare 502)  
- MT5: Connected, Trade Allowed, Broker, Account

## Steps

```powershell
cd "C:\Users\P7 PROVIDER\QuantForg"
git fetch origin
# Prefer production tip unless instructed otherwise:
git checkout main
git pull origin main

# Single listener on 8765 + restart + session attach + verify:
.\deploy\mt5_gateway\deploy_main_gateway.ps1

# Preferred P0 wrapper (deploy + tunnel service hints + public /health gate):
.\deploy\mt5_gateway\p0_gateway_recovery.ps1
```

If Cloudflare still 502 after local `/health` is 200:

1. Confirm `cloudflared` / tunnel service is running and points at `http://127.0.0.1:8765`.
2. Restart the tunnel service; re-check public `/health`.
3. Capture `docs\production\reports\oat_v71\deploy_main_gateway_verify.json`.

## Verify payload (required fields)

From local `/account` + `/health`:

| Field | Expect |
|-------|--------|
| `mt5.connected` / `mt5_connected` | `true` |
| `trade_allowed` | `true` |
| `server` / broker | non-empty |
| `login` | non-empty |
| `account_mode` | `demo` \| `contest` \| `real` |

## After restore

From any network:

```bash
curl -sS -D- https://gateway.quantforg.com/health | head
```

Must be HTTP 200 JSON (not Cloudflare 502 HTML/plain).
