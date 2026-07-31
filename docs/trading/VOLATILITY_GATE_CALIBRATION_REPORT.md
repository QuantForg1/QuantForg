# Volatility Gate Calibration Report

**Investigation type:** Observe-only — no threshold, strategy, or code changes  
**Generated at:** 2026-07-31T20:05:00Z  
**Symbol:** XAUUSD (Weltrade-Real via `gateway.quantforg.com`)  
**Related:** [`FINAL_EXECUTION_TRACE_REPORT.md`](./FINAL_EXECUTION_TRACE_REPORT.md)  
**Raw stats:** `docs/trading/_vol_gate_calibration_stats.json`

---

## Gate under study (unchanged)

| Parameter | Value |
|---|---|
| Check | AI Scalping `valid_volatility` |
| Band rule | `low` when `atr_pct ≤ atr_low_pct` (**0.40**) |
| Compression reject | when band=`low` **and** `atr_pct < atr_low_pct / 2` → **&lt; 0.20%** |
| Formula | `atr_pct = ATR(14) / mid × 100` |
| Code | `ai_scalping/quality_gates.py` + `adaptive_thresholds.py` |

**Observed production ATR input:** live cycle ATR **5.1357** / mid ~4050 → **ATR% ≈ 0.13%**.  
Recomputed live gateway bars: **M15 ATR(14) ≈ 5.3** matches; **M5 ATR(14) ≈ 2.5** does not.  
Primary calibration below therefore uses **M15 ATR%** (the series that matches the live gate). M5 is reported as a sensitivity check only (scalping config labels entry TF as M5, but the live ATR magnitude matches M15).

---

## Data window

| Series | Bars (ATR samples) | Span | Notes |
|---|---|---|---|
| **M15 (primary)** | 2,020 | **30.11 days** (2026-07-01 → 2026-07-31) | Full 30d within gateway `count≤5000` |
| M5 (sensitivity) | 4,999 | **24.11 days** (2026-07-07 → 2026-07-31) | Gateway max depth; not full 30d |
| H1 (reference) | 505 | 30.08 days | Not used by this gate |

Method: True Range → simple average last 14 TRs (same as `compute_atr`) → `atr_pct = atr / close × 100`.

---

## 1. Distribution of ATR% (M15, last 30 days)

| Statistic | ATR% |
|---|---|
| Mean | **0.1905** |
| Median | **0.1777** |
| Min | 0.0720 |
| Max | 0.5476 |
| P10 | 0.1240 |
| P25 | 0.1435 |
| P50 | 0.1777 |
| P75 | 0.2226 |
| P90 | 0.2737 |
| P95 | 0.3143 |

Volatility band occupancy (vs `atr_low_pct=0.40` / `atr_high_pct=1.50`):

| Band | Share of bars |
|---|---|
| `low` (≤0.40) | **98.47%** |
| `normal` | 1.53% |
| `high` | 0.00% |

Almost every bar is classified **low**, so the **0.20% compression floor** is the operative allow/deny switch.

---

## 2. Percentage of time in requested ATR% buckets (M15, 30d)

| Bucket | Count | % of time |
|---|---|---|
| **&lt; 0.10** | 52 | **2.57%** |
| **0.10 – 0.15** | 549 | **27.18%** |
| **0.15 – 0.20** | 700 | **34.65%** |
| **0.20 – 0.30** | 587 | **29.06%** |
| **&gt; 0.30** | 132 | **6.53%** |

**~64.4%** of M15 bars sit **below** 0.20% (sum of first three buckets).

### Sensitivity — M5 ATR% (available ~24d, not production-matched)

| Bucket | % of time |
|---|---|
| &lt; 0.10 | 54.35% |
| 0.10 – 0.15 | 32.57% |
| 0.15 – 0.20 | 9.20% |
| 0.20 – 0.30 | 3.44% |
| &gt; 0.30 | 0.44% |

M5 median ATR% = **0.096** — even more compressed; included only to show scale difference.

