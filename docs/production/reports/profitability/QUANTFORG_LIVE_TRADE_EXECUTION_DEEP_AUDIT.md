# QuantForg — LIVE Trade Execution Deep Audit

**Generated:** 2026-11-05T17:20:00Z  
**Deploy under audit:** Railway `1fdef8ea` (commit `3c8bd4f`, PME #162)  
**Owner policy:** unchanged (max_lot 0.01, risk 20%, Q≥70, RR≥0.20, concurrent 1, …)

## Verdict

**The pipeline is not stuck.** After the capital top-up, QuantForg **already reached broker execution multiple times**. The earlier “no trades while LIVE” window was explained by (1) `MIN_LOT_INFEASIBLE` at $14.92, then (2) patient `OWNER_MIN_TRADE_QUALITY` rejects — not a broken worker.

**No deployment was required to “resume” trading.** No owner floors were changed. No forced trades. An open LIVE position may exist at report time — **not modified**.

---

## 1. Broker capital (authoritative)

| Time (approx UTC) | Balance | Equity | Margin | Positions |
| --- | --- | --- | --- | --- |
| Pre-deposit (prior audit) | 14.92 | 14.92 | 0 | 0 |
| Post-deposit verify | 30.92 | 30.92 | 0 | 0 |
| Mid second trade (~17:15) | 31.18 | ~28.7 floating | 4.12 | 1 |
| After SL close (~17:16) | **28.11** | **28.11** | 0 | 0 |
| Third fill open (~17:16:36) | 28.11 | ~28.59 floating | 4.12 | 1 |

Gateway `/session/status`: connected, trade_allowed, MT5 AutoTrading enabled, not degraded.  
XAUUSD: min lot 0.01, CS 100, tick 0.001/0.1, spread ~0.34–0.42, market open.

Sizing logs use **live equity** (e.g. `equity=28.11`), not stale $14.92.

---

## 2. End-to-end pipeline proof (real fills)

### Trade A — ticket **686061280** (~17:12:45Z)

| Stage | Result |
| --- | --- |
| Scheduler | PASS (`mode=LIVE`, `execution_enabled=True`) |
| Scanner / AI | BUY, quality **77**, confidence 67–80 |
| Sizing | final_lot **0.01**, Risk micro min-lot approved |
| OMS / bridge | Submitting Order |
| Broker | `order_send` retcode **10009** FILLED @ 4119.657 |
| SL/TP | SL 4116.119 · TP 4121.193 |
| Path log | `Scheduler → AI → Submit → MT5 Accepted → Ticket` |
| Close | **TP** · net **+$1.54** · deal 663559641 |

### Trade B — ticket **686063406** (~17:14Z)

| Stage | Result |
| --- | --- |
| Fill | BUY 0.01 @ 4121.847 · SL 4118.798 · TP 4124.783 · magic 260720 |
| Concurrent gate | Subsequent entries blocked: `Open positions 1 at max 1` (correct) |
| PME | Evaluating each cycle; R underwater → legitimate `NOOP` (BE at 0.80R not reached) |
| Close | **SL** · net **−$3.07** (−0.89R) · deal 663563587 |

### Trade C — ticket **686067251** (~17:16:36Z)

| Stage | Result |
| --- | --- |
| Risk | `risk_engine_micro_min_lot_approved` equity=28.11 needed_pct=8.54% |
| Broker | FILLED @ 4118.207 · SL 4115.806 · TP 4119.483 · planned risk ~$2.75 (9.62%) |
| Path | Full chain PASS again |

**Conclusion:** Market data → strategy → quality → Risk → OMS → MT5 → PME monitor → attribution ledger path is **operational**.

---

## 3. What blocked trades *before* fills (historical)

| Period | Dominant blocker | Nature |
| --- | --- | --- |
| Equity ~$14.92 | `MIN_LOT_INFEASIBLE` (stop ~5.07 ≫ max ~2.98) | Capital geometry — resolved by deposit |
| Flat, equity ~$30.92, no fill yet | `OWNER_MIN_TRADE_QUALITY` (e.g. 68 &lt; 70) | Owner floor — **correct patience** |
| Transient gateway 530 | Session not connected / safety fail-closed | Recovered |
| Transient | `Daily P/L unavailable — verifying` | Fail-closed — recovered |
| While position open | `Max open positions 1>=1` / `Already in trade` | Owner concurrent=1 — correct |

### Stage counts (qualitative, from Railway samples ~17:12–17:17)

| Stage | Observed behavior |
| --- | --- |
| Gateway / MD | Fresh quotes/candles after recovery |
| Scheduler | Continuous ~5s ticks |
| Strategies (5) | Evaluated every scan; often `multi_strategy_no_passer` / prefer-no-trade when SOE floors unmet |
| Signal gen | Frequent BUY candidates when quality ≥~76 |
| Quality &lt; 70 | Rejected at DECISION (`OWNER_MIN_TRADE_QUALITY`) |
| Risk | Approves min-lot when stop fits; blocks concurrent |
| OMS | Reached on fills (`forwarded_to_oms=True`) |
| Broker | `10009` fills — no broker reject on sampled sends |

---

## 4. Exact root cause of “missing trades” (owner question)

**Not** a dead worker, stuck OMS, or permanent capital lock.

1. **Before deposit:** Risk correctly refused oversized stops at min lot.  
2. **After deposit, before first fill:** System waited for **quality ≥ 70** (and other gates).  
3. **After first fill:** System traded; further entries correctly deferred by concurrent=1 until close.  
4. **Now:** Continuously monitoring; opens when full gate stack passes.

If the UI still “looks idle,” check whether a position is already open or whether the last cycles are quality/cooldown/`DIRECTION_NONE` waits — those are intentional.

---

## 5. Soft defects / follow-ups (not blocking execution)

| Issue | Evidence | Severity | Action this cycle |
| --- | --- | --- | --- |
| Close `strategy_id=None`, `soe_recorded=False` | Attribution logs on TP/SL closes | Medium — hurts strategy P&amp;L books | Documented; bind-on-open repair deferred (frozen core / needs careful PR) |
| Log reason `safety_blocked_manage` while PME still evaluates | Manage called from safety-blocked *entry* path | Low — misleading label | Docs only; management still runs |
| Occasional `STALE_RISK` / `ignored_action NO_TRADE` abort on a tradable BUY | One cycle aborted; next cycle filled | Medium — race/latency | Monitor; do not weaken STALE_RISK without dedicated fix |
| `high_quality=False` on some `SIGNAL_EXECUTED` rows while reasons say quality 76 | Telemetry flag vs trade quality mismatch | Low | Monitor |

**No safeguard weakening.** LIVE reversal remains off.

---

## 6. Strategy review

| Strategy | Data / scan | Signals | Quality path | Notes |
| --- | --- | --- | --- | --- |
| All five evaluated | Yes | Via SOE | Owner Q70 | `strategies_evaluated=5` |
| momentum_scalping | Active selector historically | Yes | Can pass | Dominant when SOE picks |
| Others | Scanned | Often no passer | Prefer-no-trade when floors unmet | Not broken — selective |

---

## 7. Min-lot at current equity (~$28.11)

| Metric | Value |
| --- | --- |
| Max $ risk @ 20% | ≈ $5.62 |
| Max stop @ 0.01 | ≈ 5.62 |
| Recent fills | Stops ~2.4–3.7 → **FEASIBLE** (Risk approved) |

Wider stops that exceed 20% still correctly blocked.

---

## 8. Changes / deploy

| Item | Status |
| --- | --- |
| Code/config changes for execution resume | **None required** |
| Owner YAML | Unchanged |
| Tests / PR / Railway redeploy for this audit | Docs-only report PR |
| Production health | `/health` `/ready` 200; LIVE worker running |

---

## 9. Success condition checklist

| Requirement | Status |
| --- | --- |
| Operationally healthy | Yes |
| Continuously monitoring XAUUSD | Yes |
| Qualified setups can reach OMS/broker | **Proven by fills** |
| Never forced to trade | Yes — waits on Q&lt;70 / concurrent / SOE |
| Explain waits | Rejection reasons logged (`OWNER_MIN_TRADE_QUALITY`, concurrent, cooldown, etc.) |

**Capital protection and positive expectancy remain priorities.** Recent net of sampled closes (+1.54 then −3.07) does **not** establish profitability.
