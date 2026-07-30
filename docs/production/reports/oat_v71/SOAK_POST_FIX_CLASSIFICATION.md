# Soak vs gateway reconnect fix — classification

Generated: `2026-07-30T12:45Z`

## Question

Does synchronized soak evidence (`9837123` → `soak_24h_metrics.jsonl`) reflect a production run **after** the gateway reconnect fix was deployed?

## Verdict

**No. This is pre-fix evidence.**

A post-fix ≥24h soak is still required. Acceptance criteria are unchanged; do not force PASS.

## Timeline

| Event | When |
|---|---|
| Soak first sample | `2026-07-27T18:35:38Z` |
| MT5 dropout (connected true→false) | `2026-07-28T12:38:14Z` |
| Soak last sample (still disconnected) | `2026-07-28T18:35:18Z` |
| RCA documenting defect | ~`2026-07-29T01:20Z` (**after** soak ended) |
| Evidence git sync commit `9837123` | `2026-07-30T12:31Z` (sync only; same sample window) |

## Code reality (critical)

Docs previously claimed the reconnect fix was applied in `services/mt5_gateway/runtime.py`.

**That claim is false for all reviewed refs** (`main`, `cursor/v7-1-acceptance-evidence`, `cursor/v7-1-production-stabilization-bc83`):

```python
# services/mt5_gateway/runtime.py _heartbeat_loop (unchanged since f66173c 2026-07-20)
should_beat = self.diagnostics.connected and self._creds is not None
if not should_beat:
    continue
```

- No commit after the soak changes this loop.
- Claimed unit test `test_attached_session_recovers_after_connected_flag_drop` is **absent**.
- Therefore the reconnect fix was **never committed and never deployed** to the Windows production gateway.

## Why the disconnect window exists in this soak

Matches the still-present defect: once `connected=False`, heartbeat/reconnect work is skipped permanently until process recycle/manual attach. Observed: ~5.95h unmanaged disconnect, 0 false→true reconnects, heartbeat frozen at `2026-07-28T12:36:33Z` while samples continued.

That is a genuine production defect **during this soak**, but it is **not** post-fix failure evidence.

## TEST_9 / OAT Step 5 rejection mapping

| Gate | Exact rejection reason for this soak | Category |
|---|---|---|
| PAT `TEST_9_LONG_RUN` | duration **23.994h &lt; 24h** | duration shortfall (same pre-fix file) |
| PAT `TEST_9_LONG_RUN` | last sample age **~42h &gt; 2h** freshness | **stale evidence** |
| OAT Step 5 quality | 305 disconnect samples / 0 self-heal / ~5.95h unmanaged window | **pre-fix evidence** of the reconnect defect (fix never landed) |

## Required next step

1. Land and deploy the reconnect-loop fix to the Windows gateway.
2. Run a **new** ≥24h soak after that deploy.
3. Re-run PAT/OAT only against that post-fix soak.
