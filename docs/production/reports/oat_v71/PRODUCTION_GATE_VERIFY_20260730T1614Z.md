# Production gate verification — post-bridge recovery

Generated: `2026-07-30T16:14Z`  
Agent: cloud (no Railway CLI login, no owner bearer for `/ite/ops/*`)

## 1) Is PR #39 deployed into the running production process?

**No. Evidence:**

| Check | Result |
|-------|--------|
| `gh pr view 39` | `state=OPEN`, `isDraft=true`, `mergedAt=null` |
| Base | `cursor/v7-1-acceptance-evidence` (not `main`) |
| `origin/main` tip | `de63a61` (2026-07-27) |
| `ite_cycle_market_context` on `main` | still `mt5_autotrading_enabled=False` (hardcoded) |
| `ite_cycle_market_context` on `acceptance-evidence` | still `mt5_autotrading_enabled=False` |
| PR #39 branch `ec3eb2d` | has `_read_mt5_autotrading_enabled` |
| GitHub Deployments | only **Preview** (Vercel) for `ec3eb2d` — no Production Railway deployment of that SHA |
| Live Railway `/api/v1/version` | `{"name":"QuantForg","version":"1.0.0","environment":"production"}` — **no git SHA** exposed |

Windows gateway **is** on 1.1.3 (separate host). Railway API process is **not** proven to include PR #39.

## 2) EXECUTION_ENABLED=true?

**Not verifiable from this agent.**

- `/ite/ops/auto-trading` and TOC/reliability endpoints require bearer → HTTP 401
- Railway CLI: `Unauthorized` (no login in cloud env)
- Last **repo** PRR snapshots (`institutional_prr_latest.json`) recorded `EXECUTION_ENABLED: false` (2026-07-23) — **stale**, not live proof of current Railway vars
- Code default: `execution_enabled=False` until env sets `EXECUTION_ENABLED=true`

Operator must confirm in Railway Variables (or authenticated `GET /api/v1/ite/ops/auto-trading` → `execution_enabled`).

## 3) Caller token (PR #38)?

**PR #38 also OPEN / not merged.** Same deploy gap.

- Live gateway still correctly rejects anonymous `/account` with `Invalid or missing gateway token` (expected)
- Whether Railway sends `Authorization` / `X-Gateway-Token` requires Railway logs or authenticated auto-trading `live.gateway` / `configuration` payload — not available here without token

## 4) Live cycle trace (what can be proven now)

```text
Market Data → Context → Safety → Signal → Risk → OMS → Gateway → MT5
```

| Step | Live evidence this run |
|------|------------------------|
| Gateway / MT5 | `/health`: `1.1.3`, `connected=true`, `bridge_available=true`, `mt5_autotrading_enabled=true`, `dlls_allowed=true`, session `attached` |
| Session filter (UTC) | ~16:14Z → `london_ny_overlap` (allowed by default policy) |
| Context AutoTrading flag | **Still hardcoded false in any process without PR #39** |
| Safety | Would emit `SAFETY_BLOCKED` / `"AutoTrading is disabled in MetaTrader 5"` when enrich also lacks the flag |
| Signal → Risk → OMS | **Not reached** while Safety fails closed on that flag |
| `execution_path_step` | No live Railway log stream in this environment |

Historical witness (repo, 2026-07-23): `cycle_outcome=safety_blocked`, `Session 'tokyo' not allowed` — different gate, Tokyo hours.

## First remaining production gate (evidence-based)

**PR #39 is not in the running Railway API process.**

Until `ec3eb2d` (or equivalent) is merged and Railway redeploys, the first reject remains:

```text
execution_path_step: Safety
result: FAIL
detail: AutoTrading is disabled in MetaTrader 5
abort_reason: SAFETY_BLOCKED
forwarded_to_oms: false
```

…even though live gateway health reports AutoTrading **true**.

## Operator checklist (no strategy / risk changes)

1. Merge PR #39 → deploy Railway from that commit (or promote branch Railway tracks)
2. Confirm Railway `EXECUTION_ENABLED=true`
3. Merge/deploy PR #38; set `MT5_GATEWAY_CALLER_TOKEN` (= Windows `MT5_GATEWAY_TOKEN`)
4. Authenticated poll: `GET /api/v1/ite/ops/auto-trading`  
   - expect `execution_enabled=true`, `facts.mt5`/live probes connected, `primary_blocker` null or next real gate  
   - `orchestrator.last_cycle` / `recent_execution_attempts` for `execution_path_step`
5. If still no order: capture exact `failed_reasons` / `Rejected because:` / `abort_reason` from that payload or Railway logs

## Not claimed

- No live MT5 ticket
- No live `EXECUTION_ENABLED` read
- No live caller-token match proof
