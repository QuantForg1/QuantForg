# QuantForg — Capital Verification & Min-Lot Resume

**Generated:** 2026-11-05T16:20:00Z  
**Authority:** MT5 Gateway `https://gateway.quantforg.com` (Weltrade-Real) + Railway LIVE logs  
**Owner policy:** unchanged (max_lot 0.01, risk 20%, RR≥0.20, Q≥70, concurrent 1, …)

**Verdict:** Broker confirms **+$16.00** capital (equity **$30.92**). The prior **`MIN_LOT_INFEASIBLE`** rejection for typical ATR stops (~5.065) is **resolved**. LIVE continues under owner floors; current cycles reject on **`OWNER_MIN_TRADE_QUALITY` (68&lt;70)** — not capital. No forced entries.

---

## 1. Broker-confirmed capital

| Field | Value | Source |
| --- | --- | --- |
| Login | 12260878 | `GET /account` |
| Server | Weltrade-Real | `/account` |
| Currency | USD | `/account` |
| **Balance** | **30.92** | `/account` (also Railway cycle logs) |
| **Equity** | **30.92** | `/account` |
| Margin used | 0.0 | `/account` |
| Free margin | 30.92 | `/account` |
| Floating profit | 0.0 | `/account` |
| Leverage | 1000 | `/account` |
| Trade allowed | true | `/account` + `/session/status` |
| MT5 AutoTrading | true | `/session/status` health |
| Session | connected, not degraded | `/session/status` |
| Open positions | **0** | `/positions` → `items: []` |

### Deposit evidence

| Prior LIVE equity (2026-11-05 ~15:10Z logs) | Current broker equity | Delta |
| --- | --- | --- |
| 14.92 | 30.92 | **+16.00** |

Local `GET /history/deals` returned HTTP 403 with the workstation gateway token; deposit is evidenced by **live `/account` balance change** corroborated by production Railway `/account` previews showing `balance":"30.92"`. No assumed deposit amount was used.

---

## 2. XAUUSD broker specifications (live)

| Spec | Value |
| --- | --- |
| volume_min / step | 0.01 / 0.01 |
| volume_max | 1000 |
| contract_size | 100.0 |
| tick_size / tick_value | 0.001 / 0.1 |
| stops_level / freeze_level | 0 / 0 |
| Bid / Ask (sample) | ~4102.9 / ~4103.3 |
| Spread (sample) | **0.344** |
| Market open | true |
| Trade mode | full |

Approximate margin at 0.01 lot ≈ `price × CS × lot / leverage` ≈ 4100×100×0.01/1000 ≈ **$4.10** ≪ free margin $30.92 → margin feasible.

Rough one-way spread cost at 0.01 lot ≈ `0.344 × 0.01 × 100` ≈ **$0.34** (commission/swap not asserted without deal access).

---

## 3. Min-lot geometry reassessment (owner 20%)

Using production `evaluate_min_lot_feasibility` / tick path:

| Metric | At equity 14.92 (prior) | At equity **30.92** (now) |
| --- | --- | --- |
| Max monetary risk (20%) | ≈ $2.98 | **$6.18** |
| Max allowed stop @ 0.01 lot | ≈ 2.98 | **6.184** |
| Stop 5.065 needed % | ≈ 33.9% → **INFEASIBLE** | **16.36% → FEASIBLE** |

### 0.01 lot dollar risk vs equity 30.92

| Stop distance | $ risk | Needed % of equity | Classification |
| --- | --- | --- | --- |
| 2.0 | 2.00 | 6.47% | FEASIBLE |
| 3.0 | 3.00 | 9.70% | FEASIBLE |
| 4.0 | 4.00 | 12.94% | FEASIBLE |
| **5.065** (prior blocker) | **5.06** | **16.36%** | **FEASIBLE** |
| 5.5 | 5.50 | 17.79% | FEASIBLE |
| 6.0 | 6.00 | 19.40% | FEASIBLE |
| 6.184 | 6.18 | 19.99% | boundary / INFEASIBLE |
| 7.0 | 7.00 | 22.64% | MIN_LOT_INFEASIBLE |
| 10.0 | 10.00 | 32.34% | MIN_LOT_INFEASIBLE |

