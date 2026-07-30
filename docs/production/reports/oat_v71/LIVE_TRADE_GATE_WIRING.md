# Live trade path gate wiring — evidence + fix

Generated: `2026-07-30T16:15Z`  
Branch: `cursor/live-trade-gate-wiring-bc83`

## Live evidence (MT5 bridge OK — not re-investigated)

`GET https://gateway.quantforg.com/health` (this run):

- `gateway_version=1.1.3`
- `bridge_available=true`
- `connected=true`
- `session_mode=attached`
- `server=Weltrade-Real`
- `terminal_trade_allowed=true`
- `mt5_autotrading_enabled=true`
- `dlls_allowed=true`

Anonymous protected routes correctly return `Invalid or missing gateway token`.

## Decision cycle (code)

```text
run_forever
  → build_ite_cycle_market_context   [Market Data]
  → run_auto_cycle
       → evaluate_auto_trading       [Safety]
       → decision_pipeline.run       [Signal → Risk → Eligibility]
       → continuous_ops pause
       → ExecutionBridge.handle
       → GuardedOMS → order_send → Gateway → MT5
```

## Exact implementation bug blocking AutoTrading safety

`ite_cycle_market_context.py` **hardcoded**:

```python
mt5_autotrading_enabled=False
```

even when live `/health` reports `mt5.mt5_autotrading_enabled=true`.

Orchestrator then did:

```python
mt5_at = enrich[...] if enrich known else False  # did NOT fall back to ctx
```

Safety gate key `mt5_autotrading` → `"AutoTrading is disabled in MetaTrader 5"`  
→ `cycle_outcome=safety_blocked` / `abort_reason=SAFETY_BLOCKED`  
→ **OMS never called** (no strategy change; false negative wiring).

Enrich previously required `GatewayMT5Client.gateway_health()` only. When the
API used MockMT5Client (missing caller token), public `/health` flags were
ignored even though `LiveProbeCollector` already fetched them.

## Historical log evidence (repo witness)

`docs/production/reports/live_execution_witness.jsonl` (2026-07-23):

- `cycle_outcome=safety_blocked`
- `abort_reason=SAFETY_BLOCKED`
- `safety_failed_reasons=["Session 'tokyo' not allowed"]`

That is a **real** session filter reject (UTC Tokyo hours). At investigation
time (~16:00 UTC) session classifier is London / London-NY overlap — allowed.

PAT startup tick earlier today (bridge down era) also showed continuous-ops
pause: `broker unavailable`, `stale heartbeat:mt5` — expected while
`connected=false`; should clear once probes see attached session.

## Fix (this PR)

1. Read AutoTrading from gateway `/health` in market context (never hardcode False)
2. Persist `LiveProbeCollector.last_health_payload`; enrich falls back to it / public `/health`
3. Orchestrator falls back to `ctx.mt5_autotrading_enabled` like account flags

## Still required for live fills (config — not strategy)

Railway must have:

- `EXECUTION_ENABLED=true`
- `MT5_GATEWAY_BASE_URL` + `MT5_GATEWAY_CALLER_TOKEN` (or `MT5_GATEWAY_TOKEN` alias from PR #38)
- Ops mode LIVE/CANARY, kill switch disarmed

Without those, safety/bridge abort with `EXECUTION_ENABLED=false` /
`execution_disabled` — by design.

## Not claimed

No live MT5 ticket observed in this cloud environment (no Railway log stream /
owner token for `/ite/ops/auto-trading`). After deploy, confirm Railway logs
show `execution_path_step` PASS through OMS or the next exact `Rejected because:`.
