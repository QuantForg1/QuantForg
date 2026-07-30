# Soak disconnect RCA — v7.1 OAT Step 5

Generated: 2026-07-29T01:20Z (approx)
Updated: 2026-07-30T13:25Z

## Evidence

Source: `docs/production/reports/oat_v71/soak_24h_metrics.jsonl`

| Metric | Value |
|---|---|
| First sample | `2026-07-27T18:35:38Z` |
| Last sample | `2026-07-28T18:35:18Z` |
| Span | ~23.994 h |
| Connected samples | 601 |
| Disconnected samples | 305 |
| Gateway HTTP fails | 2 |
| Railway sample fails | 287 |
| Connected→Disconnected transitions | **1** |

Single dropout:

- At `2026-07-28T12:38:14Z`: `connected=true → false` (Railway still ok)
- Remained disconnected through soak end (`2026-07-28T18:35:18Z`)
- Live probe after soak: gateway healthy again, MT5 attached (new gateway PID observed)

## Root cause (software)

Gateway heartbeat loop previously required `diagnostics.connected` to stay true before any further heartbeat/reconnect work:

```text
should_beat = connected AND creds
if not should_beat: continue   # permanent skip once connected=False
```

After a failed reconnect burst (attached sessions often have empty password and rely on terminal still being logged in), `connected` was set false and **reconnect was never attempted again** until process restart / manual attach.

Classification:

| Layer | Role in this soak window |
|---|---|
| Application gateway reconnect loop | **Verified defect** — abandoned session after failed burst |
| MT5 terminal / broker | Likely initial trigger (IPC/session blip at 12:38Z) — environment |
| Railway FE/API | Intermittent sample timeouts; not the MT5 disconnect cause |
| QuantForg trading strategy / OMS | Not implicated |

## Fix status (updated 2026-07-30)

**Landed in git** on `cursor/v7-1-acceptance-evidence` (cherry-picked from `de992f1`):

`services/mt5_gateway/runtime.py` `_heartbeat_loop` now:

- While credentials remain, keeps attempting reconnect even when `connected=False`
- After max-attempt bursts, cools down then starts a new burst (does not permanently abandon)
- Intentional `disconnect()` still clears credentials and stops reconnect

Unit coverage: `TestMT5GatewayReconnectLoop` in `tests/unit/test_mt5_gateway.py`

Gateway package version bumped to **1.1.1** (`gateway_version` on `/health`) for deploy confirmation.

## Soak acceptance status

**Not yet accepted for release.** Prior synced soak (`2026-07-27`→`2026-07-28`) is **pre-fix evidence**. After Windows deploy of 1.1.1, run a fresh ≥24h soak with:

- disconnect samples near zero (or brief blips that self-heal within minutes)
- single gateway worker
- MT5 attached for the majority of samples
