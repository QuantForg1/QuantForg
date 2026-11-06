# QUANTFORG PR #184 — Strategy Performance & Profitability Optimization

**Audit time (UTC):** 2026-11-06 ~11:30–12:00  
**Instrument:** XAUUSD  
**Method:** Public `/health`+`/ready`, Railway variables + logs, gateway broker-authoritative deals for login **12479147**, code inspection of SOE / unified decision / M1 / cascades.  
**Principles:** Capital preservation first. No invented P&L or backtests. No real-money test orders. Owner risk policy unchanged. M1 LIVE submit left OFF. Reverse entry left OFF. BUY/SELL cascades not weakened.

---

## 1. Production verification

| Check | Evidence | Result |
| --- | --- | --- |
| GitHub `main` (audit baseline) | `gh api` at start | `741a99ec` over trading `5df0a872` |
| GitHub `main` (after PR #184 merge) | `gh api` | `8b4c7a1aba84c7a86021093854ca781a2ebde705` |
| Railway `/health.commit` (post-merge) | public GET | `8b4c7a1aba84…` **matches main** |
| Trading protections baseline | PR #182 | Cascades / LIVE / M1-submit policy unchanged by this audit |
| `/ready` | public GET | ok · routers complete |
| Railway service | `railway status` | Online |
| Worker | logs `worker_state=RUNNING` | **Running** |
| Open positions | gateway `/positions` | **0** |
| Broker login | gateway `/account` | **12479147** · Weltrade-Real |
| Equity / balance | gateway | **21.46 / 21.46** |
| Trade allowed | gateway | true |

### Feature flags (Railway variables — observed, not assumed from code defaults)

| Flag | Value | Effective |
| --- | --- | --- |
| `EXECUTION_ENABLED` | `true` | LIVE execution authorized |
| `QUANTFORG_M1_MICRO_SCALPING` | `true` | M1 **evaluation ON** |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | `false` | M1 **OMS submit OFF** |
| `QUANTFORG_LIVE_REVERSAL_EXITS` | **unset** | Code default → LIVE close-on-confirmed-reversal **ON** |
| `ALLOW_RISK_LOCK_OVERRIDE` | `false` | Override disabled |
| `FORCE_FIRST_TRADE` | `false` | No force-first |

### Cascade / protection (production logs at PR #182 deploy)

| Control | Status |
| --- | --- |
| BUY cascade | `buy_cascade_startup_restore` trusted=True |
| SELL cascade | `sell_cascade_startup_restore` trusted=True; backfilled 9 SELL loss anchors on 12479147 |
| Reverse entry | Forced `live_reverse_entry_enabled=False` in runtime |
| M1 submit in cycles | `m1_complement … submitted=False` |

---

## 2. Account-separated performance

### Account isolation

| Account | Role in this audit |
| --- | --- |
| **12479147** | Current gateway session — **only** account with live deal history used below |
| **12260878** | **Not** on current gateway session. Prior historical figures must not be merged into 12479147 totals |

Evidence artifact: `docs/production/reports/pr184/performance_analysis.json`

### Period cutoffs (UTC)

| Period | Cutoff | Closed XAU positions (12479147, 30d window) | Net |
| --- | --- | --- | --- |
| Pre-PR #180 | `< 2026-11-06T09:51Z` | **55** | **+4.68** |
| Post-PR #180 / pre-PR #182 | `≥ 09:51` and `< 11:11` | **8** | **−25.22** |
| Post-PR #182 | `≥ 11:11` | **0** | n/a |
| All in window | — | **63** | **−20.54** |

Post-PR #182 has **no** new closed trades yet — cascade durability is evidenced by restore/backfill logs, not by a new win streak.

---

## 3. Strategy scorecards

### Engine-level (broker-recoverable)

Five-pack SOE IDs (`trend_continuation`, `momentum_scalping`, …) are **not** in MT5 comments (`ite:v1:{S|H}:{hash}` only). Historical five-pack scorecards are therefore **Unreliable attribution**. Engine tags only:

| Bucket | n | Win rate | Net | Expectancy | BE win rate | Classification |
| --- | --- | --- | --- | --- | --- | --- |
| `ite_primary` (all tagged) | 63 | 50.8% | −20.54 | −0.326 | 56.5% | Negative expectancy |
| `m1_micro` | 0 | — | — | — | — | Insufficient data |
| Pre-PR #180 | 55 | 58.2% | +4.68 | +0.085 | 56.7% | Demonstrated positive expectancy |
| Post-PR #180 cascade window | 8 | 0% | −25.22 | −3.15 | n/a | Negative (provisional / small) |

### Direction

| Side | n | Win rate | Net | Expectancy | Classification |
| --- | --- | --- | --- | --- | --- |
| BUY | 13 | 46.2% | −8.48 | −0.65 | Negative (provisional) |
| SELL | 50 | 52.0% | −12.06 | −0.24 | Negative expectancy |

### Five-pack SOE strategies

| Strategy | Classification |
| --- | --- |
| trend_continuation / smc_scalping / breakout_scalping / momentum_scalping / range_mean_reversion | **Unreliable attribution** on broker history — ticket store may hold IDs at fill, but MT5 history alone cannot recover them; do not promote/disable from this sample |

---

## 4. BUY and SELL performance / loss root causes

### Confirmed root cause of the post-PR #180 wipe (PR #181 → fixed in #182)

Eight consecutive **SELL** SL exits (−25.22) after PR #180 because SELL cascade was file-backed / fail-open and not armed like BUY. **PR #182** made SELL anchors durable Postgres + fail-closed. Do not weaken.

### Other loss drivers (evidence-based)

1. **Same-direction SELL re-entry into unresolved adverse tape** — primary capital damage in the post-180 window; losses ≈ planned SL risk (ratios ~1.0–1.12) → sizing/SL geometry OK, **selection/re-entry** failed.
2. **No LIVE reversal exits observed** in that 8-trade sample — all broker `[sl …]`; reversal config ON ≠ demonstrated protective effect on that window.
3. **BUY sample small and net-negative** (−8.48 / 13) — insufficient to claim BUY edge after costs.
4. **Win rate near break-even but avg loss ≥ avg win** overall — observed BE win rate ~56.5% vs actual ~50.8% → negative expectancy.
5. **Correlated SOE trend cluster** — orchestrator already de-duplicates trend-cluster confluence; still one LIVE order path (good). Residual risk is poor regime timing, not multi-order spam.
6. **Spread/commission fields often 0** on gateway deals — cost-adjusted figures ≈ gross profit field; true spread cost may be embedded in fill prices (not separately itemized).

### Cascade verification (post-#182)

- Startup restored BUY + SELL stores as trusted.
- Backfilled nine broker-confirmed SELL losses on 12479147 (includes the eight cascade tickets).
- Historical anchors later released via documented bearish-reversal path after structure already printed — consistent with rules; **future** SELL losses re-arm.

---

## 5. Reversal protection performance

| Item | Finding |
| --- | --- |
| Config | LIVE reversal exits default ON (`QUANTFORG_LIVE_REVERSAL_EXITS` unset) |
| Broker evidence post-#180 sample | **0** reversal-tagged closes; **8/8** SL |
| Verdict | Activation verified by config; **effectiveness not demonstrated** on available broker closes |

---

## 6. M1 strategy findings

| Item | Finding |
| --- | --- |
| Evaluation | ON |
| LIVE OMS submit | **OFF** (`submitted=False` in cycles) |
| Broker fills with `m1:` comment | **0** in analyzed window |
| Expectancy | **Cannot claim** — no broker-confirmed M1 outcomes |
| Role | Timing complement under unified decision; must not override HTF blindly; submit stays OFF |

---

## 7. Strategy coordination findings

| Requirement | Status |
| --- | --- |
| Single decision owner | SOE → one primary; `unified_decision.resolve_unified` for primary↔M1 |
| Duplicate / correlated votes | Trend-cluster confluence counting in `orchestrator.py` |
| Conflict BUY vs SELL | Wait / direction_conflict — no hedge |
| One order to Risk/OMS | Enforced (max concurrent 1 + unified path) |
| Explainable rejects | Scoring reject list + wait codes |

No evidence of multiple independent LIVE submissions for one opportunity in the broker sample (sequential tickets, concurrent 0–1).

---

## 8. Cost-adjusted expectancy

| Window | n | WR | Avg win | Avg loss | BE WR | Expectancy | Verdict |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Pre-#180 | 55 | 58.2% | (from card) | (from card) | 56.7% | **+0.085** | Thin positive edge **before** cascade failure |
| Post-#180 (8 SELL) | 8 | 0% | n/a | −3.15 | n/a | **−3.15** | Destroyed prior edge |
| All 63 | 63 | 50.8% | — | — | 56.5% | **−0.326** | Negative overall |

No candle backtest was invented. Out-of-sample post-#182 closed-trade sample = **0**.

---

## 9. Confirmed defects

| # | Defect | Status |
| --- | --- | --- |
| 1 | SELL cascade gap (PR #181) | **Fixed in PR #182** — leave armed |
| 2 | Five-pack strategy_id not in MT5 comments → historical scorecards unreliable | **Open** (structural); fill-time store helps only while process memory/disk survives |
| 3 | `bind_fill(... strategy_id="ite_primary")` when SOE id missing **pollutes** strategy books with an engine tag | **Fixed this PR** — bind only real SOE ids |
| 4 | Reversal exits not observed as broker closes in cascade window | **Open / monitor** — do not weaken; gather more evidence |
| 5 | M1 submit OFF → no LIVE M1 expectancy | **By design** this PR |

---

## 10. Changes made (this PR)

1. **Attribution honesty:** ITE fill path binds `StrategyAttributionStore` only when a real SOE `strategy_id` is present — no invented `ite_primary` strategy_id.
2. **Profitability metrics module:** `app/domain/.../profitability_metrics.py` + unit tests for expectancy / BE win rate / classifications.
3. **Audit artifacts:** `docs/production/reports/pr184/` analysis scripts + `performance_analysis.json`.
4. **This report.**

**Not changed:** risk 20%/48%/0.01, Q≥70, RR floors, cascades, LIVE enablement, M1 submit, reverse entry, strategy thresholds, regime classifiers, quality floors.

---

## 11. Tests

Local (representative):

- `test_profitability_metrics.py` — new
- BUY/SELL cascade, PR180 protection, close attribution, strategy attribution store
- **66 passed** in focused run

Full CI required green on PR before merge.

---

## 12. Remaining limitations

1. Post-#182 closed-trade sample = 0 — cannot yet prove expectancy improvement from cascade alone.
2. Account 12260878 not queried on this gateway session.
3. Five-pack historical attribution remains incomplete without durable ticket→strategy persistence beyond local JSON.
4. Commission/swap often zero in gateway fields — costs may be in price.
5. No invented multi-year backtest.

---

## 13. Features genuinely LIVE vs OFF

| Feature | State |
| --- | --- |
| LIVE execution | **ON** |
| BUY cascade (Postgres) | **ON** |
| SELL cascade (Postgres) | **ON** |
| LIVE confirmed-reversal close | **ON** (default) |
| M1 evaluation | **ON** |
| M1 LIVE OMS submit | **OFF** |
| Automatic reverse entry | **OFF** |
| Grid / martingale / averaging | **OFF** |

---

## 14. Recommended next optimization (priority order)

1. **Capital:** Keep cascades + Q70 + concurrent 1; do not chase frequency.
2. **Attribution durability:** Postgres (or volume) for ticket→five-pack bindings so future scorecards are trustworthy.
3. **Regime / SELL selectivity:** After a meaningful post-#182 sample, tighten SELL entries in range/expansion only with evidence — **owner approval** required for behavior changes.
4. **Reversal effectiveness study:** Tag and measure broker closes that actually exit via reversal path.
5. **M1:** Keep submit OFF until shadow/broker-linked expectancy is positive and HTF-aligned.

---

## 15. Owner policy confirmation

Risk 20% · Absolute 20% · Daily halt 48% · Max lot 0.01 · Q≥70 · Min RR 0.20 · Preferred 0.50 · Concurrent 1 · Aggregate 30% · Mandatory broker SL · No grid/martingale/averaging — **unchanged**.

CAPITAL PRESERVATION FIRST · PROVEN EDGE SECOND · SUSTAINABLE COMPOUNDING THIRD.
