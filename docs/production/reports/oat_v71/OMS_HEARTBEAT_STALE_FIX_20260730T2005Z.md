# OMS stale heartbeat — root cause and fix

Generated: `2026-07-30T20:05Z`

## Verified symptom

```
Scheduler PASS
Ops Mode PASS
Execution Enabled PASS
Gateway Connectivity PASS
AI Decision = NO_TRADE
abort_reason = ignored_action
continuous_ops_pause_new_entries
stale heartbeat:oms
OMS never called / MT5 never reached
```

## OMS heartbeat architecture

| Role | Location |
|------|----------|
| Producer (reliability) | `InstitutionalIteRuntime.tick_health` → `reliability.heartbeats.publish(OMS)` |
| Producer (continuous ops) | `ContinuousOperationController.tick` → `heartbeats.publish(OMS)` when `oms_ok` |
| Consumer (pause) | `evaluate_new_entry_pause(missing_heartbeats=…)` → `stale heartbeat:oms` |
| Consumer (cycle) | `_run_cycle` reads `_last_continuous_op.pause` → demotes BUY/SELL → NO_TRADE |
| Timeout | `HeartbeatRegistry.timeout_seconds` (was 30s; scheduler default 60s) |

## Root cause (implementation bug)

`oms_ok` was derived as:

```python
railway_api_up AND gateway_available
```

Railway self-probe (`RAILWAY_PUBLIC_DOMAIN` → GET `/health`) often fails or is unset inside the API container. That set `oms_ok=False` even when Gateway Connectivity already PASSed.

Then `ContinuousOperationController.tick`:

1. Did **not** publish OMS heartbeat
2. Added `"oms"` to `failed_deps`
3. Pause reason: `stale heartbeat:oms`
4. Cycle demoted signal to NO_TRADE → Bridge `ignored_action`

Heartbeat protection itself is correct — the **OMS liveness signal was wrong**.

## Fix

1. `_oms_submit_path_healthy(probes)` → `gateway_available` only (OMS submits via gateway)
2. Railway API remains its own heartbeat component (`RAILWAY_API`)
3. Align heartbeat timeout to `≥ 2× scheduler interval + 5s` so age-based missing() cannot false-trigger between ticks
4. Continuous ops also merges registry age-missing for gateway/mt5/oms

No strategy change. No Safety/Risk threshold change. No forced BUY/SELL. Heartbeat pause retained when gateway is truly down.

## Tests

`tests/unit/test_oms_heartbeat_wiring.py` — 15 related tests green with continuous suite.

## After deploy

Expect: when gateway healthy, `stale heartbeat:oms` clears. Next cycle may still NO_TRADE for **legitimate** signal/risk reasons — report that as the next blocker if present.
