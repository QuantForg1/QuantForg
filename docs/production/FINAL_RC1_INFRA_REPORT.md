# FINAL RC1 INFRA REPORT

Generated: `2026-07-31T12:41:00Z`  
Mission: **INFRASTRUCTURE RECOVERY RC1**  
Branch: `cursor/infra-recovery-rc1-bc83`

## Final Recommendation

**NOT READY**

Evidence does not support `READY FOR LIMITED LIVE PILOT` or `READY FOR FULL PRODUCTION`.

No strategy / AI / scoring / trading-logic changes.  
No merge to `main`.  
No production deployment.  
No automatic migrations.

---

## P0 — MT5 Gateway restore

| Check | Required | Observed | Result |
|-------|----------|----------|--------|
| `GET https://gateway.quantforg.com/health` | HTTP 200 | HTTP **502** (Cloudflare origin failure) | **FAIL** |
| No 502 | Origin up via tunnel | `cf-ray` present; body `error code: 502` | **FAIL** |

Evidence:

- `docs/production/infra_recovery_evidence/public_probes.json`
- `docs/production/infra_recovery_evidence/gateway_authenticated_probes.json`
- `docs/production/infra_recovery_evidence/authenticated_infra_probes.json` → `gateway.status=DOWN`

**Root cause (diagnosed):** Cloudflare reaches DNS for `gateway.quantforg.com`, but the Windows origin behind the tunnel (gateway on `:8765` and/or `cloudflared`) is not serving. Cloud Linux agents cannot restart the Windows VPS process.

**Operator action (Windows VPS only):** elevated PowerShell:

```powershell
cd "C:\Users\P7 PROVIDER\QuantForg"
.\deploy\mt5_gateway\deploy_main_gateway.ps1
# then confirm public:
Invoke-RestMethod https://gateway.quantforg.com/health
```

Runbook: `docs/production/infra_recovery_evidence/WINDOWS_GATEWAY_RECOVERY.md`

---

## P0 — Reconnect MT5

| Check | Required | Observed | Result |
|-------|----------|----------|--------|
| Connected | `mt5.connected=true` | `DISCONNECTED` | **FAIL** |
| Trade Allowed | `trade_allowed=true` | unreachable (gateway 502) | **FAIL** |
| Broker | server/broker name | unreachable | **FAIL** |
| Account | login + account_mode | unreachable | **FAIL** |
| Mock | prefer live gateway | `mt5_use_mock=true` in Railway settings probe | **FAIL** |

Evidence: `authenticated_infra_probes.json` → `mt5.status=DISCONNECTED`, `use_mock=true`.

---

## P1 — Railway staging + RC1 endpoints

| Check | Required | Observed | Result |
|-------|----------|----------|--------|
| Staging environment | usable `staging` env | CLI: “already exists”; `environment list --json` shows **only production** | **BLOCKED** |
| Staging deploy | service online | `https://quantforg-staging.up.railway.app/health` → **404 Application not found** | **FAIL** |
| RC1 endpoint | HTTP 200 (auth) | Production tip still **404** on `/api/v1/ite/ops/rc1-production-validation` | **FAIL** |
| Local wiring | route works | Prior local TestClient OperatorUser → **200** | PASS (local only) |

Evidence: `railway_staging_blocked.json`, `public_probes.json`.

**Operator action:** Railway dashboard → resolve orphaned/hidden `staging` env or create service under a visible staging environment; deploy RC1 branch; verify authenticated 200. Do **not** auto-deploy production.

---

## P1 — Authenticate Operator Services

| Component | Required | Observed | Result |
|-----------|----------|----------|--------|
| Gateway | HEALTHY | **DOWN** | **FAIL** |
| OMS | HEALTHY | **ENABLED** (settings-only; not full runtime HEALTHY) | **FAIL** |
| MT5 | HEALTHY | **DISCONNECTED** | **FAIL** |
| AI | HEALTHY | **SETTINGS_ONLY** | **FAIL** |
| Ops desk probe | authenticated `services-health` | HTTP **401** without OWNER/ADMIN bearer | **FAIL** |

No component was reclassified from UNKNOWN/DOWN to HEALTHY without evidence.

Evidence: `authenticated_infra_probes.json`, public health probes (API process healthy; ops routes auth-gated).

---

## P1 — Supabase schema / migrations

| Check | Result |
|-------|--------|
| Remote connect via Railway `DATABASE_URL` (pooler) | **PASS** |
| Remote `supabase_migrations.schema_migrations` count | **49** |
| Repo supabase migrations | **49** |
| Pending (repo not on remote) | **None** |
| Migrations applied by this run | **No** (`applied_migrations=false`) |
| Production auto-migrate | **Blocked** |

Evidence:

- `docs/production/infra_recovery_evidence/migration_audit.json`
- `docs/production/infra_recovery_evidence/RC1_MIGRATION_AUDIT.md`
- `docs/production/RC1_MIGRATION_REPORT.md`

Supabase MCP in this agent only lists unrelated project `Jimvio`; QuantForg DB audited via Railway DSN only.

---

## P1 — RC1 Paper / Shadow / Acceptance

| Gate | Recommendation | Result |
|------|----------------|--------|
| Paper validation | **NOT READY** (infra attached) | Ran |
| Shadow validation | **NOT READY** (infra attached) | Ran |
| Acceptance gates | 1/7 pass (migration audit policy only) | **FAIL** |

Evidence:

- `docs/production/infra_recovery_evidence/RC1_PAPER_VALIDATION.md`
- `docs/production/infra_recovery_evidence/RC1_SHADOW_VALIDATION.md`
- `docs/production/infra_recovery_evidence/rc1_paper_result.json`
- `docs/production/infra_recovery_evidence/rc1_shadow_result.json`
- `docs/production/infra_recovery_evidence/acceptance_gates.json`

Quality/Confidence floors remain **80/80**. No threshold/weight/risk changes.

---

## What this agent could restore remotely

| Item | Status |
|------|--------|
| Gateway Windows process / Cloudflare tunnel | **Cannot** — requires Windows VPS operator |
| Railway staging env linkage / deploy | **Blocked** — token cannot list/link staging; no prod deploy |
| Operator JWT for `services-health` | **Not available** in agent secrets (401) |
| Migration audit (read-only) | **Done** — schema appears aligned; nothing applied |
| Paper/shadow pipeline (local + live health) | **Done** — NOT READY |
| Production tip / merge | **Not done** (policy) |

---

## Path to change recommendation

### → READY FOR LIMITED LIVE PILOT (minimum)

1. Windows: `deploy_main_gateway.ps1` → public `/health` **200**; `/account` Connected + Trade Allowed + Broker + Account.
2. Railway: visible staging env + deploy RC1 endpoints → authenticated **200**.
3. Operator bearer: `services-health` shows Gateway / OMS / MT5 / AI **HEALTHY** (no UNKNOWN/DOWN).
4. Staging paper then shadow acceptance **PASS** with floors intact.
5. Migration audit still clean; staging-only applies if ever needed — never auto prod.

### → READY FOR FULL PRODUCTION

All Limited Pilot items, plus production deploy of reviewed RC1 tip under explicit human approval, soak evidence, and signed release — **out of scope for this mission**.

---

## Explicit non-actions (policy)

- No merge  
- No production deployment  
- No automatic migrations  
- No strategy / AI / scoring / trading-logic changes  
