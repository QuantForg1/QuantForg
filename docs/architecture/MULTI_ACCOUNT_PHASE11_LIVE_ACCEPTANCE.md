# Phase 11 — LIVE Broker Connection Acceptance

**Status:** EXECUTED — **0 / 7** brokers have genuine `VERIFIED_LIVE` authentication evidence.  
**Date (UTC):** 2026-11-13  
**Owner directive:** Real LIVE MT5 auth acceptance for all seven brands; no fake verification; no real orders.  
**Baseline (PR #243 / `main`):** `c95db3b42ecde99592d29e337061c25119904cc7`  
**This branch:** `feat/phase11-live-broker-acceptance` (docs + LIVE credential fail-closed messaging)

> Selectability ≠ LIVE-connected. Candidate servers ≠ confirmed LIVE. DEMO evidence ≠ LIVE evidence.

---

## A. Release evidence

| Item | Value |
|---|---|
| Base commit | `c95db3b42ecde99592d29e337061c25119904cc7` (PR #243 — Universal LIVE Broker Access) |
| Final commit (this acceptance) | See PR merge SHA after merge of `feat/phase11-live-broker-acceptance` |
| Prior release | PR #243 merged to `main` |
| CI | Required checks on acceptance PR (Black / mypy / unit / frontend as applicable) |
| Railway Production | Service **QuantForg** · Online · `https://quantforg-production.up.railway.app` · Environment ID `cb96aa83-7ace-470a-9e98-d52a1634a446` |
| Railway Production SHA | `/api/v1/health` → `c95db3b42ecde99592d29e337061c25119904cc7` · `/health/live` → 200 `{"status":"ok"}` |
| Railway Staging | Same project; safety flags remain OFF (dispatch / LIVE submit) |
| Vercel `frontend` / `quant-forg` | Public `/broker` served from production domain |
| Production domain | `https://www.quantforg.com/broker` → **HTTP 200** (2026-11-13) |
| Apex | `https://quantforg.com/broker` → **308** redirect (expected) |

Code changes in this phase are **messaging / inventory / documentation only**. No trading-core, OMS, gateway, or safety-flag changes.

---

## B. Seven-broker results

Evidence source for DEMO rows: host `var/mt5_broker_verification.json` (updated_at `2026-11-13T03:46:52+00:00`).  
LIVE credential inventory: `deploy/mt5_worker_agent/local.env` presence check via resolver (values never printed).  
LIVE auth attempts: fail-closed before terminal init when `QF_LIVE_*` triples are incomplete.

| Broker | LIVE server | Credentials present | MT5 auth | Account mode | Evidence | Final status |
|---|---|---|---|---|---|---|
| Weltrade | `Weltrade-Real` (catalogue seed; LIVE singleton not re-authed) | No `QF_LIVE_WELTRADE_*` triple | Not attempted (singleton protected) | Production LIVE path observed read-only (PID protected) | DEMO only: `Weltrade-Demo` / `demo_verified` | `NOT_TESTED` (protected singleton) + `BLOCKED_MISSING_LIVE_CREDENTIALS` for isolated portable verify |
| XM | No confirmed LIVE server provisioned | No `QF_LIVE_XM_*` (DEMO only present) | Fail-closed; DEMO material **not** reused | — | DEMO only: `XMGlobal-MT5 2` / `demo_verified` | `BLOCKED_MISSING_LIVE_CREDENTIALS` |
| Exness | — | No `QF_LIVE_EXNESS_*` | Fail-closed (`live_credentials_not_provided`) | — | None LIVE | `BLOCKED_MISSING_LIVE_CREDENTIALS` |
| HFM | — | No `QF_LIVE_HFM_*` | Not attempted | — | None LIVE | `BLOCKED_MISSING_LIVE_CREDENTIALS` |
| IC Markets | — | No `QF_LIVE_IC_MARKETS_*` | Not attempted | — | None LIVE | `BLOCKED_MISSING_LIVE_CREDENTIALS` |
| Pepperstone | — | No `QF_LIVE_PEPPERSTONE_*` | Not attempted | — | None LIVE | `BLOCKED_MISSING_LIVE_CREDENTIALS` |
| FP Markets | — | No `QF_LIVE_FP_MARKETS_*` | Not attempted | — | None LIVE | `BLOCKED_MISSING_LIVE_CREDENTIALS` |

**Genuine successful LIVE authentications this phase: 0 / 7.**

### What already works (not LIVE proof)

- All seven brokers are **customer-selectable** on `/broker` (PR #243).
- LIVE is the primary account type; DEMO remains optional.
- Confirmed vs candidate server distinction and manual server entry are in the catalogue UX.
- Evidence store persists DEMO verifies for Weltrade + XM only.
- LIVE credential resolver **does not** fall back to `QF_DEMO_*`.
- Worker refuse path for `--env live` without complete `QF_LIVE_*` keys (exact key names, no DEMO fallback hint).

### What is only a candidate / assumption

- Catalogue LIVE server seeds / documented candidates for non-Weltrade brands.
- Server names without MT5 `account_info` trade_mode proof.
- Any prior DEMO `connectable=true` row.

### What has real authentication evidence

- **DEMO:** XM (`XMGlobal-MT5 2`) and Weltrade (`Weltrade-Demo`) only.
- **LIVE:** none recorded in `mt5_broker_verification.json` for any of the seven brands under Phase 11.

---

## C. Infrastructure

| Item | Observation |
|---|---|
| Windows host | Existing QuantForg MT5 worker host (no new VPS) |
| LIVE Program Files terminal | Path `C:\Program Files\MetaTrader 5\terminal64.exe` · PID **10528** classified `LIVE_PROTECTED` · working set ~41 MB |
| Portable slots | Under `C:\QuantForg-Workspace\mt5_worker_slots` · soft portable concurrency ~1 |
| Capacity | Free RAM soft constraint (~750 MB observed earlier) · sequential verify only |
| Queue | No LIVE verify jobs enqueued (all blocked on credentials) |
| Worker heartbeat | Registration path unchanged; not required for credential-blocked acceptance |
| Process cleanup | No force-kill; LIVE singleton not restarted |
| New VPS | **Not provisioned** |

---

## D. Safety

Explicit confirmation at acceptance time:

```text
MULTI_ACCOUNT_LIVE_SUBMIT_ENABLED=false
FORCE_FIRST_TRADE=false
QF_ALLOW_WORKER_ON_LIVE_TERMINAL=false
MULTI_ACCOUNT_DISPATCH_ENABLED=false   # production remains off
```

| Control | Result |
|---|---|
| Production LIVE submit | OFF |
| Production dispatch | OFF |
| FORCE_FIRST_TRADE | OFF |
| LIVE terminal worker override | OFF |
| Weltrade singleton | Protected (read-only PID classification; no reconnect / kill / slot reuse) |
| `order_send` / open / close / modify | **Orders submitted: 0** |
| Automated LIVE trading enabled to prove connectivity | No |

---

## E. Remaining blockers

### Missing LIVE credentials (exact keys)

Provision on the Windows host only — gitignored `deploy/mt5_worker_agent/local.env` — never in chat, GitHub, or CI logs:

```text
QF_LIVE_WELTRADE_LOGIN=
QF_LIVE_WELTRADE_PASSWORD=
QF_LIVE_WELTRADE_SERVER=

QF_LIVE_XM_LOGIN=
QF_LIVE_XM_PASSWORD=
QF_LIVE_XM_SERVER=

QF_LIVE_EXNESS_LOGIN=
QF_LIVE_EXNESS_PASSWORD=
QF_LIVE_EXNESS_SERVER=

QF_LIVE_HFM_LOGIN=
QF_LIVE_HFM_PASSWORD=
QF_LIVE_HFM_SERVER=

QF_LIVE_IC_MARKETS_LOGIN=
QF_LIVE_IC_MARKETS_PASSWORD=
QF_LIVE_IC_MARKETS_SERVER=

QF_LIVE_PEPPERSTONE_LOGIN=
QF_LIVE_PEPPERSTONE_PASSWORD=
QF_LIVE_PEPPERSTONE_SERVER=

QF_LIVE_FP_MARKETS_LOGIN=
QF_LIVE_FP_MARKETS_PASSWORD=
QF_LIVE_FP_MARKETS_SERVER=
```

**Secure provisioning (owner):**

1. On the Windows MT5 host, edit `deploy/mt5_worker_agent/local.env` (gitignored).
2. Or use a secure PowerShell prompt that sets process env without echoing values.
3. Validate presence without printing secrets:

```powershell
.\deploy\mt5_worker_agent\check_broker_credentials.ps1
```

4. Re-run Phase 11 sequential LIVE verify per broker with `--env live` on a **portable** slot only.
5. Confirm `account_info` trade_mode / environment metadata is LIVE before recording `VERIFIED_LIVE`.

### Other blockers

| Broker | Blocker |
|---|---|
| Weltrade | Isolated LIVE re-auth **NOT_TESTED** — production singleton must not be disrupted; dedicated `QF_LIVE_WELTRADE_*` + portable path required for acceptance-grade re-proof |
| All seven | No confirmed LIVE server names authenticated via MT5 metadata this phase (Weltrade catalogue seed is operational history, not Phase 11 portable evidence) |
| Capacity | Soft portable cap ~1; free RAM previously near soft floor — keep sequential |

---

## F. Final conclusion

**0 of 7** brokers have genuine successful LIVE authentication evidence under Phase 11.

PR #243 correctly delivered universal **selectability** and LIVE-first UX. Phase 11 correctly refuses to promote that into `VERIFIED_LIVE` without owner-provisioned `QF_LIVE_*` triples and portable MT5 auth metadata.

Re-run sequential LIVE acceptance after credentials are present; do not flip LIVE submit, dispatch, `FORCE_FIRST_TRADE`, or `QF_ALLOW_WORKER_ON_LIVE_TERMINAL`.

---

## Initial audit summary (pre-change)

| Area | Finding |
|---|---|
| PR #243 / `main` | Seven brands selectable; no Pending/Verified badges as connection gates; candidates + manual server |
| Catalogue / adapters | Broker-slug validation; LIVE vs DEMO credential namespaces |
| Evidence store | XM + Weltrade **demo_verified** only |
| Windows worker | LIVE Program Files protected; portable slots available under soft cap |
| Safety | LIVE submit / force-first / live-terminal override OFF |
| Credentials | **0** complete `QF_LIVE_*` triples; XM DEMO only |
| Safe to test without LIVE ops impact | Fail-closed credential checks; Weltrade read-only PID inspect; no portable LIVE auth without creds |

---

## Customer experience notes (`/broker`)

Inspected production domain HTTP 200. Catalogue contract (PR #243):

- Seven brokers selectable; LIVE primary; DEMO optional.
- Confirmed servers vs candidates; manual entry where supported.
- Connection lifecycle separate from selectability.
- Connected state must remain evidence-backed (no auto-authorization for automated trading).

Full authenticated customer UX walkthrough with a disposable LIVE test identity was **not** performed (no LIVE credentials; no production customer identity used as disposable test).
