# QuantForg PME Follow-up — PR #157 Deploy + Gap Closure Report

**Date:** 2026-11-05  
**Owner policy:** **UNCHANGED**  
**Instrument:** XAUUSD / Weltrade-Real

---

## A. PR #157 merge and deployment evidence

| Item | Evidence |
|---|---|
| PR | https://github.com/QuantForg1/QuantForg/pull/157 — **MERGED** |
| Merge commit | `98f173aab3ad07a462243980ed611b7510c79b9e` |
| CI | Design Governance, Lint, Type Check, Unit, Trading Core, Frontend, Integration — **SUCCESS** |
| Railway deployment | `75db8c3d-1316-4ef3-bf19-2e89e28c72e2` — **SUCCESS** (commit `98f173a`) |
| `/health` | HTTP 200 `{"status":"ok"}` |
| `/ready` | HTTP 200 routers complete (100 registered) |
| Change set | Class-aware BE recovery offset + comment marker scan + audit doc |

Authenticated policy deep-probe was blocked locally (missing SUPABASE_* / owner token in shell). Health/ready + Railway SUCCESS are the independent deploy proof for #157.

---

## B. Break-Even audit and verified behavior

- Geometric BE (entry ± class offset_R) remains LIVE default.
- SCALP 0.80R / 0.35R, HOLD 1.0R / 0.30R, UNKNOWN 1.0R / 0.2R unchanged.
- Recovery 1R reconstruct now class-aware (**production via #157**).
- Net BE implemented behind `use_net_break_even=False` (default) — **not LIVE-active**.

---

## C. Broker SL re-confirmation — implementation status

| Item | Status |
|---|---|
| Module | `management/broker_confirm.py` |
| Engine hook | After OMS ok for BE/TRAIL when `require_broker_sl_confirm=True` |
| Reader adapter | `pme_broker_position_reader.Mt5BrokerPositionReader` |
| Default LIVE | **`require_broker_sl_confirm=False`** — preserves prior semantics |
| On confirm fail | `ManageOutcome.BROKER_CONFIRM_FAILURE`; no local BE/trail lock; retry next cycle |
| Tests | BUY/SELL/timeout/worse-SL/legacy path |

**Owner approval required** to set `require_broker_sl_confirm=True` in production PME config (material LIVE modify semantics).

---

## D. Net Break-Even analysis

| Item | Status |
|---|---|
| Helper | `r_math.net_break_even_stop` |
| Behavior | Returns `(None, incomplete_costs:…)` when spread/commission/swap/contract_size incomplete — **never invents** |
| LIVE | `use_net_break_even=False` |
| ITE | Passes optional `open_commission` / `open_swap` when present on broker row |
| Tests | Incomplete costs; BUY/SELL net vs geometric |

**Owner approval required** to enable `use_net_break_even=True`.

---

## E. Reversal / AI exit — findings and approval status

| Item | Status |
|---|---|
| Design | `PHASE_D_REVERSAL_EXIT_DESIGN.md` |
| Offline proposer | `management/exit_context.py` |
| LIVE wiring of exit booleans | **NOT done** |
| Session flatten | Gated: `session_flatten_on_market_closed=False` |
| Honest `market_open` | ITE now uses account/snapshot when known (no longer hard-coded True) |

**Owner approval required** before LIVE structural/AI exits or session flatten.

---

## F. Partial TP at 0.01 lot

| Finding | Fix |
|---|---|
| Lifecycle advanced with `record_partial(success=True)` on volume 0 | Now `ManageOutcome.SKIPPED`, `skipped=True`, **no** fictitious partial success metric, volume unchanged, **no OMS call** |
| Limitation | True scale-out impossible at single min-lot 0.01 — trail path remains reachable via lifecycle advance |

---

## G. Session / news / market-state

| Item | Status |
|---|---|
| Hard-coded `market_open=True` | Replaced with account/snapshot truth when available |
| Auto session liquidation | **Disabled** unless `session_flatten_on_market_closed=True` |
| News exits | Still unwired (planner ready; no invent-safe source confirmed for LIVE) |

---

## H. Broker trade attribution

| Item | Status |
|---|---|
| Existing stack (#153) | `attribution_store`, `close_attribution`, comment markers |
| This PR | Comment marker scan already on main via #157; no guesswork attribution added |
| Remaining | Most historical closes still unattributed — do not invent strategy IDs |

---

## I. Strategy and capital analysis (recommendations only)

Prior verified sample (Nov 2–3 broker): n=29, PF **0.68**, expectancy **−$0.33**, equity ~**$22.63**.  
**Do not raise lot / risk / concurrent.** Soft Scenario B remains approval-only. Re-fetch of authenticated broker history was blocked in this local shell; use prior audit figures until a fresh authenticated pull is available.

---

## J. Test results (this follow-up)

```
pytest tests/unit/test_pme_broker_confirm_net_be.py \
       tests/unit/test_institutional_trading_phase_d.py \
       tests/unit/test_trading_core_regression.py
→ 47 passed
ruff check (touched modules) → clean
```

---

## K. Production deployment IDs

| Deploy | ID / commit | Notes |
|---|---|---|
| #157 | Railway `75db8c3d` / `98f173a` | **Production verified** health/ready |
| Follow-up PR (this work) | Pending merge/deploy | Flags default OFF — safe to merge; activations need owner |

---

## L. Remaining defects / blockers

1. Enable broker SL confirm in LIVE (owner).  
2. Enable net BE in LIVE (owner).  
3. Wire reversal exits after shadow period (owner).  
4. Session flatten / news LIVE exits (owner).  
5. Fresh authenticated attribution + expectancy refresh.  
6. Wire `Mt5BrokerPositionReader` into ITE PME create path when confirm flag enabled.

---

## M. Exact owner decisions still required

1. **Merge follow-up PR** (gated defaults — recommended).  
2. **`require_broker_sl_confirm=True`?**  
3. **`use_net_break_even=True`?**  
4. **Approve shadow logging and/or LIVE reversal exits?**  
5. **`session_flatten_on_market_closed=True`?**  
6. Soft SOE Scenario B (unchanged recommendation — optional).

---

### Scorecard

| Bucket | Items |
|---|---|
| Completed and production verified | #157 class-aware recovery + comment scan |
| Implemented, awaiting merge/deploy | Broker confirm (OFF), net BE (OFF), exit proposer, session gate, min-lot partial honesty, honest market_open |
| Implemented, awaiting owner activation | Confirm flag, net BE flag, session flatten, LIVE reversal wiring |
| Recommendations only | Owner YAML, Scenario B, capital growth scenarios |
| Still missing | LIVE reversal context feed; full attribution coverage; confirm reader wired into ITE create |
