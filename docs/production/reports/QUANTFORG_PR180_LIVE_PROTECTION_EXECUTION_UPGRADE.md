# QUANTFORG PR #180 — LIVE Protection & Intelligent Trading Upgrade

**Date:** 2026-11-06  
**Baseline before this PR:** PR #179 / `944d5c0a`  
**Instrument:** XAUUSD  
**Principle:** Keep authorized LIVE trading operational. Strengthen protection. Do not convert the desk to shadow-only.

---

## 1. Existing LIVE behavior (pre-change audit)

| Item | Status at audit |
| --- | --- |
| Auto-trading | Enabled / running (saved ops evidence; public `/health` ok) |
| Execution | LIVE path authorized; OMS orders allowed when gates pass |
| Owner risk | 20% per trade, 48% daily halt, 0.01 lot, Q≥70, RR 0.20/0.50, concurrent 1 |
| BUY cascade | Durable Postgres anchors; blocks unresolved BUY decline |
| PME | BE / partial / trail / mandatory broker SL confirm |
| Shadow reversal | Side-aware observation from PR #179 |
| LIVE reversal close | **Off** (`live_reversal_exits_enabled=False`) |
| M1 evaluation | **Off** unless env set |
| M1 LIVE submit | **Off** (requires second flag) |
| Reverse entry | Not activated |

Public probes at audit: `/health` and `/ready` returned ok. `/health` did not yet expose commit SHA (added in this PR). Exact Railway SHA must be read from `/health.commit` after deploy.

---

## 2. Reversal protection changes

### LIVE close-on-confirmed-reversal (activated by default)

- `PositionManagementConfig.live_reversal_exits_enabled` default → **True**
- Kill-switch: `QUANTFORG_LIVE_REVERSAL_EXITS=false`
- LIVE planner is fed `structure_broken` / `trend_reversed` **only** when:
  - classification ∈ `{confirmed_structure_reversal, htf_trend_reversal}`
  - `structure_broken` is True (HTF-agreed opposite BOS/CHOCH)
  - market data not stale
  - reverse-close dedup allows the ticket (90s)
- PME existing path issues `EMERGENCY_EXIT` → existing OMS close → broker confirm
- Temporary M1 pullback / false LTF noise **never** close LIVE
- AI-fade-only classifications do **not** feed LIVE close
- **Reverse-entry remains forced off** (`live_reverse_entry_enabled=False`)

### Dedup

`reversal_close_dedup` blocks repeated close requests for the same ticket within cooldown.

---

## 3. M1 strategy status

| Capability | Status after PR #180 |
| --- | --- |
| Pipeline evaluation (`m1_micro_enabled`) | **Default ON** (unset env = evaluate) |
| Unified arbitration (`resolve_unified`) | Active when evaluation on — conflict → wait |
| LIVE order submit (`m1_live_submit_enabled`) | **Default OFF** — needs `QUANTFORG_M1_MICRO_LIVE_SUBMIT=true` |
| Stop / cost / RR checks in module | Present in `m1_micro` |
| Duplicate-order prevention | Via unified owner + OMS |
| Costed shadow expectancy on Weltrade | **Not proven** → submit stays off |

**Why submit is not LIVE yet:** entry/exit logic and stops exist, but production does not have verified costed expectancy / OOS evidence for M1 live fills. Integration = evaluation + arbitration inside LIVE cycles; unsafe independent OMS bypass is prevented.

Explicit disable: `QUANTFORG_M1_MICRO_SCALPING=false` or policy `m1_micro_enabled=false`.

---

## 4. Strategy coordination

Unchanged contract, now exercised more often because M1 evaluates by default:

1. Collect primary + M1 signals  
2. Opposite sides → wait (no fight, no hedge)  
3. Same side → one owner  
4. No quality/opportunity score inflation  
5. Q70 / Risk / OMS unchanged  

---

## 5. Loss protection improvements

| Protection | Change |
| --- | --- |
| BUY cascade | Unchanged (kept) |
| SELL cascade | **New** — file-backed anchors; blocks higher SELL after losing SELL until reclaim or bearish M1/M5 structure; does not block BUY |
| Consecutive losses / daily halt | Unchanged |
| Reversal close dedup | **New** |
| Stale / spread / missing SL | Existing PME paths retained |
| Risk breach | Continues to block new entries; management of open positions continues |

---

## 6. Test results (local)

```
tests/unit/test_pr180_live_protection.py
tests/unit/test_reversal_intelligence.py
tests/unit/test_m1_micro_scalping.py
tests/unit/test_unified_decision.py
tests/unit/test_pme_broker_confirm_net_be.py
```

(Executed in CI for the PR; local run before push.)

---

## 7. Production feature flags (intended after deploy)

| Flag / config | Intended value | Effect |
| --- | --- | --- |
| LIVE trading / execution | Unchanged (keep on) | Desk stays LIVE |
| `live_reversal_exits_enabled` | True (unless env false) | Close on confirmed reversal |
| `QUANTFORG_LIVE_REVERSAL_EXITS` | unset or true | Kill-switch available |
| `QUANTFORG_M1_MICRO_SCALPING` | unset → evaluate on | Arbitration |
| `QUANTFORG_M1_MICRO_LIVE_SUBMIT` | unset/false | **No M1 OMS submit** |
| Reverse entry | Off | Never open opposite before broker-confirmed close + separate approval |
| Risk 20% / halt 48% / lot 0.01 / Q70 | Unchanged | Owner policy |

---

## 8. Verified deployment commit

Fill after merge + Railway recycle:

| Check | Value |
| --- | --- |
| GitHub `main` HEAD | _(post-merge SHA)_ |
| `GET /health` → `commit` | _(must match)_ |
| `/ready` | ok |
| CI | green on PR |

Do not claim deploy success without matching `/health.commit`.

---

## 9. Remaining risks

1. Confirmed-reversal closes can realize losses earlier — intentional protection, not profit guarantee.  
2. M1 evaluation conflicts may reduce primary entries (wait) — protective, monitor frequency.  
3. SELL cascade is file-backed (not Postgres); lose volume → anchors reset → fail open.  
4. Structure map gaps → fewer LIVE closes (fail quiet).  
5. M1 LIVE submit still needs expectancy evidence before env enable.

---

## 10. Genuinely LIVE vs not yet LIVE

| Feature | LIVE after this deploy? |
| --- | --- |
| Existing scalping / ITE / OMS entries | **Yes** (unchanged authorization) |
| Close on confirmed structural reversal | **Yes** (default on; kill-switch available) |
| Reverse entry after close | **No** |
| M1 evaluation + unified arbitration | **Yes** (default on) |
| M1 independent / complement OMS submit | **No** |
| BUY cascade | **Yes** |
| SELL cascade | **Yes** (new; file store) |
| Risk / lot / Q / RR owner limits | **Yes** (unchanged) |

---

## Owner policy confirmation

Risk 20% · Daily halt 48% · Max lot 0.01 · Q≥70 · Min RR 0.20 · Preferred 0.50 · Concurrent 1 · Aggregate 30% · Mandatory broker SL · No grid/martingale/averaging — **not modified**.
