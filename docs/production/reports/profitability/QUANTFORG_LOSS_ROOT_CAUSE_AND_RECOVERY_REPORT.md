# QuantForg — Loss Root-Cause Investigation & LIVE Quality Recovery

**Generated:** 2026-11-05T18:30:00Z  
**Instrument:** XAUUSD / Weltrade-Real (login 12260878)  
**Broker sample:** `docs/production/reports/profitability/loss_audit_broker_history.json`  
**Owner policy:** **unchanged** (max_lot 0.01, risk 20%, RR floor 0.20 / preferred 0.50, Q≥70, concurrent 1, daily halt 48%, aggregate 30%, mandatory SL, no grid/martingale/averaging, M1 LIVE off)

**Verdict:** Broker-authoritative sample shows **negative expectancy** (n=46, net **−$29.94**, PF **0.50**). Primary monetary driver is **asymmetric SL vs TP geometry** plus a **heavy BUY bias into losers**. Deferred attribution / `STALE_RISK` / logging defects are fixed in code. Geometry now prefers a second structure TP when it clears preferred RR **0.50** without raising the hard floor. **No profitability claim** — improvements are verified in unit tests; LIVE confirmation still required.

---

## 1. Broker-authoritative baseline (Phase 1)

| Item | Value |
| --- | --- |
| Balance / equity | **$18.30 / $18.30** |
| Floating P/L | **$0.00** |
| Open positions | **0** (no SL/TP open) |
| Closed positions (sample) | **46** (magic 260720) |
| Deposits (separated) | +$19 + $13 + $16 = **+$48.00** (not trading P/L) |
| Commission / swap (sample) | **$0.00 / $0.00** |
| Period | Broker history window used by gateway deals_7 ≈ deals_30 (same 46 closes in dump) |
| Missing data | Per-strategy SOE books incomplete historically (`strategy_id=None` on many closes); session clocks on raw deal times not remapped to named sessions in this dump — side/TP/SL used instead of invented sessions |

### Performance metrics (closed trades only)

| Metric | Value |
| --- | --- |
| Wins / losses | 20 / 26 |
| Win rate | **43.5%** |
| Gross profit / gross loss | +$30.53 / −$60.47 |
| **Net trading P/L** | **−$29.94** |
| Profit factor | **0.50** |
| Avg winner / avg loser | +$1.53 / −$2.33 |
| Expectancy / trade | **−$0.65** |
| Max consecutive losses | **5** |
| Avg holding time | **~232 s** |
| TP outcomes | 20 closes, **+$30.53** |
| SL outcomes | 26 closes, **−$60.47** |
| Implied avg TP distance / avg SL distance | ~1.52 / ~2.20 → ~**0.69R** if stops were equal |
| Costs % of gross profit | ~0% in this sample (commission/swap 0) |

### Side split (authoritative)

| Side | n | Net |
| --- | --- | --- |
| BUY | 34 | **−$28.12** |
| SELL | 12 | −$1.82 |

Almost all trading loss dollars are on **BUY** fills.

---

## 2. Exact causes of losses (ranked by impact)

1. **Asymmetric reward vs risk at the broker (highest $)** — SL bucket −$60.47 vs TP +$30.53; avg loss 1.52× avg win. Operator geometry often selected nearest structure TP clearing only the **0.20** floor (~0.39–0.47R) while SL realized ~1.0–1.1R. Break-even expectancy at 43.5% WR would need avg win ≳ avg loss.
2. **BUY-dominant fill stream** — 34 BUY vs 12 SELL; BUY net −$28.12. Consistent with cascade BUYs into declining/chop marks in the deep-audit window (not invented news).
3. **Capital erosion → tighter geometry** — Equity $18.30 after deposits $48 and trading −$29.94. At 20% risk / 0.01 lot, max stop ≈ **3.66**; wider ATR stops still correctly blocked, but approved trades remain small-RR / full-SL.
4. **Attribution black hole (analytics, not direct $)** — Closes logged `strategy_id=None`, `soe_recorded=False`, so strategy P&amp;L books could not steer selection. Root: PME path marked the close ledger and cleared bindings **without** a resolved `strategy_id`, racing the broker reconcile path; live fill meta was also ignored after `[sl]`/`[tp]` comment overwrite.
5. **Occasional `STALE_RISK` same-cycle abort** — Risk stamp reused market `as_of` while `force_sync_positions` consumed wall time → 8s freshness race. Missed/deferred fills only; did **not** create the dollar asymmetry.
6. **Misleading `high_quality=False` / `safety_blocked_manage`** — Telemetry/logging defects; management still ran; quality 76 could fail `high_quality` when confidence lagged.

**Not claimed without evidence:** news blackouts, specific five-pack strategy death sentences for unattributed history, LIVE reversal benefit.

---

## 3. Strategy / session / regime (limits)

