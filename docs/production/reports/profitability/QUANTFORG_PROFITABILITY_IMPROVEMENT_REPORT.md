# QuantForg — Profitability Improvement Report

**Generated:** 2026-11-05T15:20:00Z  
**Instrument:** XAUUSD / Weltrade-Real  
**Owner policy:** immutable (max_lot 0.01, risk 20%, RR≥0.20, Q≥70, concurrent 1, daily halt 48%, aggregate 30%, mandatory SL, no grid/martingale/averaging, M1 LIVE off)

**Verdict:** **Negative expectancy** on the broker-confirmed closed sample, with the LIVE robot currently **healthy but capital-constrained** (no open positions; high-quality signals correctly rejected by `MIN_LOT_INFEASIBLE`). No profitability claim is authorized.

---

## 1. Current production baseline (read-only)

| Check | Evidence |
| --- | --- |
| LIVE mode / scheduler | Railway logs `mode=LIVE` `execution_enabled=True` `run_state=running` (deploy `95d7a582`, post-#160) |
| Open positions | Gateway `/positions` → `{"items":[]}` — **0** MT5 / QuantForg |
| Balance / equity | Gateway `/account` preview: **balance=14.92 equity=14.92** (Weltrade-Real login 12260878) |
| Kill-switch | No arm events in sampled cycle; capital protection scale `0.55` (drawdown protection) active |
| Gateway | `gateway.quantforg.com` HTTP/2 200 on positions/account/candles/quotes |
| PME recovery | `mt5_positions=0 quantforg_positions=0 registered=0` |
| Owner floors | Unchanged — Risk Engine rejecting stop 5.065 > max_allowed_stop ≈ 2.98 at equity 14.92 |

Robot left running. No restart, disarm, arm, pause, or position interference.

Local authenticated ops/portfolio refresh was **not** available (`QUANTFORG_OWNER_TOKEN` / Supabase keys empty in local `.env`). Broker facts above come from Railway production logs (gateway responses), not fabricated snapshots.

---

## 2. Broker-confirmed performance (existing audit corpus)

Source: `docs/production/reports/scalping_optimization/audit_analysis.json` (generated 2026-11-05, equity snapshot then **22.63**).

### Closed trades (n=29)

| Metric | Value |
| --- | --- |
| Wins / losses | 14 / 15 |
| Win rate | 48.28% |
| Gross profit / loss | +20.36 / −29.97 |
| **Net** | **−9.61** |
| Profit factor | **0.68** |
| Expectancy | **−$0.33 / trade** |
| Avg win / avg loss | +1.45 / −2.00 |
| Avg hold | ~198 s |

### Exit geometry

| Exit | n | Net |
| --- | --- | --- |
| SL | 15 | **−29.97** |
| TP | 14 | +20.36 |

Average loss exceeds average win (~1.37×). That asymmetry — not win rate alone — is the primary expectancy drag.

### Session (monetary impact)

| Session | n | Net | PF | Expectancy |
| --- | --- | --- | --- | --- |
| **london_ny_overlap** | 7 | **−4.81** | 0.38 | −0.69 |
| new_york | 12 | −1.25 | 0.90 | −0.10 |
| asia | 9 | −1.80 | 0.76 | −0.20 |
| off_hours | 1 | −1.75 | 0.00 | −1.75 |

Largest avoidable-loss **session** driver by net dollars: **london_ny_overlap**.

### Classification

**Negative expectancy** (broker-confirmed sample). Sample is small; not “statistically sufficient” for strategy death sentences, but enough to reject a profitability claim and to prioritize loss reduction over activity.

Post-Phase-3 / post-SOE closed fills in the same dump: **0** (Risk / geometry bound). Telemetry: high-quality signals present, risk blocks dominate.

---

## 3. Loss-driver analysis (monetary)

1. **Asymmetric R realization** — SL bucket −$29.97 vs TP +$20.36. Late/adverse stops and/or insufficient BE/trail protection dominate dollars.
2. **Overlap session** — −$4.81 of the −$9.61 net (≈50% of sample loss dollars).
3. **Capital erosion → tradeability collapse** — equity fell from ~$22.63 (audit) to **$14.92** (LIVE log). At 0.01 lot and 20% risk, max stop ≈ **2.98** price units; live ATR/owner stops ~**5.07** → `MIN_LOT_INFEASIBLE` / `MIN_LOT_EXCEEDS_RISK_BUDGET`. Robot correctly refuses to upsize or bypass `OWNER_SL_RISK`.
4. **Attributed strategy sample insufficient** — `trend_continuation` attributed n=2, net −$3.55; most historical closes remain **unattributed** (explicitly marked as such in prior attribution work). Do not invent strategy blame for unattributed tickets.
5. **BUY bias in current LIVE cycle** — logs show repeated BUY candidates with quality ≥70 but Risk halt; not a fill problem today.

---

## 4. Five-strategy comparison (SOE telemetry + attribution)

From audit `soe_per_strategy` (scans≈9020 each window):

| Strategy | Eligible (approx) | Closed (attrib) | Net (attrib) | Guidance |
| --- | --- | --- | --- | --- |
| smc_scalping | 18 | 0 | — | More evidence; keep filters |
| trend_continuation | 18 | 2 | −3.55 | Technical/attribution repair; do not force volume |
| breakout_scalping | 18 | 0 | — | Evidence insufficient |
| range_mean_reversion | null / heavy reject | 0 | — | Remain inactive when regime unfit |
| momentum_scalping | 18 accepted (SOE) | 0 closed attrib | — | Dominant LIVE selector in logs; wait for fills + attribution |

**Do not** force diversification or increase activity. Optimize for expectancy after costs once capital allows min-lot geometry again.

---

## 5. PME verification (confirm / net BE / trail / reversal)

| Feature | LIVE intended | Status |
| --- | --- | --- |
| `require_broker_sl_confirm` | True | Wired (#160); confirm before local BE/TRAIL/RESTORE lock |
| `use_net_break_even` | True | Wired; geometric fallback when costs incomplete |
| Trailing | improve-only | Unchanged; SL improvement checks retained |
| Shadow reversal | True | Observe-only; now **durable + outcome mark** (this PR) |
| `live_reversal_exits_enabled` | **False** | **Remains False** — activation gates not met |

### Reversal shadow results

Prior book was **in-memory only** (lost on Railway restart). No durable BUY/SELL outcome corpus exists yet → **cannot** satisfy activation gates. This PR persists `pme_shadow_exits.json` and marks `broker_closed` when the live book confirms ticket absence. LIVE reversal stays off until real observations accumulate (both sides, costs, false-exit audit).

---

## 6. Entry-quality & risk rejection

LIVE cycle evidence (2026-11-05 ~15:10Z):

- Scanner: `momentum_scalping` BUY, quality 94 / conf 82, sniper passed, spread 0.374
- `owner_tp_level_selected` RR after spread 0.25–0.59 (≥ owner 0.20 floor)
- Risk: `needed_pct=33.91% > hard_max≈19.97%` → **OMS not attempted** (correct)
- Portfolio capital protection scale 0.55

Entry quality is often above floors; **geometry vs equity** is the binding constraint, not weak SOE scores.

---

## 7. Capital analysis (current equity $14.92)

Assumptions: owner max_lot **0.01**, risk ceiling **20%**, mandatory SL. From LIVE Risk message: `max_allowed_stop_at_min_lot ≈ 2.98` for this account state.

| Scenario | Equity | 20% $ risk | Feasible max stop (LIVE-implied) | Notes |
| --- | --- | --- | --- | --- |
| Current (observed) | 14.92 | ≈2.98 | ≈2.98 | ATR/owner stops ~5.07 → **not tradeable** |
| Conservative rebuild | ≥25–30 | ≥5–6 | allows ~5+ stops | Prefer before expecting fills |
| Moderate | ≥40 | ≥8 | room for costs + slippage | Still 0.01 lot only |
| Aggressive research | ≥50+ | ≥10 | still owner-capped lot | Do **not** raise lot/risk while expectancy negative |

**Monetary loss at 0.01 lot** scales with stop distance; historical avg loss ≈ **−$2.00** already large vs $14.92 equity (~13% per average SL). Consecutive-loss scenarios at that size are account-threatening under the locked policy — another reason Risk halt is correct.

**Recommendation:** do **not** increase lot or risk; do **not** bypass `OWNER_SL_RISK`. Capital top-up is an owner business decision, not an engineering bypass.

---

## 8. Improvements implemented (this cycle)

1. **Durable shadow reversal book** — disk persist + idempotent `mark_shadow_outcome`; summary helper for gate reporting.
2. **Wire `ai_momentum` / `ai_volatility`** into `PositionManageContext` from snapshot score factors so existing SCALP fade/collapse exits can fire when scores are present (previously always `None`).
3. **Adverse-session management** — include `london_ny_overlap` (and `asia`) in `weak_management_sessions` for earlier SCALP BE / tighter trail (soft management only; **owner YAML unchanged**).
4. **Tests** — `tests/unit/test_pme_shadow_durable_overlap.py` (+ existing confirm suite green).
5. **Report** — this document under `docs/production/reports/profitability/`.

**Not done (correctly):** LIVE reversal activation; lot/risk changes; forced trades; fabricated shadow outcomes.

---

## 9. Tests

```text
pytest tests/unit/test_pme_shadow_durable_overlap.py
pytest tests/unit/test_pme_broker_confirm_net_be.py
→ 22 passed
```

---

## 10. PRs / deploys

| Item | Ref |
| --- | --- |
| Prior PME LIVE confirm+net BE | #160 → `95d7a582` (Railway SUCCESS) |
| Prior docs | #161 → `a6b9ea57` |
| This profitability engineering PR | *(filled on merge)* |

Frontend Vercel: **not required** for this backend-only change.

---

## 11. Remaining limitations

- No local owner token → cannot refresh authenticated `/ops` portfolio JSON from this workstation.
- Shadow outcome corpus still empty until positions open and close under durable book.
- Most historical broker closes still **unattributed** by strategy.
- `history_deals_unavailable` intermittent warning on daily PnL path (fail-closed) — monitor.
- Gateway transient `ReadError` / EAGAIN on candles observed; reconnects logged; positions sync recovered.

---

## 12. Next evidence-based priorities

1. Keep robot running under owner policy; allow capital recovery / owner top-up before expecting LIVE fills.
2. Accumulate durable shadow reversal observations (BUY and SELL) with broker outcomes — **no LIVE activate** until gates pass.
3. After next attributed fills: refresh expectancy / PF / session tables; verify overlap earlier-BE effect without cutting winners.
4. Continue attribution idempotency on every broker-confirmed close.
5. Soft entry research (freshness / chase / RR geometry) as **documented proposals only** until out-of-sample evidence — never silently lower owner floors.

**Capital protection first. Evidence before activation. Broker-confirmed results before profitability claims.**