---

## 3. How often would the current 0.20% threshold allow trading?

Compression gate passes iff `atr_pct ≥ 0.20`.

| Timeframe | Allow (`ATR% ≥ 0.20`) | Block (`ATR% &lt; 0.20`) |
|---|---|---|
| **M15 (matches live ATR)** | **35.59%** | **64.41%** |
| M5 (sensitivity) | 3.88% | 96.12% |
| H1 (reference only) | 100.00% | 0.00% |

On the series that matches production’s live ATR, the gate **blocks roughly 2 of every 3 bars**.

Latest M15 sample at analysis time: ATR% ≈ **0.131** (would **FAIL**, consistent with [`FINAL_EXECUTION_TRACE_REPORT.md`](./FINAL_EXECUTION_TRACE_REPORT.md)).

---

## 4. Comparison with historical profitable trades (if available)

Source: gateway `GET /history/deals?days=30`, XAUUSD deals FIFO-paired (entry=0 → entry=1). ATR% = M15 ATR(14) at **entry** time.

| Metric | Value |
|---|---|
| Closed XAUUSD trades (30d) | **19** |
| Excluding micro cert/send/close tests | **13** |
| Non-micro net P/L | **+$180.83** |
| Non-micro winners | **10** |
| Mean ATR% on non-micro winners | **≈ 0.187** |

### Non-micro winners vs 0.20% gate

| Outcome vs gate | Count | Notes |
|---|---|---|
| Would **PASS** (`ATR% ≥ 0.20`) | **2 / 10** | ATR% 0.2056, 0.3454 |
| Would **FAIL** (`ATR% &lt; 0.20`) | **8 / 10** | Mostly **0.15–0.20** (0.150–0.171) |

Bucket mix for non-micro winners:

| Bucket | Winners |
|---|---|
| 0.15 – 0.20 | **8** (all would fail current gate) |
| 0.20 – 0.30 | 1 |
| &gt; 0.30 | 1 |

**Caveat (evidence integrity):** several fills are `FORCE:…`, `e2e-controlled-b`, or blank-comment holds — **not** AI quality-gate–approved natural signals. They prove only that **realized profitable XAUUSD exposure occurred while M15 ATR% was often below 0.20**, not that the AI strategy edge peaks there.

No separate labeled “AI-approved live winners” sample exists in the last 30 days (robot path has been largely `NO_TRADE`).

---

## 5. Recommendation (evidence only — no change applied)

**Verdict: too conservative** for XAUUSD under the ATR series that matches the live gate (M15 ATR%).

Evidence:

1. **Market distribution:** median M15 ATR% = **0.178** &lt; 0.20; **64%** of the last 30 days fails the floor.  
2. **Operational impact:** current live blocker (`ATR% ≈ 0.13`) sits in the **modal** region of recent gold volatility (0.10–0.20), not an extreme dead-market tail.  
3. **Trade history (limited):** **8 of 10** non-micro profitable closes in the last 30d entered with ATR% **below** 0.20 — concentrated in **0.15–0.20**.  
4. **Band design:** `atr_low_pct=0.40` puts **~98%** of M15 bars in `low`, so the half-floor **0.20** dominates allow-rate; it is not a rare “dead tape” filter on this instrument/TF.

**Not “too aggressive”:** the floor already excludes the majority of recent bars; there is no evidence it is letting through extreme low-vol noise relative to XAUUSD’s own 30d distribution.

**Not “appropriate” as a typical-condition filter:** a threshold above the median of the instrument’s own ATR% distribution will systematically starve execution even when ITE quality/confidence/MTF already pass.

This report does **not** recommend a new number, does **not** lower thresholds, and does **not** modify strategy — calibration evidence only.

---

## Conclusion

**0.20% compression floor is too conservative for live XAUUSD M15 ATR% (allows ~36% of bars; most recent profitable fills and the live NO_TRADE ATR sit below it).**
