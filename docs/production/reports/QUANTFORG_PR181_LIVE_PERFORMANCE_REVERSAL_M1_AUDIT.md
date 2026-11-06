# QUANTFORG PR #181 — LIVE Performance, Reversal Effectiveness & M1 Profitability Audit

**Audit time (UTC):** 2026-11-06 ~10:00–10:10  
**Production baseline claimed:** PR #180 / `e4f15e40`  
**Instrument:** XAUUSD  
**Method:** Public health probes + Railway filtered variables + gateway broker-authoritative deals/positions + Railway log samples. Owner API ops endpoints were **not** refreshed (local `SUPABASE_*` empty).

**Principles honored:** LIVE trading left enabled. M1 OMS submit left OFF. Reverse-entry left OFF. Owner risk settings not changed. No real-money test orders. No invented P&L or backtests.

---

## 1. Production verification

| Check | Evidence | Result |
| --- | --- | --- |
| GitHub `main` | `gh api .../commits/main` | `e4f15e40d07a8664738a6cf4ef6fd988bad8f938` |
| Railway `/health` | public GET | `status=ok`, `commit=e4f15e40d07a8664738a6cf4ef6fd988bad8f938`, `commit_short=e4f15e40d07a` |
| `/ready` | public GET | ok, routers complete |
| `/health/live` | public GET | ok |
| Railway service | `railway status` | Online · deployment `7eb01476-…` · URL quantforg-production |
| Deployed commit match | health.commit == main SHA | **Verified** |

### Actual production flags (Railway variables — filtered)

| Flag | Present | Value | Effective behavior |
| --- | --- | --- | --- |
| `EXECUTION_ENABLED` | yes | `true` | LIVE execution authorized |
| `QUANTFORG_M1_MICRO_SCALPING` | yes | `true` | M1 **evaluation** on |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | yes | `false` | M1 **OMS submit OFF** |
| `QUANTFORG_LIVE_REVERSAL_EXITS` | **no** | unset | Code default after PR #180 → LIVE close-on-confirmed-reversal **enabled** |
| `ALLOW_RISK_LOCK_OVERRIDE` | yes | `false` | Override disabled |

Owner risk percentage / lot / quality env keys were **not listed** in the Railway variable table under the scanned names; runtime policy / code defaults remain the enforcement path (20% / 48% / 0.01 / Q70 / RR floors per owner limits module — **not modified** this audit).

### Broker identity & book (gateway)

| Field | Value |
| --- | --- |
| Account (masked) | `***9147` → login **12479147** |
| Server | Weltrade-Real |
| Equity / balance | 21.46 / 21.46 (at probe) |
| Trade allowed | true |
| Open positions | **0** |

---

## 2. LIVE reversal event evidence

### Broker-confirmed closes since PR #180 cutoff (`2026-11-06T09:51:00Z`)

**n = 8** reconstructed XAUUSD positions on account 12479147 (gateway `/history/deals`).

| Finding | Evidence |
| --- | --- |
| Confirmed LIVE reversal closes | **0** |
| Broker SL closes | **8 / 8** (exit comments `[sl …]`) |
| `looks_reversal_close` / structure / emergency tags | **none** in deal comments |
| Magic | `260720` (ITE) |
| Entry comments | `ite:v1:S:…` or `ite:v1:H:…` — **not** `m1_micro` |

Railway log samples (`railway logs --tail` 300–1500, filtered for `pme_shadow_reversal`, `live_fed`, `shadow_classification`, `sell_cascade`, `EMERGENCY_EXIT`) returned **no matching lines** in the sampled window. That is **not** proof the code path is absent; it is only proof that those log tokens were not present in the sampled tail.

### Interpretation

LIVE close-on-confirmed-reversal is **configured on** (unset kill-switch → default true), but **no broker-confirmed close in the post-deploy sample is attributable to a reversal exit**. Every sampled close is a broker stop-loss fill.

Therefore: reversal **activation ≠ demonstrated protective effect** on this sample. Effectiveness remains **insufficient evidence / not observed**.

---

