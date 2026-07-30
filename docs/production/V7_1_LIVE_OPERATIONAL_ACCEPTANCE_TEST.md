# QuantForg v7.1 Live Operational Acceptance Test (OAT)

Generated: `2026-07-30T12:08:59.325732+00:00`

**Declaration: QUANTFORG v7.1 LIVE PRODUCTION NOT ACCEPTED**

## Soak file validation (this workspace)

| Field | Value |
|---|---|
| Path | `docs/production/reports/oat_v71/soak_24h_metrics.jsonl` |
| Bytes in this git workspace / remotes | **139021** |
| Bytes confirmed on Windows host | **250073** |
| Size match | **False** |
| First timestamp | `2026-07-27T18:35:38.2499607Z` |
| Last timestamp | `2026-07-28T10:45:19.9132149Z` |
| Duration | **16.162h** (need ≥24h) |
| Age of last sample | **49.394h** |
| Gateway ok/bad | 504/1 |
| MT5 connected/disconnected | 504/0 |
| Session attached samples | 504 |
| Railway ok/bad | 238/267 |
| Reconnect events (connected false→true) | 0 |
| Sampling gaps >3min | 1 (largest ~6.1h on 2026-07-28) |

## Live gateway (now)

- Reachable: **True**
- Connected / session / server: **True** / `attached` / `Weltrade-Real`
- Heartbeat: `2026-07-30T12:09:00.135339+00:00`

## Remaining verified blocker

**Soak evidence not synchronized into git.**

Windows has `250073` bytes; this verifier still sees `139021` bytes.
This cloud agent cannot read `C:\Users\P7 PROVIDER\QuantForg\...` directly.

On the Windows host, use normal git (no special script required):

```powershell
cd "C:\Users\P7 PROVIDER\QuantForg"
git checkout cursor/v7-1-production-stabilization-bc83
git pull
git add docs/production/reports/oat_v71/soak_24h_metrics.jsonl docs/production/reports/oat_v71/soak_24h_latest.json
git status
git commit -m "Sync production soak evidence from Windows host"
git push origin cursor/v7-1-production-stabilization-bc83
```

After that push lands, re-run PAT/OAT on the updated file.

JSON: `docs/production/reports/oat_v71/soak_validation_20260730.json`
