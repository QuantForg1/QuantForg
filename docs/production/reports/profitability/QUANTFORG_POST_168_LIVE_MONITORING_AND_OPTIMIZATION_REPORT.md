# QuantForg — Post-#168 LIVE Profitability Monitoring & Strategy Optimization

**Generated:** 2026-11-05T20:05:00Z  
**Baseline deploy:** `afe30c48` (PR #168) — Railway SUCCESS `72070c3f` @ `2026-11-05T19:42:46Z`  
**Instrument / account:** XAUUSD · Weltrade-Real · login `12260878`  
**Owner policy:** **unchanged** (max_lot 0.01, Q≥70, RR floor 0.20 / preferred 0.50, risk 20%, daily halt 48% SOD, concurrent 1, mandatory SL, no grid/martingale/averaging, no forced entries)

**Honest verdict:** #168 is **live and healthy**, but **post-deploy broker fills = 0**. Impact on net P/L, PF, expectancy, and win rate is **not yet measurable**. Historical net remains negative from the **pre-#168** sample (n=46, −$29.94, PF 0.50), driven by asymmetric SL vs TP and BUY-heavy losers. No experimental strategy change was deployed to LIVE.

---

## 1. Current broker-authoritative status

| Item | Value (fresh probe) |
| --- | --- |
| Production commit | `afe30c4824a6d5b90c1850f93d72de0993d0eab9` |
| Railway deploy | `72070c3f` SUCCESS (sfo) |
| `/health` · `/ready` | `ok` · `ok` (routers complete) |
| LIVE worker | `mode=LIVE` · `execution_enabled=True` · `run_state=running` |
| MT5 Gateway | attached · Weltrade-Real · trade_allowed · AutoTrading on |
| XAUUSD | market_open · bid/ask ~4115.4 / 4115.8 · fresh ticks |
| Balance / equity | **$18.30 / $18.30** |
| Floating P/L | **$0.00** |
| Open positions | **0** |
| Closed positions (30d sample) | **46** (unchanged vs pre-cutover) |
| Last broker close | **2026-11-05 19:39:22Z** (≈3.4 min **before** #168 cutover) |

Probe artifact: `docs/production/reports/profitability/post168_monitor_probe.json`  
History artifact: `docs/production/reports/profitability/loss_audit_broker_history.json` (refreshed)

### Protective controls (observed)

| Control | Status |
| --- | --- |
| Max lot 0.01 / concurrent 1 / Q70 / RR≥0.20 | Present in owner limits (code) |
| Capital protection soft scale | `scale=0.5` — approaching daily loss + drawdown (post-deposit day loss ≈ −$12.62) |
| Owner daily hard stop (48% SOD) | **Not exceeded** post +$16 deposit @ 18:13:47Z (cap ≈ $14.84; loss $12.62) |
| Mandatory SL / no martingale / no forced entries | Intact; cycles abort on `DIRECTION_NONE` |
| Open positions | None modified |

---

## 2. Pre-#168 versus post-#168 (do not mix)

**Cutover:** `2026-11-05T19:42:46Z` (Railway deploy created).

| Metric | Pre-#168 (all closes with `last_time` &lt; cutover) | Post-#168 |
| --- | --- | --- |
| Broker-confirmed closes | **46** | **0** |
| Wins / losses | 20 / 26 | — |
| Win rate | 43.5% | — |
| Gross profit / loss | +$30.53 / −$60.47 | — |
| Net P/L (comm/swap 0) | **−$29.94** | **$0.00** (no sample) |
| Profit factor | **0.50** | n/a |
| Expectancy | **−$0.65** / trade | n/a |
| Avg winner / loser | +$1.53 / −$2.33 | — |
| Max DD (cum. path) | ≈ −$34 | — |
| Avg R (vs avg loss) | ≈ −0.28R | — |
| OMS / fills | Historical only | **0** submissions → fills |
| TP / SL outcomes | 20 TP / 26 SL | — |

### Same-UTC-day context (pre-cutover only)

| Window | n | Net | Note |
| --- | --- | --- | --- |
| 2026-11-05 UTC all closes | 17 | **−$20.33** | All **BUY** |
| After deposit 18:13:47Z | 9 | **−$12.62** | Risk daily PnL basis |
| After #168 cutover | 0 | — | Idle / prefer-no-trade |

### Funnel after #168 (LIVE logs, qualitative)

| Stage | Observation |
| --- | --- |
| Generated scans | Continuous XAUUSD cycles |
| Opportunity score | Often **85–89** (≥ Q70 threshold) |
| Direction | Persistently **NONE** (bullish≈32, bearish≈46) |
| Qualified directional | **0** (balanced scores → reject) |
| SOE | `multi_strategy_no_passer` / prefer-no-trade (floors 76/80 live) |
| Risk approvals / OMS / fills | **0** |
| First blockers | `WAIT_NO_DIRECTIONAL_EDGE`, `WAIT_NO_VALID_TP_ROOM`, `OWNER_MIN_RR: net reward:risk None`, `DIRECTION_NONE` |

**Interpretation:** #168 removed false **presend** RR rejects and relaxed SOE solo bars / RR quality mapping. Those gates only matter once a **BUY/SELL** with valid TP exists. Current tape has **no directional edge**, so opportunity expansion is correctly idle — not a regression to “zero opportunity forever,” and not yet proof of improved expectancy.

---

## 3. Five-strategy scorecard

**Cannot invent attribution.** All 46 broker closes carry exit comments only (`[tp …]` / `[sl …]`); `strategy_id` not present on historical deals. Pre-#166 SOE books were incomplete for this sample.

| Strategy | Trade count | Win rate | Net | PF | Expectancy | … |
| --- | --- | --- | --- | --- | --- | --- |
| SCALPING_V1 / others | **unknown** | — | — | — | — | — |

Post-#166/#168 code preserves `strategy_id` / `soe_recorded` on **future** closes. Re-score after attributed fills accumulate. Engine tags (`m1:` / `ite:`) also absent on this broker comment set.

**Loss concentration (authoritative without strategy_id):** BUY side and SL outcomes — see §4–5.

---

## 4. BUY versus SELL (pre-#168 broker sample)

| Side | n | Win rate | Net P/L |
| --- | --- | --- | --- |
| **BUY** | 34 | 41.2% | **−$28.12** |
| SELL | 12 | 50.0% | −$1.82 |

| Topic | Evidence |
| --- | --- |
| Entry quality | Short holds (~minutes); cascade BUYs into falling marks on 2026-11-05 |
| SL / TP | SL bucket −$60.47 vs TP +$30.53; avg loss 1.52× avg win |
| Structure / momentum | LIVE post-#168: structure/momentum scores high but **balanced** → NONE (no force) |
| Spread / slippage | Soft-scored; sample commission/swap **$0** |
| Session / vol | Not re-bucketed without verified session map; do not invent labels |

**Directional weakness supported by data:** BUY fills dominate dollar loss. SELL sample is small and near flat — not a proven edge.

---

## 5. Exact causes of losses (unchanged root, updated clock)

1. **Asymmetric geometry (primary $):** near-floor TP vs wider SL → PF 0.50. Last 10 pre-cutover closes (after #166 preferred-TP preference) still show TP ≈ +$1.3–1.5 vs SL ≈ −$2.7–3.7 when L2 preferred RR was unavailable — preferred TP helps **only when** a second structure level clears 0.50.
2. **BUY bias into losers:** 34/46 BUY; today UTC 17/17 BUY, −$20.33.
3. **Capital thinness:** $18.30 equity after deposits $48 and trading −$29.94; 0.01 lot + 20% risk caps stop distance.
4. **Not primary $:** attribution race / STALE_RISK / high_quality telemetry (addressed in #166); presend double-count RR (addressed in #168) — none yet validated on new fills.

---

## 6. Fixes implemented this mission

| Change | Scope | LIVE trading behavior |
| --- | --- | --- |
| Scan `purpose=scan` no longer trips `daily_pnl_fail_closed` / `history_deals_unavailable` alarm | `ite_cycle_market_context.py` + unit test | **None** — telemetry only. Execution path still fail-closes on true deal outages. |
| Monitoring report + refreshed broker probe/history | docs / JSON | None |

**Not implemented (requires attributed fills + explicit approval):** weakening `WAIT_NO_DIRECTIONAL_EDGE`, forcing SOE passers, raising trade count, LIVE reversal, lot/risk/Q changes, experimental indicator rewrites.

---

## 7. Backtest / out-of-sample evidence

| Item | Result |
| --- | --- |
| Broker chronological baseline | Reproduced: n=46, −$29.94, PF 0.50 |
| Post-#168 OOS fills | **Empty** — no trade-level OOS for #168 P&L |
| Unit regression | `tests/unit/test_ite_cycle_risk_fail_closed.py` — 4 passed (incl. scan skip) |
| Strategy parameter search | **Not run into LIVE** — would overfit without holdout attributed sample |

---

## 8. Remaining risks

1. **Empty post-#168 fill sample** — cannot claim improved expectancy yet.
2. **BUY asymmetry may persist** when direction returns — preferred TP only helps if L2 exists.
3. **Soft capital scale 0.5** while min=max lot 0.01 is a no-op on size; drawdown proxy still uses daily loss %, not peak-equity DD (measurement quirk; not changed).
4. **True** `history_deals` outages still fail-closed (correct); must not be confused with former scan noise.
5. **Attribution** still unproven on LIVE closes until the next filled+closed ticket shows `strategy_id` / `soe_recorded=true`.

---

## 9. Deployment and verification evidence

| Check | Result |
| --- | --- |
| Git HEAD (local at report) | `afe30c48` (+ pending telemetry commit if merged) |
| Railway production | SUCCESS on `afe30c4` · service QuantForg |
| Domain health | `https://quantforg-production.up.railway.app/health` → `{"status":"ok"}` |
| Ready | `status=ok`, routers complete |
| LIVE scheduler | `Scheduler Tick` · `execution_enabled=True` · `mode=LIVE` |
| MT5 | Gateway session attached; account/positions/quotes probed |
| CI | Validate on PR/push of telemetry fix |

---

## Bottom line

- **#168 did not worsen LIVE:** worker healthy, owner guards intact, prefer-no-trade when edge is absent.
- **#168 did not yet prove better P/L:** zero post-deploy fills.
- **Historical net is still negative** for the reasons in the prior loss audit (geometry + BUY), not because scans are “too quiet” today.
- **Next evidence gate:** first post-#168 attributed closes — compare RR realized, side mix, `strategy_id`, `soe_recorded`, STALE_RISK rate, and `high_quality` vs quality≥70 on **BUY/SELL** rows only (`high_quality=False` on `direction=NONE` is by design).

**No profitability promise.** Report evidence only.