## 3. Broker-confirmed close outcomes (post-PR #180)

Source: `docs/production/reports/pr181/post180_enriched_closes.json`

| Metric | Value |
| --- | --- |
| Sample size | **8** (label: **small / insufficient for expectancy claims**) |
| Wins / losses | 0 / 8 |
| Net P&L (profit+commission+swap) | **−25.22** |
| Win rate | 0% |
| Profit factor | 0.0 |
| Avg loss | −3.15 |
| Max single loss | −5.38 |
| Direction | **8 SELL / 0 BUY** |
| Avg hold | ~347 s |
| All SL closes | true |
| Actual loss vs approx planned risk (from SL comment geometry × 0.01 × 100) | ratios ≈ **0.999–1.12** |

### Per-position (authoritative)

| Position | Side | Net | Hold (s) | Approx planned risk | Loss/planned | Close |
| --- | --- | --- | --- | --- | --- | --- |
| 687174307 | SELL | −2.68 | 64 | 2.65 | 1.01 | SL |
| 687177072 | SELL | −4.28 | 90 | 4.23 | 1.01 | SL |
| 687180731 | SELL | −2.28 | 12 | 2.23 | 1.02 | SL |
| 687184354 | SELL | −3.62 | 1076 | 3.25 | 1.12 | SL |
| 687225893 | SELL | −5.38 | 1230 | 5.38 | 1.00 | SL |
| 687259338 | SELL | −1.76 | 61 | 1.59 | 1.11 | SL |
| 687268349 | SELL | −2.90 | 90 | 2.70 | 1.08 | SL |
| 687270993 | SELL | −2.32 | 149 | 2.32 | 1.00 | SL |

**Slippage / cost note:** Gateway commission and swap fields summed to 0.0 on these deals; net ≈ gross profit field. Loss/planned ≈ 1.0 implies SL geometry roughly matched realized loss (not a sizing blow-up). Slight ratio >1 may include spread/slippage not separated in deal fields.

**Counterfactual after-close path:** Not computed — subsequent candle series were not fetched for a defined measurement window. No invented “would have recovered” P&L.

---

## 4. Capital protection findings

| Control | Observed status |
| --- | --- |
| Mandatory broker SL | **Working** — all 8 exits tagged `[sl …]`; losses ≈ planned SL risk |
| Broker-confirmed close | Positions fully closed; open book = 0 at probe |
| Max concurrent 1 | Consistent with sequential tickets (no overlapping open set in reconstructed closes) |
| Net BE / trailing | Not evidenced as exit reason on this sample (SL hit first) |
| Daily loss halt 48% | Not evaluated as tripped; equity still trading then later NO_TRADE / min-lot pressure |
| Aggregate open risk 30% | No multi-position book observed |
| Duplicate-order | No duplicate tickets observed in sample |
| BUY cascade | No BUY losses in post-PR180 sample — **not exercised** |
| SELL cascade | **Did not prevent 8 consecutive SELL losses** — see §5 |
| Reversal close | **Not observed** on broker closes |
| Gateway / worker | Railway Online; cycles logging; gateway history latency called out in timings |

### Loss cause classification (sample)

Primary cause for these 8: **strategy / directional SELL entries into adverse move, stopped out by broker SL**.  
Not evidenced: incorrect lot (>0.01), missing SL, martingale, grid, averaging, or reverse-entry.

Rapid same-direction **SELL re-entry after losing SL** is the main process failure relative to PR #180’s SELL-cascade intent.

---

## 5. BUY and SELL cascade findings

### BUY cascade

Not tested by post-PR180 broker outcomes (0 BUY closes). Prior durable Postgres BUY cascade remains in code; no contradiction observed this audit.

### SELL cascade (PR #180)

**Broker evidence:** after the first losing SELL, seven further SELL losses still occurred.

**Likely defect (code-path audit, not a live debugger attach):**

1. SELL anchors are armed in `record_losing_sell_close` via `record_broker_confirmed_close` → `_arm_durable_buy_cascade`.
2. PME/SL close handling in ITE often records strategy stats / ledger marks **without** always calling `record_broker_confirmed_close`.
3. SELL store is **file-backed** and has **no** broker-history startup reconcile equivalent to BUY’s Postgres recovery.

