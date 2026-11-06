# QUANTFORG PR #186 — Strategy Attribution Integrity & Post-#182 Performance Monitoring

**Date:** 2026-11-06  
**Instrument:** XAUUSD  
**Baseline:** PR #184/`8b4c7a1a` · docs PR #185/`85166552`  
**Scope:** Observability + durable attribution only — **no** LIVE decision, risk, cascade, M1-submit, or reverse-entry changes.

---

## 1. Attribution root cause

Historical MT5 deals show `ite:v1:{S|H}:{hash}` because OMS comments are built by `encode_execution_comment` for class/hash only (31-char constraint). Five-pack SOE IDs (`smc_scalping`, …) were never written into the broker comment.

Lifecycle gaps before this PR:

| Stage | Gap |
| --- | --- |
| SOE select | Real `strategy_id` exists on orchestration result |
| Fill bind | Ticket store was **file-only** → lost on Railway restart |
| Comment map | `ite:*` was mapped to fabricated **`ite_primary`** as `strategy_id` |
| Close | Exit comment `[sl]`/`[tp]` overwrites entry comment → store must be SoT |
| Metrics | Unattributed or polluted IDs made five-pack expectancy unreliable |

PR #184 stopped inventing `ite_primary` on `bind_fill`. This PR removes remaining `ite_primary` invention from comment→metadata paths and persists bindings + outcomes in Postgres.

---

## 2. Existing five-pack strategy IDs

From `app/domain/.../strategies/registry.py`:

| ID | Name |
| --- | --- |
| `smc_scalping` | SMC Scalping |
| `trend_continuation` | Trend Continuation Scalping |
| `breakout_scalping` | Breakout Scalping |
| `range_mean_reversion` | Range Mean-Reversion Scalping |
| `momentum_scalping` | Momentum Scalping |

M1 engine identity `m1_micro` is separate (comment `m1:*`), not a five-pack member.

---

## 3. Attribution propagation design

1. SOE selects primary `strategy_id` + `influence_weights` contributors.  
2. ITE fill path binds **only** a real SOE id (never `ite_primary`) via `StrategyAttributionStore.bind_fill`, including contributors.  
3. MT5 comment format **unchanged** (`ite:v1:{S\|H}:{digest}`).  
4. Durable Postgres table `strategy_attribution_binding` + file cache.  
5. On broker-confirmed close: resolve binding → write `strategy_trade_outcome` → clear binding.  
6. Unknown remains `strategy_id=NULL` / confidence `unknown`.  
7. Startup: `recover_strategy_attribution_on_startup` restores bindings + pins broker login.

---

## 4. Broker reconciliation

- Outcomes keyed by `(position_id, exit_deal_id)` — idempotent.  
- Net P&L = broker profit + commission + swap when present.  
- `costs_complete=False` when commission/swap absent (not silently zero for claims).  
- Account isolation via `broker_login`.  
- Order requests are never outcomes; only confirmed closes via `record_broker_confirmed_close`.

---

## 5. Post-PR #182 performance monitoring

Module: `performance_monitor.build_post182_performance_monitor`  
Ops (auth): `GET .../strategy-attribution-performance`

Periods (UTC):

- `pre_pr180` — before `2026-11-06T09:51Z`  
- `post_pr180_pre_pr182` — until SELL cascade deploy ~`11:11Z`  
- `post_pr182` — after  

Account **12260878** must be queried separately; never merged with **12479147** without an explicit combined label.

At audit time, durable outcome rows begin with this deploy — historical broker history remains in PR #184 JSON artifacts and is not rewritten with invented strategy IDs.

---

## 6. Account-separated statistics

| Account | Source | Note |
| --- | --- | --- |
| 12479147 | Current LIVE gateway | Post-#182 monitoring target |
| 12260878 | Not on current session | Keep separate |

PR #184 broker sample (12479147) remains the historical reference; five-pack expectancy there is **Insufficient attribution**.

---

## 7. Strategy scorecard

`build_five_pack_scorecards` emits one card per registry strategy + an unattributed bucket, with honest classifications:

- Positive expectancy demonstrated  
- Negative expectancy observed  
- Promising but insufficient sample  
- Insufficient attribution  
- Insufficient data  

Signal/qualified counts remain `null` until cycle telemetry is joined — closed trades are broker-authoritative only.

---

## 8. Data-quality limitations

1. Pre-deploy history cannot recover five-pack IDs from MT5 comments.  
2. File cache alone is insufficient without Postgres.  
3. Broker commission/swap often report `0.0` — complete but may embed spread in price.  
4. Post-#182 closed sample may still be small immediately after deploy.  
5. Contributors are advisory (influence weights), distinct from primary selected id.

---

## 9. Changes implemented

| Change | Trading behavior impact |
| --- | --- |
| Postgres `strategy_attribution_binding` | None — observability |
| Postgres `strategy_trade_outcome` | None — observability |
| Stop inventing `ite_primary` from `ite:*` comments | Attribution honesty only |
| Contributors on bind_fill | None |
| Startup attribution restore | None |
| Ops endpoint `/strategy-attribution-performance` | Read-only |
| Tests for attribution + scorecards | None |

Owner risk, cascades, LIVE enablement, M1 submit OFF, reverse entry OFF — **unchanged**.

---

## 10. Tests

- `tests/unit/test_pr186_attribution_performance.py`  
- Updated `test_close_attribution.py`, `test_strategy_attribution_store.py`  
- Cascade / profitability regressions green in focused runs  

Full CI required on PR.

---

## 11. Production verification

Fill after merge:

| Check | Value |
| --- | --- |
| GitHub main | _(post-merge)_ |
| `/health.commit` | must match |
| `/ready` | ok |
| LIVE / cascades / M1 submit | unchanged |

---

## 12. Features LIVE versus OFF

| Feature | State |
| --- | --- |
| LIVE execution | ON |
| BUY / SELL cascade | ON |
| LIVE reversal exits | ON |
| M1 evaluation | ON |
| M1 LIVE submit | OFF |
| Reverse entry | OFF |
| Durable attribution bindings | ON (this PR) |
| Durable trade outcomes | ON (this PR) |

---

## 13. Remaining risks

1. First deploy must create Postgres tables successfully.  
2. Fills without SOE `strategy_id` remain unattributed (honest).  
3. No profitability claim until post-#182 attributed sample is adequate.

---

## 14. Recommended next step

After a meaningful post-#182 attributed sample: strategy-selective optimization under owner approval — **only** with broker-confirmed expectancy, never from unattributed `ite:v1` history.

ACCURATE ATTRIBUTION FIRST · RELIABLE EVIDENCE SECOND · OPTIMIZATION THIRD.
