# QuantForg — Capital Preservation First, Sustainable Profitability Mission

**Baseline:** PR #177 / `68216c2d`  
**Report time:** 2026-11-06T08:40:00Z (approx.)  
**Instrument:** XAUUSD  
**Accounts:** historical sample login **12260878**; live login **12479147** (do not mix P/L across accounts)  
**Broker sample:** `docs/production/reports/profitability/loss_audit_broker_history.json` (46 closed positions, magic 260720)  
**Owner policy:** **not changed** by this mission

## Final principle

Capital preservation first. Proven edge second. Sustainable compounding third.  
A refused bad trade is better than continuous trading that destroys the account.  
No guaranteed profits. No claim of positive expectancy from an inadequate sample.

---

## 1. Executive summary

Broker-confirmed trading on the historical Weltrade book is **negative expectancy**: **n=46**, net **−$29.94**, profit factor **0.50**, win rate **43.5%**, path drawdown **≈ −$34**. Losses cluster in minutes. Twelve consecutive BUY lower-entry loss pairs drove most of the dollar damage. SELL has no durable same-direction cascade guard. Daily halt at **48%** of start-of-day equity and **20%** per-trade risk can empty a small account in a handful of full-risk hits. Consecutive-loss pause and weekly/monthly halt are **disabled** by owner setting (`OWNER_MAX_CONSECUTIVE_LOSSES = 0`, weekly/monthly = 0).

LIVE now (login 12479147): balance **33.82**, equity **≈32.6**, one open SELL ticket **687225893** volume **0.01**, SL **4072.827**, TP **4056.883**, floating ≈ **−1.5**. Concurrent-position cap **1** is blocking new entries. Quality on recent SELL scans is **87** with clock map `H1=down M15=down M5=down M1=up`. That is selectivity working after #174/#175/#177 — it is **not** proof of profitability.

**This mission implements no owner-risk change and no experimental LIVE strategy change.** It documents evidence, protection gaps, safer policy options for approval, and what is already safe.

---

## 2. Root causes of large or clustered losses

Evidence from the 46 closed positions (login 12260878):

| Rank | Cause | Evidence |
| --- | --- | --- |
| 1 | Asymmetric SL vs TP | SL outcomes 26 / −$60.47; TP outcomes 20 / +$30.53; avg loss −$2.33 vs avg win +$1.53 |
| 2 | BUY cascade into the same decline | BUY 34 / −$28.12; **12** consecutive BUY pairs with a lower entry after a prior BUY loss |
| 3 | Rapid loss clusters | **6** clusters of ≥2 losses within 15 minutes; sizes 3,2,2,3,3,4; largest cluster 2026-11-05 19:24–19:39 UTC four BUYs net **−$11.09** |
| 4 | Worst single day | 2026-11-05 net **−$20.33** (17 trades, 11 losses) |
| 5 | Max consecutive losses | **5** (owner consecutive-loss pause disabled) |
| 6 | Capital already small | Equity ~$18 on that account after deposits and trading; 20% risk still allows multi-dollar stops on 0.01 lot |

### Rapid cluster examples (broker)