**Conclusion:** SELL cascade is **implemented but not proven LIVE-effective**. Treating it as production protection today would be incorrect.

**Correction status:** Documented only. Wiring SL closes → `record_losing_sell_close` / broker reconcile would **change LIVE entry eligibility** → requires **explicit owner approval** before activation (Phase 9 rule).

---

## 6. M1 strategy performance

### Production configuration

- Evaluation: **ON** (`QUANTFORG_M1_MICRO_SCALPING=true`)
- OMS submit: **OFF** (`QUANTFORG_M1_MICRO_LIVE_SUBMIT=false`)

### Broker fills

Post-PR180 closes: **0** deals attributable to `m1_micro` comments. All closes are `ite:v1:…`.

### Evaluation records

Fresh authenticated robot-health / orchestration payloads were **not** available this session (no owner API token). Stale Nov-3 ops JSON must **not** be used as current M1 submit status (it previously showed submit true; Railway now shows **false**).

### Profitability readiness for future LIVE submit

| Criterion | Status |
| --- | --- |
| Deterministic entry/exit in code | Present |
| Stop calculation | Present |
| Cost-aware RR checks | Present in module |
| LIVE OMS submit | **OFF** |
| Cost-adjusted expectancy from LIVE fills | **No M1 fills** → **insufficient evidence** |
| Recommendation | **Keep submit OFF** |

---

## 7. Unified strategy coordination findings

From Railway log sample (not a full cycle dump):

- Primary decisions include high-confidence **SELL** with `action=NO_TRADE` and blockers such as `MIN_LOT_CONSTRAINT` / lifecycle FAIL after AI SELL intent — quality can pass while execution is blocked.
- Scanner quality explanations show MTF down alignment with M15 `PULLBACK_WITHIN_TREND` semantics (not treated as confirmed reversal).
- Shadow AI disagreement recorded (risk/RR deltas) while primary engine remains authoritative.
- No log evidence in the sample of BUY vs SELL fight producing dual OMS submits.
- No evidence of Opportunity/Quality inflation above published components.

**Limitation:** Without fresh orchestration monitor JSON, conflict counts / M1 arbitration tallies cannot be quantified for the post-deploy window.

---

## 8. Reverse-entry readiness

Reverse entry remains **forced OFF** in code paths (`live_reverse_entry_enabled=False`).

| Gate | Readiness |
| --- | --- |
| Broker-confirmed close before opposite | Evaluator encodes; **not LIVE-exercised** |
| Reconcile internal vs broker | Existing PME/truth paths; not stress-tested on reverse sequence LIVE |
| Independent opposite eligibility (Q/Risk/OMS/SL) | Designed; **no LIVE reverse sample** |
| Cascade interaction | SELL cascade currently ineffective → **not ready** |
| Flip/cooldown | Dedup exists for close; reverse-entry still off |

**Assessment:** **Not ready for owner activation.** Fix SELL cascade arming + accumulate confirmed-reversal close evidence first.

---

## 9. Profitability statistics & sample limitations

### A. Current account 12479147 — post-PR #180 only

| Metric | Value | Label |
| --- | --- | --- |
| n | 8 | **Insufficient for strategy expectancy** |
| Net | −25.22 | Broker-confirmed |
| PF | 0.0 | |
| Win rate | 0% | |
| Expectancy | −3.15 / trade | |
| Direction | 100% SELL | |

### B. Historical account 12260878 — prior loss-audit snapshot (7d metrics in saved file)

From `loss_audit_broker_history.json` → `deals_7.metrics` (account login ends **0878**):

| Metric | Value |
| --- | --- |
| n_positions | 46 |
| Wins / losses | 20 / 26 |
| Win rate | ~43.5% |
| Net | −29.94 |
| Profit factor | ~0.50 |
| Avg win / avg loss | ~1.53 / −2.33 |
| Expectancy | ~−0.65 |