| Area | Finding |
| --- | --- |
| Five strategies | Historical closes largely **unattributed** in SOE books — cannot invent per-strategy PF from broker comments alone except engine tags (`m1:` / `ite:`). Repair restores future attribution; past tickets without fill evidence stay unmarked. |
| Sessions | Prior smaller audit flagged **london_ny_overlap** as worst session net; this 46-trade dump was not re-bucketed by UTC session without a verified time map. Do not invent session labels. |
| Regime | BUY cascade + short holds (~4 min) into SL is consistent with trend-fade / chop entries; structure TP too near entry relative to stop. |

---

## 4. Execution & position management

| Topic | Status |
| --- | --- |
| Broker fills | Operational (`10009`); pipeline proven in deep audit |
| Spread / commission | Spread soft-scored; commission 0 in sample |
| PME | BE/trail/confirm/net-BE already LIVE; reversal remains **shadow-only** |
| Partial TP @ 0.01 | Unchanged — not enabled as loss chase |
| Open positions | None at report time — none modified |

---

## 5. Defects fixed (Phase 3)

| Defect | Fix |
| --- | --- |
| `strategy_id=None` / `soe_recorded=False` | PME no longer marks ledger or clears bindings without `strategy_id`; `merge_position_metadata` keeps fill-time strategy when ticket matches despite `[sl]`/`[tp]`; entry-comment engine tags (`m1:`/`ite:`) used on broker reconcile |
| `STALE_RISK` race | After account sync, refresh `risk_as_of` / `safety_as_of` to now — **max age still 8s** |
| `high_quality` vs quality 76 | `high_quality` follows owner Q70 on **quality**; confidence no longer vetoes a passing quality |
| `safety_blocked_manage` | Renamed `entry_safety_blocked_position_manage` + note that management continues |

---

## 6. Evidence-based profitability change (Phase 4)

**Change:** `select_owner_structure_tp` — among levels that clear the hard floor (0.20), prefer the nearest level that also clears **preferred RR 0.50** when present within `OWNER_TP_MAX_STRUCTURE_LEVELS` (2). Floor unchanged; no lot/risk/Q changes.

| | |
| --- | --- |
| Observed defect | Nearest TP often ~0.2–0.4R while SL ~1R → PF 0.50 |
| Evidence | Broker n=46; avg win $1.53 vs avg loss $2.33; prior operator RR alerts |
| Expected effect | Larger TP when second structure level is valid → better avg win / PF **if** L2 is reachable before SL |
| Side effects | Slightly longer path to TP may reduce WR on some setups; may reject fewer geometries than raising the hard floor |
| Test | Unit: prefers L2 at 0.60 when L1 is 0.25; keeps L1 when L2 is 0.40 &lt; preferred |

**Not done:** raise min RR, raise lot, enable LIVE reversal, force trades, fabricate strategy P&amp;L for unknown tickets.

---

## 7. Backtest / OOS (Phase 5)

| Item | Result |
| --- | --- |
| Broker baseline reproduced | Yes — n=46, net −$29.94, PF 0.50 |
| Bar-level chronological OOS of TP preference | **Not available** in this pass (no leakage-safe multi-month bar replay wired to owner TP selector here) |
| Unit geometry / attribution / stale / quality | **64 passed** (`--no-cov` focused suite) |
| Statistical power | Small LIVE sample — treat preferred-TP change as **limited evidence**, confirm on next LIVE closes |

Reject “win-rate only” tuning — change targets expectancy via RR geometry.

---

## 8. Owner policy confirmation (Phase 6)

YAML floors **unchanged**. `OWNER_PREFERRED_REWARD_RISK = 0.50` is the documented soft target already in runtime policy text; hard floor remains **0.20**.

---

## 9. Tests (Phase 7)

```
64 passed — close_attribution, attribution_store, owner_sl15_tp2,
            signal_lifecycle, live_scalping_continuity, phase6_strategy_intelligence
```

Ruff clean on touched modules after format/import fix.

---

## 10. Deployment (Phase 8)

| Item | Evidence |
| --- | --- |
| Git | `c4426f47` on `main` — PR [#166](https://github.com/QuantForg1/QuantForg/pull/166) squash-merged |
| CI | Lint, Type Check, Unit Tests, Trading Core Regression, Frontend, Integration — **pass** |
| Railway | Deployment `55889b8c` **SUCCESS** · service QuantForg · commit **c4426f4** · env production |
| `/health` | `{"status":"ok"}` |
| `/ready` | `{"status":"ok","detail":"routers_registered",...}` |
| Owner floors | Unchanged in release (hard RR 0.20, Q70, max_lot 0.01, …) |

---

## 11. Remaining risks / unresolved

- Equity **$18.30** — min-lot geometry still tight; further SL streaks hurt tradeability.
- Preferred-TP may not fire when only one structure level clears 0.20.
- Historical strategy P&amp;L for tickets without fill evidence remains unknown.
- LIVE reversal still off pending more evidence.
- Need more LIVE closes after deploy to validate expectancy lift.

---

## 12. Distinction of claims

| Class | Items |
| --- | --- |
| Verified | Broker baseline; attribution race; STALE_RISK stamp race; high_quality mismatch; manage log label; unit tests green |
| Limited evidence | Preferred structure TP → better expectancy |
| Needs more LIVE observation | Post-deploy PF/expectancy; session-tagged strategy books; whether BUY bias abates |