1. 2026-11-02 14:07 UTC — 3 SELLs in ~minutes, net −$4.68 (entries rising then chopping).  
2. 2026-11-03 04:58 UTC — 3 BUYs stepping lower 3950 → 3943, net −$5.62, holds 17–99s.  
3. 2026-11-05 14:25 UTC — 3 BUYs lower 4129 → 4121, net −$8.04.  
4. 2026-11-05 19:24 UTC — 4 BUYs lower 4117 → 4108, net −$11.09 (later released as other-account anchors under #173).

### Pipeline stage that failed first (historical)

Market data and structure were producing new signatures on each lower break. Same-symbol requalification treated each as a fresh setup → Risk allowed another 0.01 lot → OMS submitted → SL hit. That is correlated re-entry, not independent opportunities. Durable BUY cascade (#171–#173) was built for this. SELL still lacks an equivalent durable same-direction guard.

### What is working LIVE now

- Concurrent max **1**: new SELL opportunities with quality 87 are blocked with `Max open positions reached (1>=1)` while ticket 687225893 is open.  
- Broker SL and TP are present on the open SELL.  
- MT5 and internal position counts both report **1**.  
- Daily-loss flag false on the last observed cycle; entries blocked for open-slot only.  
- PME manages the open ticket; LIVE reversal exit remains shadow / disabled.

---

## 3. Broker-verified trading performance

### Historical closed book (12260878)

| Metric | Value |
| --- | --- |
| Closed positions | 46 |
| Wins / losses | 20 / 26 |
| Win rate | 43.5% |
| Gross profit / loss | +$30.53 / −$60.47 |
| Net | **−$29.94** |
| Profit factor | **0.50** |
| Expectancy / trade | **−$0.65** |
| Path max drawdown | **≈ −$34.04** |
| Avg hold | ≈ 232 s |
| Commission / swap in sample | $0 / $0 |
| Strategy ID on closes | largely absent historically |

| Side | n | WR | Net |
| --- | ---: | ---: | ---: |
| BUY | 34 | 41.2% | **−$28.12** |
| SELL | 12 | 50.0% | −$1.82 |

### Live account (12479147) — snapshot ~08:34 UTC 2026-11-06

| Item | Value |
| --- | --- |
| Balance | 33.82 |
| Equity | 32.6 |
| Margin / free | 2.03 / 30.57 |
| Open | 1 SELL 0.01 @ 4067.443, SL 4072.827, TP 4056.883, floating ≈ −1.5 |
| New entries | Blocked by concurrent cap |

Do **not** add this floating P/L to the n=46 net. Different login.

---

## 4. Strategy-by-strategy profitability

Historical closes are mostly **unattributed** (`strategy_id` missing; comments `[sl]` / `[tp]`). Per-strategy profit factor, expectancy, and regime/session books **cannot** be claimed from that sample without inventing IDs.

Attribution repairs (#166) apply to future closes. Until a broker-confirmed attributed sample accumulates:

- Do not disable BUY or SELL by strategy name.  
- Do not promote a “winning” strategy from n≈0 attributed LIVE fills.  
- Side-level evidence (BUY cascade) is the only strong directional finding in the 46-trade book.

Cascade price-rule counterfactual (documented earlier; **not** a forecast): blocking lower BUY re-entries would have cut that book’s net from −$29.94 toward roughly flat. Holdout on 5 Nov remained slightly negative. Reversal exceptions can re-admit winners and losers.

---

## 5. Capital protection architecture — status and gaps

| Layer | Status | Notes |
| --- | --- | --- |
| 1. Per-trade max planned risk 20% equity | Active | Absolute ceiling; not conservative for small equity |
| 2. Daily loss halt 48% SOD equity | Active | Realized; deposits excluded; formula audited correct |
| 3. Weekly loss halt | **Off** (0) | Owner 2026-10-23 |
| 4. Overall drawdown halt | **Off** unless saved | Default 0 |
| 5. Max aggregate open risk 30% | Active | With concurrent 1, largely overlapping per-trade |
| 6. Consecutive-loss cooldown | **Off** (`OWNER_MAX_CONSECUTIVE_LOSSES = 0`) | Observed max streak 5 in sample |
| 7. Same-direction re-entry | BUY durable cascade yes; **SELL no durable equivalent** | BUY fails closed if store untrusted |
| 8. Correlated exposure | Concurrent 1 + SOE thesis clustering | Helps; does not replace SELL cascade |
| 9. Spread / slippage | Soft score + hard spread ceiling; net RR after costs | Presend double-count fixed earlier |
| 10. Broker / gateway integrity | Gateway health, trade_allowed, sync before max-open reject | Observed working on open SELL |
| 11. Kill switch | Present in management / control plane | Must stay reachable |
| 12. Restart / account reconcile | BUY cascade restore + account-mismatch release (#172/#173) | Open positions recovered from MT5 |

Risk breaches must continue to **block new entries** while allowing PME / monitoring. Observed behavior matches that for max-open.

### Gaps (not silently “fixed” here)

1. 20% risk and 48% daily halt are too large for capital preservation on a ~$30–50 account.  
2. Consecutive-loss pause disabled.  
3. No durable SELL same-direction cascade guard.  
4. Weekly / overall drawdown halts off.  
5. Historical strategy attribution too thin for strategy kill/promote.  
6. No repository XAUUSD candle archive for honest walk-forward expectancy.

---

## 6. Risk policy mathematical assessment

Assumptions: gold contract size 100, volume 0.01 → **$1 of risk ≈ 1.00 price distance** on XAUUSD for this account class. Full-risk hits assume every stop realizes the planned risk (actual sample avg loss ≈ $2.33, often below 20% of equity when equity was already small).

| Equity | Risk / trade | $ / trade | Daily halt | Daily $ | Recovery after daily hit* | Full-risk hits to wipe ≈ |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 33.52 | 20% | 6.70 | 48% | 16.09 | +92% on remainder | ~5 |
| 33.52 | 5% | 1.68 | 10% | 3.35 | +11% | ~19 |
| 33.52 | 2% | 0.67 | 5% | 1.68 | +5% | ~50 |
| 33.52 | 1% | 0.34 | 3% | 1.01 | +3% | ~98 |
| 50 | 20% | 10.00 | 48% | 24.00 | +92% | ~5 |
| 50 | 2% | 1.00 | 5% | 2.50 | +5% | ~50 |
| 100 | 2% | 2.00 | 5% | 5.00 | +5% | ~50 |

\*Recovery % = daily_cap / (equity − daily_cap). A 48% daily hit requires roughly doubling what remains to recover the lost dollars.

Breakeven win rate with avg win W and avg loss L is `L / (W + L)`. At observed 1.53 / 2.33 that is ≈ **60%**. Observed WR **43.5%** cannot compound under that geometry.

---

## 7. Proposed safer risk policy (owner approval required)

**Do not activate without explicit owner approval.** Current LIVE settings remain as coded.

Recommended capital-preservation tier for a micro account:

| Setting | Current | Proposed (for approval) | Why |
| --- | --- | --- | --- |
| Risk per trade | 20% | **1–2%** | Survives dozens of full stops instead of ~5 |
| Daily loss halt | 48% | **3–5%** | Stops the day before a wipeout path |
| Consecutive-loss pause | Off | **3 losses → cool-down** | Breaks the 15-minute clusters |
| Max concurrent | 1 | **1** (keep) | Already correct |
| Max lot | 0.01 | **0.01** (keep) | Broker / owner floor |
| Min quality | 70 | **70** (keep; do not lower) | Selectivity |
| Min net RR | 0.20 / preferred 0.50 | Keep floors; prefer geometry that realizes ≥0.50 when structure allows | Addresses avg win < avg loss |
| BUY cascade | Durable | Keep | Proven for BUY re-entry |
| SELL same-direction guard | None durable | Design + approve separately | Symmetric cluster risk on Nov 2 SELL burst |
| Weekly halt | Off | Optional **8–10%** of week-start equity | Second backstop |

Also recommend: pause new entries while floating loss on the open ticket exceeds a fraction of daily budget (monitoring only until approved).

---

## 8. Changes implemented in this mission

| Change | Type |
| --- | --- |
| This report | Documentation |
| Stats artifacts `_capital_mission_stats.json`, `_capital_mission_risk_scenarios.txt` under profitability reports | Evidence helpers |

**Not implemented:** any change to lot, risk %, daily halt, quality floor, RR floor, concurrent positions, cascade semantics, or LIVE strategy thresholds.

---

## 9. Tests and evidence

Prior missions already cover BUY cascade, quality explanation, direction recency, and MTF clock labels (PRs #171–#177). This mission adds no behavior code; therefore no new production behavior tests were required beyond evidence reproduction from the broker JSON.

Evidence files:

- `docs/production/reports/profitability/loss_audit_broker_history.json`  
- `docs/production/reports/profitability/_capital_mission_stats.json`  
- Live Railway account / positions previews (login 12479147, ticket 687225893)

---

## 10. Remaining unknowns

1. Attributed LIVE closes after #166/#174–#177 (strategy-level expectancy).  
2. Whether open SELL 687225893 hits TP or SL (do not modify it).  
3. Post-cascade BUY expectancy under live reversal exceptions.  
4. Chronological candle walk-forward (no in-repo XAUUSD archive).  
5. Slippage vs planned risk on each of the 46 closes (comment shows SL/TP tags; tick-level fill audit not re-run here).

---

## 11. What is safe to deploy

- Documentation and observability of this report.  
- Continued enforcement of concurrent 1, Q70, mandatory SL, BUY cascade, account-aware reconcile.  
- Refusal of new entries when max open, quality &lt; 70, direction NONE, or risk locks fire.

---

## 12. What requires owner approval

1. Lowering risk per trade below 20%.  
2. Tightening daily halt below 48%.  
3. Re-enabling consecutive-loss pause.  
4. Adding a durable SELL same-direction cascade guard.  
5. Enabling weekly / overall drawdown halts.  
6. Any LIVE strategy threshold change aimed at more fills.  
7. Modifying or closing the current open position outside PME policy.

---

## 13. Next steps toward sustainable profitability

1. **Owner decision** on the safer risk table in §7.  
2. After approval, implement risk changes with regression tests only — no score inflation.  
3. Design SELL cascade with the same reclaim / structure rules as BUY (owner approval).  
4. Accumulate attributed LIVE closes; publish strategy books only when n is adequate.  
5. Import a verified closed-candle XAUUSD archive before claiming walk-forward edge.  
6. Keep refusing trades when edge, quality, RR, spread, or risk gates fail.

---

## Live safety confirmation

- No real-money test order placed for this mission.  
- Open SELL not modified.  
- Owner YAML / `owner_live_limits` constants not edited.  
- Production decisions unchanged by this document alone.