**Do not merge A and B.** Different accounts and periods.

### C. Pre-PR #180 on 12479147

Not separately reconstructed in this probe beyond noting PR180 cutoff filter. Deals_7 reconstruction on current account is dominated by the post-cutoff cluster for the “post” metrics above.

### D. Reversal close effectiveness

**No qualifying reversal closes** → cannot compute success/false-reversal rates from broker evidence.

### E. M1 cost-adjusted results

**No M1 LIVE fills** → N/A.

---

## 10. Corrections made

| Item | Action |
| --- | --- |
| Owner risk / lot / Q / RR | **Unchanged** |
| M1 LIVE submit | **Left OFF** |
| Reverse entry | **Left OFF** |
| LIVE trading | **Left enabled** |
| Code behavior changes | **None** this PR |
| Diagnostics added | Probe scripts + evidence JSON under `docs/production/reports/pr181/` |

**Proven defect logged for owner approval (not activated):** SELL cascade does not appear to arm/block on broker SL losing SELLs; needs attribution/reconcile wiring before claiming LIVE protection.

---

## 11. Tests

Local (this audit session):

```
pytest tests/unit/test_pr180_live_protection.py \
       tests/unit/test_reversal_intelligence.py \
       tests/unit/test_m1_micro_scalping.py \
       tests/unit/test_unified_decision.py \
       tests/unit/test_pme_broker_confirm_net_be.py \
       -q --override-ini=addopts=
```

(Exact counts recorded at commit time; trading-core / CI green expected on docs-only PR.)

No production behavior change → no new LIVE regression surface beyond documentation/probes.

---

## 12. Actual production configuration (summary)

- Commit: `e4f15e40` (verified via `/health`)
- LIVE execution: **ON**
- LIVE reversal close (confirmed structure only): **ON by default** (kill-switch unset)
- Reverse entry: **OFF**
- M1 evaluation: **ON**
- M1 OMS submit: **OFF**
- Account: 12479147 Weltrade-Real; flat book at probe

---

## 13. LIVE vs OFF

| Feature | LIVE? |
| --- | --- |
| Authorized ITE/OMS trading | **Yes** |
| Broker SL protection | **Yes** (evidenced) |
| Close-on-confirmed-reversal (config) | **Yes (default)** |
| Close-on-confirmed-reversal (broker-proven effect) | **Not observed** |
| Reverse entry | **No** |
| M1 evaluation | **Yes** |
| M1 OMS submit | **No** |
| BUY cascade | **Yes (code); not exercised in sample** |
| SELL cascade | **Code present; LIVE effectiveness not proven** |

---

## 14. Recommended next step

1. **Owner approval request:** wire broker-confirmed SL / history attribution to `record_losing_sell_close` (+ optional durable reconcile) so SELL cascade can block unresolved same-direction SELL re-entry.  
2. Keep **M1 LIVE submit OFF** until cost-adjusted fill evidence exists.  
3. Keep **reverse-entry OFF** until (1) works and confirmed-reversal closes are observed with broker timestamps.  
4. Add durable export of `pme_shadow_exits` / CTR stages from Railway data dir for the next audit window.  
5. Do **not** raise risk or lower Q70 to “recover” the −25.22 cluster.

---

## Evidence index

- `docs/production/reports/pr181/gateway_broker_evidence.json`
- `docs/production/reports/pr181/post180_enriched_closes.json`
- `docs/production/reports/pr181/railway_flags_observed.json`
- `docs/production/reports/pr181/_probe_gateway_only.py`
- `docs/production/reports/pr181/_enrich_deals.py`
- Historical (account 12260878): `docs/production/reports/profitability/loss_audit_broker_history.json`

**Bottom line:** QuantForg remains LIVE on `e4f15e40`. Post-deploy broker sample shows **eight consecutive SELL stop-outs (−25.22)** with **working SL geometry**, **no reversal closes**, **no M1 fills**, and **SELL cascade not demonstrated**. Capital preservation requires fixing same-direction SELL re-entry protection before seeking profitability improvements.
