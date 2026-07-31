# FINAL GATEWAY RECOVERY REPORT

Generated: `2026-07-31T12:51:30Z`  
Mission: **P0 Gateway Recovery**  
Branch: `cursor/p0-gateway-recovery-bc83`

## Final Recommendation

**NOT READY**

Evidence does not support `READY FOR LIMITED LIVE PILOT` or `READY FOR FULL PRODUCTION`.

No AI / strategy / MTF / liquidity / score pipeline / risk engine changes.  
No merge.  
No production deployment.  
No automatic migrations.

---

## Acceptance matrix

| Gate | Required | Observed | Result |
|------|----------|----------|--------|
| Gateway `GET /health` | HTTP 200 | HTTP **502** (Cloudflare origin failure) | **FAIL** |
| Cloudflare tunnel healthy | Origin reachable | Edge `/cdn-cgi/trace` **200**; origin **502** | **FAIL** |
| Windows service running | Listener on `:8765` | Not verifiable / not reachable from cloud agent | **FAIL** |
| MT5 Connected | true | `DISCONNECTED` | **FAIL** |
| Trade Allowed | true | Unreachable | **FAIL** |
| Broker | non-empty | Unreachable | **FAIL** |
| Account | login + mode | Unreachable | **FAIL** |
| `mt5_use_mock=false` | false | Railway var set; `railway run` settings → **false** (`--skip-deploys`) | **PASS** (config) |
| Gateway / OMS / MT5 / AI HEALTHY | all | DOWN / ENABLED / DISCONNECTED / SETTINGS_ONLY | **FAIL** |
| RC1 `GET /ite/ops/rc1-production-validation` | HTTP 200 | Production tip **404**; local TestClient **200** | **FAIL** (deployed tip) |
| Paper validation | readiness | **NOT READY** | **FAIL** |
| Shadow validation | readiness | **NOT READY** | **FAIL** |

Evidence root: `docs/production/gateway_recovery_evidence/`  
Gates JSON: `acceptance_gates.json`

---

## P0 — Windows MT5 Gateway

### Diagnosis

- `https://gateway.quantforg.com/health` → **502** (`server: cloudflare`, `cf-ray` present).
- Cloudflare edge is up (`/cdn-cgi/trace` → 200).
- Origin behind the tunnel (Windows gateway `:8765` and/or `cloudflared`) is not serving.
- This Linux cloud agent **cannot** execute `deploy/mt5_gateway/deploy_main_gateway.ps1` on the VPS.

### Operator action (required)

Elevated PowerShell on Windows host `C:\Users\P7 PROVIDER\QuantForg`:

```powershell
.\deploy\mt5_gateway\deploy_main_gateway.ps1
# or full P0 wrapper:
.\deploy\mt5_gateway\p0_gateway_recovery.ps1
```

Runbook: `docs/production/infra_recovery_evidence/WINDOWS_GATEWAY_RECOVERY.md`

Success proof must show public `/health` HTTP 200 and verify JSON with Connected / Trade Allowed / Broker / Account.

---

## Mock mode

| Item | Value |
|------|-------|
| `railway variable set MT5_USE_MOCK=false -s QuantForg --skip-deploys` | Applied |
| Process settings via `railway run` | `mt5_use_mock=false` |
| Production process restart | **Not performed** (no production deployment) |

Evidence: `mock_mode_setting.json`

---

## RC1 endpoints

| Surface | Status |
|---------|--------|
| Production `.../ite/ops/rc1-production-validation` | **404** |
| Local OperatorUser TestClient (Host: localhost) | **200** |
| Staging host | Application not found |
| Production redeploy of RC1 tip | **Blocked by mission policy** |

Evidence: `rc1_endpoint_local_200.json`, `rc1_redeploy_policy.json`, `public_probes.json`

Verifier fix (host header): `scripts/verify_rc1_endpoint_local.py` — TrustedHostMiddleware rejected `testserver` under Railway allowed hosts.

---

## Paper / Shadow / Acceptance

| Run | Recommendation |
|-----|----------------|
| Paper | **NOT READY** |
| Shadow | **NOT READY** |
| Acceptance gates | **1/10** (`mt5_use_mock_false` only) |

Quality/Confidence floors remain **80/80**.

---

## What changed in this branch

1. `deploy/mt5_gateway/p0_gateway_recovery.ps1` — Windows wrapper (deploy + tunnel hints + public 200 gate).
2. Runbook pointer update for P0 wrapper.
3. `MT5_USE_MOCK=false` on Railway with `--skip-deploys` (no prod redeploy).
4. Local RC1 verifier Host fix + gateway recovery evidence pack.
5. This report.

## Explicit non-actions

- Did not restart Windows gateway (no VPS access)
- Did not merge
- Did not deploy production
- Did not apply migrations
- Did not modify AI / strategy / MTF / liquidity / score / risk logic

---

## Path to READY FOR LIMITED LIVE PILOT

1. Windows: run `p0_gateway_recovery.ps1` → public `/health` **200**.
2. Confirm Connected, Trade Allowed, Broker, Account.
3. Approved Railway restart/redeploy so running API picks up `MT5_USE_MOCK=false` (still not an RC1 code merge).
4. Operator-authenticated `services-health`: Gateway / OMS / MT5 / AI **HEALTHY**.
5. Deploy RC1 routes to staging (preferred) or approved tip → authenticated **200**.
6. Paper then shadow acceptance **PASS**.

Only then may recommendation leave **NOT READY**.
