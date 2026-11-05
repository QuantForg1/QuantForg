# QuantForg — LIVE Robot Trade Management Audit, Repair & Risk Recommendations

**Classification:** Production audit + verified technical repairs only  
**Date:** 2026-11-05  
**Branch (repairs):** `audit/live-pme-be-recovery-offset`  
**SOE:** `soe-v1.5.0` (PR #154 / Railway `1b0ad18a`)  
**Owner policy:** **UNCHANGED** (max_lot 0.01, risk 20%, RR 0.20/0.50, Q70, concurrent 1, daily halt 48%, aggregate 30%, mandatory SL, no grid/martingale/averaging, M1 LIVE off)  
**Instrument:** XAUUSD · Weltrade-Real · magic `260720`

**Disclaimer:** Broker samples are small. Estimates are labeled. No real-money test orders were placed. No live positions were modified for testing. No owner settings were changed. No new exit logic was deployed to LIVE.

---

## 1. Executive summary

QuantForg’s Position Management Engine (PME) **does** protect open positions via mandatory SL, class-aware Break-Even (BE), ATR trailing after lifecycle advance, time/spread/kill/daily flatten paths, restart recovery from MT5, and OMS-mediated SL/TP modification. Several intelligent exit paths (structure break, trend reverse, AI confidence fade) **exist in `plan_action` but are not wired** from the LIVE ITE sync context — they cannot fire in production as written.

**Verified defect repaired in this audit (not yet production-deployed at report time):**

| Defect | Severity | Repair |
|---|---|---|
| Recovery reconstructed 1R using hardcoded `0.2R` BE offset for all classes | P1 | Class-aware offset via `resolve_class_management` (SCALP 0.35 / HOLD 0.30 / UNKNOWN 0.2) |
| `trade_class_from_comment` required fixed colon index `[2]` | P2 | Scan colon parts for `S`/`H`/`U` markers |

**Not repaired (recommendation / needs owner approval):**

- Wire structure / trend / AI exit context into ITE `PositionManageContext` (new LIVE behavior).
- Post-OMS broker SL re-read before marking BE/trail success (hardening).
- Net break-even (spread + commission + swap).
- Owner / SOE numeric soft-layer changes.

**Broker performance (available history):** Nov 2–3 n=29 closes, PF **0.68**, expectancy **−$0.33**/trade, equity ≈ **$22.63**. Post–#154 attributed fills: **0**. Hard-attributed strategy P&L: **2** `trend_continuation` closes (−$3.55). Sample is insufficient to justify raising risk or lot.

---

## 2. Production baseline

| Item | Evidence |
|---|---|
| Mode | LIVE · auto-trading armed (prior ops fetch) |
| Kill switch | Off at last verified fetch |
| Owner floors | Enforced in Risk / policy (RR 0.20, Q70, max_lot 0.01) |
| P0 volume clamp | Deployed PR #155 / Railway `a956c2d3` — planned volume clamped to owner max_lot |
| Equity | **$22.63** broker (audit_analysis.json / scalping report 2026-11-05) |
| Open positions at audit | Not modified; recovery/PME inspected via code + unit tests only |
| Frozen modules | PME / ITE / Risk / OMS / gateway remain under Trading Core Freeze; repairs limited to verified recovery/comment defects |

Owner-authorized configuration (locked — **not changed**):

```yaml
max_lot: 0.01
risk_per_trade_percent: 20
absolute_risk_ceiling_percent: 20
minimum_net_reward_risk: 0.20
preferred_reward_risk: 0.50
minimum_trade_quality: 70
max_concurrent_positions: 1
daily_loss_halt_percent: 48
max_aggregate_open_risk_percent: 30
mandatory_stop_loss: true
grid_trading: false
martingale: false
averaging_down: false
M1_LIVE_submissions: false
```

---

## 3. Break-Even audit

### Lifecycle (code path)

1. ITE `_sync_and_manage_open_positions` → recover → build `PositionManageContext` → `PositionManagementEngine.evaluate` → `plan_action` → OMS `modify_sltp`.
2. Class overlay: `resolve_class_management` — SCALP BE at **0.80R** offset **0.35R**; HOLD **1.0R / 0.30R**; UNKNOWN **1.0R / 0.2R** (`class_policy.py`).
3. Candidate SL: `break_even_stop` = entry ± `risk_distance * break_even_offset_r` (`r_math.py`).
4. Improvement gate: `is_stop_improvement` — BUY only if new SL **>** current; SELL only if new SL **<** current.
5. OMS success → local `be_moved` / state `BE_MOVED`; failure → no fingerprint (retry next cycle).
6. Restart: `recover_positions_from_mt5` detects broker SL on profit side of entry → reconstructs 1R and sets `be_moved`.

### Checklist

| # | Question | Verdict | Evidence |
|---|---|---|---|
| 1 | Detects BE qualification | **WORKING** | `plan_action` `r >= be_at` + class profile; SCALP can defer BE while momentum ≥ fade floor until 1.0R |
| 2 | Activation threshold correct | **WORKING** | Class constants; optional protection floor when adverse |
| 3 | SL to entry / net BE | **PARTIALLY WORKING** | Moves to **entry ± offset_R**, not raw entry; **not** net of spread/commission/swap |
| 4 | Spread / commission / swap in BE | **MISSING** | `break_even_stop` uses price geometry only |
| 5 | SL submitted to MT5 | **WORKING** | `engine._dispatch` → `oms.modify_sltp` for `BREAK_EVEN` |
| 6 | MT5 confirms modification | **PARTIALLY WORKING** | Relies on OMS `ok` / retcode; **no immediate broker position re-read** before local BE lock |
| 7 | Broker SL ↔ internal sync | **PARTIALLY WORKING** | Next cycle reads `book_stop`; recovery prefers broker SL; success path updates local without re-fetch |
| 8 | Duplicate / stale / repeat | **WORKING** | Fingerprint skip; `be_moved`; “already protected” advances without modify |
| 9 | Rejects / timeouts / partial fail | **WORKING** | Failed manage not fingerprinted; metrics `record_be(False)`; gateway/MT5 outcome mapping |
| 10 | After worker restart / reconnect | **PARTIALLY WORKING** → **repaired P1** | Recovery existed but used hardcoded 0.2R; now class-aware (this PR) |

### P0 residual (recommendation only)

Treat OMS `ok` as provisional until a broker `positions_get` (or equivalent) confirms SL ≥ planned BE for BUY / ≤ for SELL. Do **not** ship without isolated tests and owner approval (changes LIVE modify semantics).

---

## 4. Stop-Loss & trailing-stop audit

| Mechanism | Status | Notes |
|---|---|---|
| Initial mandatory SL | **WORKING** | Risk / OMS entry path; naked broker stop → `RESTORE_STOP` / `EMERGENCY_EXIT` |
| SL improve after favorable move | **WORKING** | BE then trail; `is_stop_improvement` blocks risk-widening |
| Trailing activation | **WORKING** (lifecycle) | After BE → partial advance → trail when `r >= trail_after_r` (default 2.0R) |
| Trail distance / ATR | **WORKING** | `trail_distance` ATR mults; structure/liquidity tiers **config-gated** (structure/liquidity trail default **False**) |
| Broker min stop / freeze | **PARTIALLY WORKING** | Enforced in OMS/gateway path when broker rejects; PME does not pre-compute freeze-level locally in all cases |
| XAUUSD digits / normalize | **WORKING** | Quantize `0.01` on BE/trail helpers |
| BUY vs SELL | **WORKING** | Explicit side branches in `break_even_stop`, `trail_stop_price`, `is_stop_improvement`, recovery |
| Never move SL backwards | **WORKING** | `is_stop_improvement` + trail “would not improve” NOOP |
| MT5 retcodes / retries | **WORKING** | Failure path retries next cycle; metrics |
| Broker ↔ DB reconciliation | **PARTIALLY WORKING** | Book sync each manage cycle; attribution gaps remain on closed trades |

**BUY never lowers SL to increase risk / SELL never raises SL to increase risk:** enforced in planner math. Confirmed by unit regression suite (`test_trading_core_regression.py`).

---

## 5. Reversal & early-exit audit

### Implemented in `plan_action` (policies.py)

- `structure_broken` → `EMERGENCY_EXIT`
- `trend_reversed` → `EMERGENCY_EXIT`
- AI path via `plan_ai_position_action` when `ai_entry_confidence` + `ai_current_confidence` set
- Time stop / absolute max hold (class-aware)
- Spread spike / market closed / connection unstable / risk_requests_exit / news / daily / kill

### LIVE wiring gap (critical)

ITE `_sync_and_manage_open_positions` builds `PositionManageContext` with price, ATR, spread, book stop, kill/daily flags — **but does not set** `structure_broken`, `trend_reversed`, AI confidence/momentum fields, `structure_stop`, or `news_requests_exit` / `risk_requests_exit` in the production sync path inspected at:

`app/application/services/institutional_ite_runtime.py` (~1514–1538).

| Capability | Verdict |
|---|---|
| Detect credible reversal vs open position | **BROKEN (unwired)** — planner ready, context never fed |
| Distinguish reversal vs retracement | **MISSING in LIVE path** — M15 CHOCH/BOS exists for **entry** scoring (`m15_semantics_v2`, AI scalping), not PME exits |
| Tighten SL on reversal | **MISSING in LIVE** (would need wired context + policy) |
| Close on validated exit | **PARTIALLY WORKING** — time/spread/kill/daily/broker-missing work; structure/trend/AI do not |
| Avoid noise exits | N/A for unwired paths; time-stop has scratch/R floors |
| Confirm broker close before local EXIT | **PARTIALLY WORKING** — empty book ≠ force exit; missing ticket → local exit; deal attribution still incomplete |
| Record deal / PnL / fees / strategy | **PARTIALLY WORKING** — broker history available; hard strategy attribution sparse (n=2) |
| Reconcile after API fail / restart | **WORKING** with recovery repair above |

**Policy:** Do **not** deploy new reversal exit wiring to LIVE without owner approval + deterministic tests. Documented as P0 product gap / recommendation only.

---

## 6. Other position-management features

| Feature | Classification | Evidence |
|---|---|---|
| Take-Profit sync | **WORKING** | Broker TP preserved on BE/trail modifies; broker TP closes |
| Partial take-profit | **PARTIALLY WORKING** | Planner supports; min-lot 0.01 often advances lifecycle with volume 0 (no real partial) |
| BE after partial | **PARTIALLY WORKING** | Lifecycle order BE → partial → trail; at 0.01 lot partial is virtual advance |
| Trailing stop | **WORKING** | ATR trail after lifecycle; improvement-only |
| Max holding time | **WORKING** | Class absolute max + time_stop_minutes |
| Session-end risk | **MISSING / NOT APPLICABLE** | No dedicated session-flatten in PME sync (market_open forced True in ITE context) |
| Spread expansion protection | **WORKING** | `emergency_spread_max` → emergency exit when context.spread set |
| High-volatility protection | **PARTIALLY WORKING** | Entry volatility gates; open-position vol exit not separately wired |
| News/event risk | **PARTIALLY WORKING** | Planner has `news_requests_exit`; not confirmed fed from ITE sync |
| Broker-side SL/TP | **WORKING** | Mandatory SL; restore if naked |
| Position recovery after restart | **WORKING** (P1 repaired) | Snapshot + MT5 book; class-aware BE reconstruct |
| Duplicate position prevention | **WORKING** | Owner max concurrent 1 + portfolio/Risk |
| Broker reconciliation | **PARTIALLY WORKING** | Live book sync; history window gaps |
| Closed-trade attribution | **PARTIALLY WORKING** | Comment markers + SOE books; most broker closes unattributed |
| Realized / floating PnL | **WORKING** at broker; floating marked in Phase B MAE/MFE observe-only |
| Execution latency / failed modify monitoring | **PARTIALLY WORKING** | PME metrics + logs (`pme_sltp_modification`); alerting via telegram hook best-effort |
| Grid / martingale / averaging | **NOT APPLICABLE** | Explicitly forbidden; no add-to-loser path in PME |
| Net break-even (fees) | **MISSING** | Offset_R only |

---

## 7. Strategy-by-strategy performance

Sources: `docs/production/reports/scalping_optimization/audit_analysis.json`, `QUANTFORG_LIVE_SCALPING_OPTIMIZATION_REPORT.md` (2026-11-05). **Verified broker data vs estimates clearly separated.**

### Broker-confirmed (Window A — Nov 2–3, magic 260720)

| Metric | Value |
|---|---:|
| n | 29 |
| Win rate | 48.3% |
| Net P&L | −$9.61 |
| Profit factor | 0.68 |
| Expectancy | −$0.33 / trade |
| Avg win / avg loss | +$1.45 / −$2.00 |
| SL / TP exits | 15 / 14 |
| Avg hold | ~198s |

Session (UTC heuristic): London–NY overlap worst (n=7, PF 0.38); NY n=12 PF 0.90; Asia n=9 PF 0.76.

### Window B — Nov 4 (Phase-2 reconstruction)

n=13, net −$8.48, PF 0.59. Hard-attributed: **2** `trend_continuation` (−$3.55). **11 unattributed** — not invented.

### Window C — Post–#154

Broker fills **0**. HQ near-misses **17** (`momentum_scalping` BUY, Risk FAIL). Rejected signals hundreds; Risk blocked 18.

### Five strategies (SOE process book — not broker P&L)

| Strategy | Eligible (book) | Accepted | Attributed closed | Attributed net |
|---|---:|---:|---:|---:|
| smc_scalping | 18 | 0 | 0 | $0 |
| trend_continuation | 18 | 0 | **2** | **−$3.55** |
| breakout_scalping | 18 | 0 | 0 | $0 |
| range_mean_reversion | **0** | 0 | 0 | $0 (regime require — by design) |
| momentum_scalping | 18 | **18** | 0 fills | $0 |

**Dominance:** Post–Phase-3 accepts skewed to momentum; **zero fills** means momentum expectancy is **unknown**. Do not loosen owner Risk to chase those 17 near-misses without geometry diagnosis.

---

## 8. Current owner policy assessment

Owner floors are **appropriate for survival** on a ~$23 micro account. Historical PF &lt; 1 argues **against** raising lot, risk %, or concurrent positions. Trade scarcity is dominated by (1) no clear direction, (2) ATR/dead-tape gates, (3) OWNER Risk geometry on HQ momentum — **not** by PME BE/trail failure.

---

## 9. Recommended alternative parameter values (**recommendations only**)

| Parameter | Current | Robot-specific evidence | Recommended value/range | Reason | Confidence |
|---|---:|---|---|---|---|
| max_lot | 0.01 | Broker min; P0 clamp deployed; equity $22.63 | **Keep 0.01** | Raising lot raises $ risk per SL hit; PF&lt;1 | **High** |
| risk_per_trade_percent | 20 | 0.01 lot + wide gold SL often hits OWNER_SL_RISK before fill | **Keep 20** (do not raise). Optional future **15–18** only after positive expectancy sample | Ceiling already aggressive for micro equity | Medium (keep); Low (lower) |
| absolute_risk_ceiling_percent | 20 | Same as planned risk bind | **Keep 20** | Aligns with owner absolute ceiling | High |
| minimum_net_reward_risk | 0.20 | LIVE floor; enables more geometry than 0.50-only | **Keep 0.20** | Raising to 0.50 would cut fills further; lowering &lt;0.20 worsens expectancy risk | High |
| preferred_reward_risk | 0.50 | Solo quality uplift when RR in [0.20,0.50) | **Keep 0.50** soft preference | No evidence to change | Medium |
| minimum_trade_quality | 70 | Owner floor; ITE uses 76 above it | **Keep 70** owner; soft ITE 72–76 candidates only | Softening owner Q is unsafe given PF&lt;1 | High |
| max_concurrent_positions | 1 | Portfolio blocked rare; aggregate risk 30% | **Keep 1** | Micro account cannot support stacking | High |
| daily_loss_halt_percent | 48 | Large relative halt for micro equity | **Keep 48** until larger sample; hypothesis **25–35** if owner wants tighter survival | Reducing halt **reduces** blow-up path; not tested OOS | Low–Medium |
| max_aggregate_open_risk_percent | 30 | With concurrent=1 rarely binds | **Keep 30** | Harmless with max 1 | High |
| mandatory_stop_loss | true | Naked-stop restore path exists | **Keep true** | Non-negotiable | High |

### PME-related parameters (exist in code)

| Parameter | Current | Recommendation | Risk effect | Confidence |
|---|---|---|---|---|
| SCALP BE at / offset | 0.80R / 0.35R | **Keep** (0.35R fixed after glued-SL incident) | Neutral | High |
| HOLD BE at / offset | 1.0R / 0.30R | **Keep** | Neutral | Medium |
| trail_after_r | 2.0R | **Keep**; optional research 1.5R only with approval | Lowering activates trail earlier (can tighten sooner) | Low |
| Net BE (fees) | Missing | **Implement as recommendation** — entry ± offset + estimated half-spread/commission in R | Reduces false BE scratches | Medium hypothesis |
| Reversal exits | Unwired | **Wire + shadow metrics first**, then owner-gated LIVE | Can reduce losers **or** cut winners — needs validation | Medium |

### Soft layers (not owner floors) — Scenario B from scalping audit (still **approval-only**)

atr_hard_min 0.08→0.075; SOE solo 82→80; NY 86/84→84/82; ITE quality 76→72. **Does not unlock Risk-failed HQ momentum alone.** Scenario C (more aggressive) **not recommended** for LIVE.

---

## 10. Small-capital analysis

| Item | Evidence |
|---|---|
| Balance / equity | **~$22.63** (broker, 2026-11-05 fetch) |
| Min lot | **0.01** (owner = broker practical min) |
| Typical XAU risk at 0.01 | Depends on SL distance; losses in sample avg **−$2.00**; wins **+$1.45** |
| Spread / costs | Deals carry commission/swap fields; BE math ignores them → net BE often worse than geometric BE |
| Expectancy | **−$0.33**/trade (n=29) — **negative** |
| Drawdown | Account deposits $19+$13; trading net negative on Windows A/B |
| Capital to support strategy safely | With 20% planned risk and gold stops, **sub-$50** equity is fragile: one full planned-risk hit ≈ large equity fraction; recommend **≥$100–$250** before expecting statistical stability (**hypothesis**, not a promise) |
| Why rejects at min lot | OWNER_SL_RISK / geometry: stop distance × 0.01 lot vs 20% of ~$23 often fails Risk; also OWNER_MIN_RR |
| RR / quality | Appropriate as **filters**; not the root of negative PF alone |

### Scenarios (settings **not** applied)

| Scenario | Idea | Trade-off |
|---|---|---|
| Conservative | Keep all owner floors; ops reliability; attribution | Fewer trades; best survival odds on current evidence |
| Moderate | Soft Scenario B + Risk reason instrumentation + net-BE design | Slightly more candidates; still Risk-bound; no lot increase |
| Aggressive | Raise lot / risk% / concurrent or Scenario C SOE | **Increases** ruin risk on PF&lt;1 sample — **not recommended** |

**Do not promise rapid capital growth.** Current verified expectancy is **negative or inconclusive** post-filter.

---

## 11. Missing features & prioritized defects

### P0

1. **Structure / trend / AI exit context unwired in LIVE ITE sync** — intelligent reversal management cannot run.
2. **BE/trail success without broker SL re-read** — internal state can diverge from MT5 if OMS reports ok spuriously.
3. **Closed-trade strategy attribution incomplete** — blocks evidence-based strategy ranking (mostly unattributed broker closes).

### P1

4. ~~Recovery BE offset hardcoded 0.2R~~ → **REPAIRED** on branch (pending deploy).
5. **Net break-even (spread/commission/swap)** missing.
6. **Partial TP ineffective at 0.01 lot** — lifecycle advances without real scale-out.
7. **`market_open=True` hard-coded** in ITE manage context — session-close flatten path muted.
8. Risk reject **reason codes** not always surfaced on HQ near-misses (ops diagnosis).

### P2

9. ~~`trade_class_from_comment` fixed index~~ → **REPAIRED**.
10. Structure/liquidity trail disabled by default (OK if intentional).
11. History API window gaps (Nov-4 missing from later `/history` fetch).

### P3

12. Telegram PME notify best-effort.
13. Dead / unused advisory paths in research simulation vs LIVE.

---

## 12. Repairs implemented & tests

### Code changes (this audit)

| File | Change |
|---|---|
| `app/domain/institutional_trading/production_hardening/position_recovery.py` | Class-aware `be_offset` from `resolve_class_management` |
| `app/domain/institutional_trading/management/class_policy.py` | Marker scan for trade class in comments |
| `tests/unit/test_trading_core_regression.py` | SCALP recovery regression + UNKNOWN comment on existing test |

### Tests executed (local)

```
pytest tests/unit/test_trading_core_regression.py
→ 8 passed

pytest …::test_position_recovery_broker_be_reconstruct
      …::test_position_recovery_scalp_be_uses_class_offset_not_hardcoded_02
→ 2 passed

pytest tests/unit/test_position_lifecycle_and_multipos.py -k "trade_class_from_comment or HOLD"
→ 3 passed, 19 deselected

ruff check (repaired modules) → All checks passed
```

No real-money orders. No live position interference. Owner YAML unchanged.

---

## 13. Deployment evidence

| Step | Status |
|---|---|
| Branch | `audit/live-pme-be-recovery-offset` |
| Production deploy of this repair | **NOT completed at report time** |
| Prior related prod | P0 volume #155 deployed; docs #156 |
| Blocker for deploy | PR + CI (`pytest -m trading_core`, lint) + merge + Railway health verification required |

After merge: verify Railway ready, worker/scheduler, gateway sync, Risk/OMS active, **no unintended modifies**, owner policy bytes unchanged.

---

## 14. Remaining risks & limitations

- Negative historical expectancy on available broker sample.
- n=2 attributed strategy trades — insufficient for strategy-level optimization claims.
- Unwired reversal exits leave winners/losers to SL/TP/time/spread only.
- Micro equity amplifies variance; 20% risk-per-trade is large in absolute survival terms.
- Trading Core Freeze: further PME/ITE behavior changes need explicit owner approval beyond this recovery fix.

---

## FINAL OWNER SCORECARD (A–F)

### A. Confirmed working

- Mandatory SL + naked-stop restore / emergency flatten paths that **are** fed (spread, kill, daily, book-missing ticket).
- Class-aware BE planning (0.80R/0.35R SCALP etc.) and improvement-only SL/trail math (BUY/SELL).
- OMS-mediated modify/close dispatch; failed modifies retry.
- ATR trailing after lifecycle advance; time stops; concurrent=1; no grid/martingale.
- Restart recovery from MT5 + snapshots (with class-aware offset repair pending deploy).
- Owner Risk floors and P0 max_lot clamp in production.

### B. Broken and repaired (this PR — pending production deploy)

- Recovery 1R reconstruction used hardcoded 0.2R → now class-aware.
- Comment trade-class marker parsing brittle → scan-based.

### C. Missing / still broken

- LIVE wiring for structure_broken / trend_reversed / AI manage context.
- Net fee-aware break-even.
- Broker SL re-confirm after successful modify.
- Effective partial TP at 0.01 lot.
- Robust closed-trade strategy attribution.
- Dedicated session-end flatten (market_open forced true).

### D. Numerical recommendations (not applied)

- **Keep all owner table values** as currently authorized.
- Soft Scenario B (ATR/SOE/ITE only) optional under separate approval — will not alone unlock Risk-failed HQ trades.
- Do **not** raise max_lot, risk %, or concurrent on current evidence.
- Optional tighter daily halt 25–35% = hypothesis only.

### E. Requires separate owner approval

- Deploy/merge of this recovery PR (if not auto-approved).
- Wiring reversal/AI exits into LIVE ITE context.
- Post-modify broker SL verification behavior change.
- Net-BE formula.
- Any owner YAML or SOE/ITE soft-threshold change (Scenario B/C).
- Any increase in lot / risk / concurrent.

### F. Production deployment of this audit’s repairs

**No — not completed / not independently verified on Railway at report authorship.** Local unit tests green; PR path required before LIVE.

---

*End of report.*
