# QuantForg — DIRECTION_NONE Root-Cause & BUY Loss Asymmetry

**Generated:** 2026-11-05T20:55:00Z  
**Baseline:** production `8157111d` (#169) · preserves #168 + owner safeguards  
**Broker sample:** `loss_audit_broker_history.json` (n=46 closed, magic 260720)  
**Analysis:** `buy_asymmetry_analysis.json` · `_analyze_buy_asymmetry.py`

**Honest verdict:** Current idle funnel is mostly **correct prefer-no-trade**. High opportunity scores (85–89) with `DIRECTION_NONE` are **not** missed forced trades — Probability Center already sets `eligible=False` without BUY/SELL. Historical net remains negative mainly from **BUY geometry + cascade entries**, not from DIRECTION_NONE itself. No experimental strategy/threshold deploy. Observability fix only (LTF edge in reject text + scan logs).

---

## 1. DIRECTION_NONE — exact causes and frequency

### Pipeline (authoritative)

```
MarketAnalysisSnapshot
  → decide_scalping_direction()     # independent BUY/SELL LTF scores; tie → NONE
  → quality_gates.clear_direction   # hard reject if not BUY/SELL
  → Probability Center              # opportunity_score; eligible only if score≥70 AND direction_ok
  → sniper_entry                    # WAIT_NO_DIRECTIONAL_EDGE when no edge
  → SOE multi-strategy pack         # prefer-no-trade if no passer (needs direction)
  → ITE execution contract          # DIRECTION_NONE / OPPORTUNITY_SCORE_BELOW_THRESHOLD
```

Direction is decided in `direction.py` from **LTF core** evidence (M1/M5 BOS/CHOCH, liquidity, OB, FVG), not total HTF-inflated scores. Margin default **5**. Tie / both-core within margin → **CONFLICT → NONE**. No core edge → **NO_LTF_EDGE → NONE**. Never defaults to BUY.

### What produces NONE (ranked)

| Cause | Mechanism | Forces trade? |
| --- | --- | --- |
| **NO_LTF_EDGE** | `ltf_buy≈ltf_sell≈0` or neither side clears margin | No — correct |
| **CONFLICT** | Both LTF sides have core; `\|buy−sell\| ≤ margin` | No — correct |
| Stale / incomplete bars | Would fail earlier market-data gates; not dominant in current logs | Fail-closed |
| AI vs setup family disagree | Setup suggestion logged; AI direction kept; no fabricated flip | No |
| Direction “lost” at SOE | SOE never invents side; NONE → no passer → prefer-no-trade | No |
| High opportunity + NONE | Structure/momentum inflate score; `direction_ok=False` → ineligible | No |

### Production frequency (recent LIVE sample)

Window ≈ last 500 log lines after #169 (~20:47–20:48Z):

| Signal | Count (approx) |
| --- | --- |
| `xauusd_signal_scan` | 5 |
| `multi_strategy_no_passer` / SOE prefer-no-trade | 5 |
| `OPPORTUNITY_SCORE_BELOW_THRESHOLD` (primary abort) | 15 |
| Primary `reason_code=DIRECTION_NONE` | 0 in this quiet window |
| Opp score ~85–89 | 0 (current tape ~54, bullish=8/bearish=8) |

**Earlier post-#168 window** (prior monitoring): frequent **opp 85–89 + DIRECTION_NONE** with bullish≈32 / bearish≈46 — CONFLICT/near-balance on totals while LTF edge absent; first_blocker often `WAIT_NO_DIRECTIONAL_EDGE`. Those were **valid rejects**, not calibration bugs forcing NONE incorrectly.

**Misread risk (fixed observability):** reject text previously said only “balanced scores → reject” without LTF BUY/SELL/edge, so operators could not tell CONFLICT vs NO_LTF_EDGE. Total `bullish_score`/`bearish_score` in logs are **not** the LTF edge test.

---

## 2. BUY versus SELL (broker-authoritative, n=46)

| | BUY | SELL |
| --- | --- | --- |
| n | **34** | 12 |
| Win rate | 41.2% | 50.0% |
| Net | **−$28.12** | −$1.82 |
| Avg win / avg loss | +$1.57 / **−$2.50** | +$1.44 / −$1.74 |
| Avg planned TP / SL dist | 1.56 / **2.38** | 1.44 / 1.60 |
| Implied planned RR | **0.66** | 0.90 |
| Avg hold | 259 s | 157 s |

### BUY session (UTC buckets)

| Session | n | Net | WR |
| --- | --- | --- | --- |
| **ny** | 16 | **−$16.86** | 37.5% |
| london_ny_overlap | 8 | −$7.71 | 37.5% |
| asia | 9 | −$1.80 | 55.6% |
| late_ny_asia | 1 | −$1.75 | 0% |

### BUY regime / timing evidence

- **12** consecutive pairs of lower-entry + both-loss (cascade BUY into declining marks).
- 2026-11-05 NY cluster: repeated BUY after deposit, TP ~+$1.3–1.5 vs SL ~−$2.7–3.7.
- Last BUY (19:36Z): SL comment 4106.751 but exit 4105.333 — **adverse slip** past stop.
- SELL sample small and near flat — **not** a proven edge; do not disable BUY/SELL on n=12/34.

**Not claimed:** per-strategy death (no `strategy_id` on historical comments).

---

## 3. SL/TP expectancy

| Metric | Value |
| --- | --- |
| Observed WR | 43.5% |
| Avg win / avg loss | +$1.53 / −$2.33 |
| Realized RR (dollars) | **0.66** |
| Breakeven WR at this RR | **60.4%** |
| Expectancy / trade | **−$0.65** |
| Req avg win for BE @ 43.5% WR | **~$3.02** (~2× current) |
| Commission / swap (sample) | **$0 / $0** |
| Spread | Soft-scored; not primary $ drag vs SL/TP asymmetry |

**Why ~+$1.50 TP vs ~−$3.00 SL:** structure TP often nearest level clearing RR floor **0.20** (~0.4–0.7R) while SL uses ATR/structure (~1R+). #166 preferred TP **0.50** helps only when L2 exists; late 11-05 trades after #166 still show near-floor TP when L2 absent.

**Hypothetical (not deployed):** if avg win rose to match avg loss at same WR → expectancy ≈ −$0.20 (still negative). Need either higher WR, larger TP when structure allows, or fewer BUY cascades — not arbitrary SL tighten.

Chronological sample is the full available broker book (n=46); no separate attributed OOS fill set post-#168 (still **0** fills).

---

## 4. Fixes implemented

| Fix | Behavior change |
| --- | --- |
| Quality-gate NONE reject includes `CONFLICT`/`NO_LTF_EDGE` + LTF BUY/SELL/edge | **Observability only** — same hard reject |
| `xauusd_signal_scan` logs `ltf_buy_score`, `ltf_sell_score`, `directional_edge`, `edge_margin`, `direction_ok`, `opportunity_eligible` | Logs only |

**Not changed:** Q70, RR floor, max lot, risk %, daily stop, concurrent 1, mandatory SL, no grid/martingale/averaging, no forced direction, no BUY/SELL disable, no LIVE experimental strategy.

---

## 5. Tests and backtest results

| Test | Result |
| --- | --- |
| `test_direction_none_observability.py` | Pass (CONFLICT / NO_LTF_EDGE text) |
| `test_close_attribution.py` | Pass (28 combined with gold reject obs) |
| Broker chronological expectancy | Reproduced: n=46, −$29.94, PF 0.50, BE WR 60.4% |
| Post-#168 OOS fills | **Empty** |

---

## 6. Attribution verification

Path (post-#166):

1. Fill → `attribution_store.bind_fill(strategy_id, ticket, …)`
2. Entry comment engine tags (`m1:` / `ite:`) as fallback
3. Close → `attribute_broker_exit` resolves `strategy_id`, records SOE stats, then clears binding
4. Premature clear without sid **removed** (race fix)
5. Unit tests cover restart-safe ledger + bind_fill → close → `soe_recorded=True`

**LIVE proof pending:** next broker-confirmed close must log `broker_confirmed_close_attributed` with non-null `strategy_id` and `soe_recorded=true`. Historical 46 closes remain unattributed in comments.

---

## 7. Current production status

| Item | Status |
| --- | --- |
| Commit (pre-this-PR) | `8157111d` |
| `/health` | ok |
| Account | $18.30 / $18.30 · 0 positions · trade_allowed |
| LIVE | Scanning; prefer-no-trade; no new fills |
| Owner policy | Unchanged |

---

## 8. Remaining uncertainty

1. Post-#168 fill sample still empty — cannot measure #168 P/L impact.
2. Whether preferred TP 0.50 improves expectancy needs attributed post-#166/#168 closes with L2 present.
3. BUY NY cascade may recur when direction returns — monitor; do not ban BUY on n=34.
4. LTF vs total score divergence needs the new log fields on the next high-opp NONE episode to confirm CONFLICT rates.

**Goal reminder:** more **valid** opportunities and better expectancy — not more trades. Fabricating direction would violate owner policy and is rejected.