**Conclusion:** Qualified XAUUSD opportunities with stops **≤ ~6.0** can pass the min-lot Risk pre-gate without changing owner policy. Stops **>~6.18** remain correctly rejected via `MIN_LOT_INFEASIBLE` / `OWNER_SL_RISK` — do not bypass.

Artifact: `docs/production/reports/profitability/capital_geometry_probe.json`

---

## 4. LIVE safety / ops status

| Check | Status |
| --- | --- |
| Backend `/health` `/ready` | 200 OK |
| Railway deploy | `1fdef8ea` SUCCESS (`3c8bd4f`) |
| Mode | **LIVE**, `execution_enabled=True`, `run_state=running` |
| Worker / scheduler | Scheduler Tick continuing |
| Gateway | Connected after transient Cloudflare **530** (~16:11Z); recovered (`network_incident_recovered`) |
| Kill switch | Not armed in sampled cycles |
| Open positions | 0 — none modified |
| Risk / OMS | Active; OMS not forced |
| PME confirm / net BE | Remain LIVE-enabled from #160 |
| Shadow reversal | Remains observe-only (`live_reversal_exits_enabled=False`) |

### Transient blockers (post-deposit)

1. Gateway tunnel **HTTP 530** (~16:11Z) → temporary `MT5 gateway session not connected` / fail-closed — **recovered**.  
2. Occasional `SAFETY_BLOCKED: Daily P/L unavailable — verifying` when deal history lag — fail-closed, correct.  
3. Steady-state after recovery: **`OWNER_MIN_TRADE_QUALITY: trade quality 68 < 70`** — owner floor working; **not** a capital issue.

No operational controls were changed. No test orders. No position interference.

---

## 5. Strategy eligibility (geometry vs filters)

All five strategies share the same owner lot/risk geometry. At equity $30.92:

| Strategy | Min-lot geometry for stops ≤~6.0 | Notes |
| --- | --- | --- |
| smc_scalping | Eligible if signal + Q/RR pass | No filter loosening |
| trend_continuation | Same | Prior attributed losses ≠ capital issue |
| breakout_scalping | Same | |
| range_mean_reversion | Same when regime allows | May stay inactive if SOE rejects |
| momentum_scalping | Same | Dominant LIVE selector historically |

**Prior rejections:** capital-driven `MIN_LOT_INFEASIBLE` at $14.92 for stop~5.065 — **cleared**.  
**Current rejections:** quality &lt; 70 (and occasional safety/history fail-closed) — **keep**.

Do not manufacture activity by lowering Q/RR.

---

## 6. Resume posture

| Question | Answer |
| --- | --- |
| Is additional capital reflected on broker? | **Yes** — equity/balance 30.92 (+16.00 vs 14.92) |
| Is prior MIN_LOT_INFEASIBLE still valid for stop~5.065? | **No** — now FEASIBLE (~16.4% &lt; 20%) |
| Can qualified entries execute under owner policy? | **Yes**, when Q≥70, RR≥0.20, stop≤~6.0, Risk/OMS/broker OK |
| Should we force a trade? | **No** |
| Claim profitability from deposit? | **No** |

Robot already in LIVE scan/execute path; owner-authorized resume means **continue** — no mode flip required.

---

## 7. Remaining limitations / monitors

- Deal-history endpoint 403 from this workstation token — deposit evidenced via `/account` + prod logs.  
- Very wide stops (&gt;~6.18) still correctly capital-bound at 0.01 lot.  
- Expectancy remains **negative** on the prior n=29 sample; deposit does not reset that.  
- Watch gateway stability (530 blips) and daily-PnL fail-closed flaps.  
- Continue shadow reversal accumulation before any LIVE reversal activation.

**Capital protection first. Evidence before activation. Broker-confirmed results before profitability claims.**
