# RC1 — Gateway

## Role

Windows MT5 Gateway is the only live order adapter. Railway never talks to MT5 DLLs directly.

## Health probe

`GET {MT5_GATEWAY_BASE_URL}/health`

LiveProbeCollector uses this for:

- Gateway availability
- MT5 connected (from health payload)
- Cloudflare tunnel / CF headers when applicable

## Tokens

- Gateway auth token is server-side only (`MT5_GATEWAY_*` secrets).
- Never expose gateway tokens to the browser or audit payloads (sanitize strips secrets).

## Failure modes

| Symptom | Check |
| --- | --- |
| Gateway down | Tunnel process, Windows service, CF route |
| MT5 disconnected | Terminal login, broker session |
| High latency | CF path, Windows host load, broker |

Do not bypass the gateway for “faster” execution — it is the safety boundary.
