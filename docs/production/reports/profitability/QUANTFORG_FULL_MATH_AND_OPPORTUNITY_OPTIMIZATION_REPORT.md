# QuantForg — Full Mathematical Correction & Opportunity Optimization

**Generated:** 2026-11-05T19:10:00Z  
**Follows:** Loss root-cause #166 / docs #167 (commit `c4426f47` / `3d56fba2`)  
**Owner policy:** **unchanged** (max_lot 0.01, risk 20%, Q≥70, RR floor 0.20 / preferred 0.50, concurrent 1, daily halt 48%, mandatory SL, no grid/martingale/averaging)

**Verdict:** Core XAUUSD monetary formulas (CS×vol×distance, 48% SOD daily halt, deal PnL) are **correct**. This release fixes verified **false rejects** (presend spread double-count), **misaligned daily-loss % display**, **Probability Center RR mapping** that crushed opportunity scores on valid owner geometry, and **SOE solo bars** that idled Q76–81 setups already above owner Q70. No profitability claim. No owner-floor changes.

---

## 1. Broker status (prior baseline; re-confirm after deploy)

| Item | Last authoritative sample |
| --- | --- |
| Equity / balance | **$18.30** / **$18.30** (Weltrade login 12260878) |
| Open positions | **0** |
| Trading net (n=46) | **−$29.94**, PF 0.50 |

---

## 2. Mathematical audit — verified correct

| Formula | Location | Status |
| --- | --- | --- |
| Planned $ risk `(dist+spread+slip)×CS×vol+fee` | `owner_live_limits.planned_risk_usd` | Correct |
| Net RR with `spread_already_in_stop` | `net_reward_risk` | Correct |
| 20% equity risk ceiling | `owner_max_risk_usd` | Correct |
| Max lot 0.01 | `owner_authorized_max_lot` | Correct |
| Daily halt: loss **>** 48% of **SOD** equity | `daily_loss_exceeded` + deal tracker | Correct (realized only; deposits excluded) |
| Deal net = profit+commission+swap | close attribution / live tracker | Correct |
| Weltrade live tick 0.001/0.1 vs canonical POINT 0.01 | Specs vs gateway | **Identity holds** via tick_value path; do not “fix” structure slippage to 0.10 without broker-point confirmation |

### Defects corrected this release

| # | Old behavior | Corrected |
| --- | --- | --- |
| 1 | `presend_owner_violations` called `evaluate_owner_entry` **without** `stop_includes_spread_buffer=True` while LIVE structure SL already embeds spread → **double-count** → false `OWNER_MIN_RR` at send | Pass `stop_includes_spread_buffer=True` from execution engine; param on `presend_owner_violations` |
| 2 | Presend slippage-buffer RR used spread-only helper | Uses `net_reward_risk` with same buffer flag |
| 3 | Daily `daily_loss_pct` = `(-pnl)/current_balance` while halt uses SOD | Display/compare % uses **SOD** (`base - pnl`) like weekly/monthly |
| 4 | `_rr_quality` mapped RR 1.0–2.5 → 40–100; owner RR 0.40 → **~16** | Map owner **[0.20, 0.50] → [40, 100]** |
| 5 | SOE solo Q≥82 / C≥80 and preferred-RR solo Q≥85 blocked Q76–81 | Solo bar **76/76**; preferred-RR solo Q **80** (absolute floor still **70**) |

### Not changed (proposed only if owner wants later)

- Daily halt **threshold** 48% (formula OK; do not silently tighten/loosen).
- Canonical `xauusd_specs.POINT=0.01` vs live tick 0.001 — document only; monetary identity OK.
- Unify price-R vs USD-R in PME telemetry (reporting consistency; follow-up).

---

## 3. Why opportunities were missed (and what we fixed)

| Cause | Protective? | Action |
| --- | --- | --- |
| Owner Q&lt;70 | Yes | Unchanged |
| MIN_LOT / concurrent=1 | Yes | Unchanged |
| Presend spread double-count | **No — bug** | Fixed |
| Probability `rr_quality` on sub-1 RR | **Unjustified** | Fixed mapping |
| SOE solo 82/80 above owner 70 | **Over-selective** | Aligned to 76 |
| Preferred-RR solo Q85 | **Over-selective** | 80 |
| Attribution / STALE_RISK / high_quality | Prior #166 | Already shipped |

---

## 4. Strategy / historical performance

- Broker n=46 baseline unchanged this pass (no claim of improved LIVE PF yet).
- Five-pack historical SOE books still incomplete for older tickets; #166 attribution repair applies going forward.
- Preferred structure TP 0.50 (#166) + SOE solo alignment are **limited-evidence** expectancy/opportunity improvements pending LIVE sample.

---

## 5. Tests

```
37 passed — owner_presend_check, phase6_strategy_intelligence,
            owner_rr_quality_mapping, strategy_orchestration_engine
```

---

## 6. Policy confirmation

Owner YAML floors **not** modified. Absolute SOE floor remains **Q70**. Solo selectivity still **above** owner minimum (76).

---

## 7. Deploy evidence

Filled after merge: Git commit, CI, Railway SUCCESS, `/health` `/ready`, production commit SHA.
