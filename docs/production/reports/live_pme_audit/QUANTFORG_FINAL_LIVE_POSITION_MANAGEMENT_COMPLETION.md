# QuantForg — Final LIVE Position Management Completion

**Date:** 2026-11-05  
**Owner risk YAML:** **LOCKED / UNCHANGED**  
**Instrument:** XAUUSD · Weltrade-Real · magic `260720`

---

## A. PR #159 merge evidence

| Item | Evidence |
|---|---|
| PR | https://github.com/QuantForg1/QuantForg/pull/159 — **MERGED** |
| Merge commit | `e204a197` |
| CI | All required checks SUCCESS |
| Content | Docs: Railway `e4807872` verification for #158 |

---

## B. PRs created and merged (this program)

| PR | Purpose | Production |
|---|---|---|
| #157 | Class-aware BE recovery + audit | Railway `75db8c3d` / `98f173a` |
| #158 | Gated confirm/net-BE/session honesty (defaults OFF then) | Railway `e4807872` / `56c777a` |
| #159 | Docs deploy evidence for #158 | Docs on main `e204a197` |
| #160 (this) | **Activate** broker SL confirm + net BE; shadow reversal; contract_size | Pending CI → merge → Railway |

---

## C. Broker SL confirmation

| Item | Status |
|---|---|
| Flag | **`require_broker_sl_confirm=True`** (DEFAULT + scalping PME replace) |
| Reader | `Mt5BrokerPositionReader` attached at ITE runtime bootstrap |
| Path | BE / TRAIL / RESTORE_STOP after OMS ok → re-read → confirm before local lock |
| Failure | `BROKER_CONFIRM_FAILURE`; no fingerprint; retry next cycle |
| Tests | BUY/SELL/timeout/worse-SL/legacy-off |

**LIVE activated** after unit evidence. No real-money test orders.

---

## D. Net Break-Even

| Item | Status |
|---|---|
| Flag | **`use_net_break_even=True`** |
| Incomplete costs | Falls back to geometric BE; never invents fees |
| Context | `open_commission`, `open_swap`, `contract_size` (XAU specs / broker) |
| Class offsets | SCALP 0.35R / HOLD 0.30R / UNKNOWN 0.2R unchanged |

**LIVE activated** with safe geometric fallback.

---

## E. Reversal / AI exit

| Item | Status |
|---|---|
| Shadow | **`shadow_reversal_exits_enabled=True`** — logs + `shadow_exit_book` |
| LIVE feed | **`live_reversal_exits_enabled=False`** |
| Reason LIVE off | No multi-day shadow observation corpus yet; owner forbade fabricating a shadow period |
| Design | `PHASE_D_REVERSAL_EXIT_DESIGN.md` + `exit_context.propose_reversal_exit` |

**Shadow-only in production** until owner reviews shadow logs vs broker outcomes.

---

## F. Session and news

| Item | Status |
|---|---|
| Honest `market_open` | From account/snapshot when known |
| `session_flatten_on_market_closed` | **False** — not enabled (quote gaps ≠ liquidation) |
| News LIVE exits | Still unwired (no verified feed → never invent “no news”) |

---

## G. Partial TP at 0.01

Verified: volume 0 → `ManageOutcome.SKIPPED`, no OMS call, volume unchanged, lifecycle advances for trail. Limitation: true scale-out impossible at single min lot.

---

## H. Broker attribution

Existing #153 pipeline retained. Unattributed closes remain explicitly unattributed (`pending_history` / no invention). Shadow/exit books do not invent strategy IDs.

---

## I. Five-strategy performance

Fresh authenticated broker re-fetch was not always available in local shells. Prior verified sample (do not treat as current equity without re-read):

- n=29, PF 0.68, expectancy −$0.33, net −$9.61  
- Attributed strategy closes remain sparse (n=2 TC)

**Recommendation:** keep owner floors; do not raise lot/risk/concurrent while PF&lt;1.

---

## J. Capital and risk recommendations (only)

| Scenario | Action |
|---|---|
| Conservative | Keep YAML; confirm+net BE ON; shadow exits; session flatten OFF |
| Moderate | After shadow review, consider `live_reversal_exits_enabled=True` |
| Aggressive research | Soft SOE Scenario B — **not** applied |

---

## K. Test results (activation branch)

```
pytest test_pme_broker_confirm_net_be + phase_d + trading_core_regression → 48 passed
focused planned-risk PME guards → 23 passed (selected)
ruff → clean on touched modules
```

---

## L–M. Deploy / health (fill after #160 merge)

| Deploy | ID |
|---|---|
| Prior #158 | `e4807872` SUCCESS; `/health` `/ready` 200 |
| This activation | *pending merge* |

---

## N. Owner YAML comparison

No changes to owner max_lot, risk %, RR floors, quality, concurrent, daily halt, aggregate, mandatory SL, grid/martingale/averaging, or M1 LIVE flags in this program.

---

## O. Remaining limitations

1. LIVE reversal exits await real shadow corpus.  
2. Session flatten disabled by design.  
3. News exits unwired.  
4. Partial TP impossible at 0.01 single lot.  
5. Strategy attribution coverage still incomplete historically.

### Scorecard

| Bucket | Items |
|---|---|
| Implemented and production verified | #157–#159 |
| LIVE activated (this PR) | Broker SL confirm; net BE |
| Shadow-only | Reversal proposals |
| Disabled intentionally | Session flatten; LIVE reversal feed |
| Recommendations only | SOE Scenario B; capital scenarios |
| Still missing | Multi-day shadow validation report; news feed |
