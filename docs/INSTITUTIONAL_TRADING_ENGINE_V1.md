# QuantForg Institutional Trading Engine v1 — Architecture

**Status:** Phases A–H ✅ — Certified institutional stack (measurement gate for LIVE)  
**Scope:** XAUUSD only · Deterministic · Execution-quality · No AI advisor  
**Date:** 2026-07-20  
**Depends on:** ADR-0007 (Analysis Pipeline), ADR-0008 (MarketAnalysisSnapshot), ADR-0010 (Analysis never trades), Institutional Execution Engine OMS  

### Institutional defaults (approved 2026-07-20)

| Setting | Value |
|---------|-------|
| MTF hierarchy | **H4** macro bias · **H1** primary structure · **M15** entry confirmation · **M5** execution & trade management |
| Min confluence | **80** (90–100 high confidence · 80–89 tradable · &lt;80 reject) |
| Max open trades | **1** |
| Trade management | **1R** → BE · **2R** → close 50% · **&gt;2R** dynamic trail on remainder |
| Simulation fills | Next bar open |
| Trade Quality Score | 0–100 from Trend · Liquidity · OB · FVG · Structure · Session · Spread; reject &lt;80 |
| Sessions | London · New York · London/NY overlap; avoid low-liquidity |
| News protection | Configurable (NFP/CPI/FOMC…); **disabled by default** without reliable feed |
| Risk | 1% / trade · 3% max daily loss · 8% max weekly DD · cooldown after 3 consecutive losses |

---

## 1. Mission statement

Build a **production-grade autonomous trading system** for **XAUUSD** that:

1. Analyses market structure, liquidity, order blocks, FVGs, and multi-timeframe trend **deterministically**.
2. Opens trades **only** when confluence confidence exceeds a hard threshold.
3. Sizes and gates risk through a dedicated Risk Engine.
4. Submits and manages orders exclusively through the **existing Institutional Execution Engine / OMS**.
5. Manages open risk (break-even, trail, partials, emergency exit, time stop) with a **Trade Management Engine**.
6. Measures itself with institutional analytics.
7. Supports a **Simulation Mode** that replays historical candles with zero `order_send`.

This is **not** a signal generator UI and **not** an LLM/AI strategy. AI may later become an optional advisor behind a port; v1 never calls it.

---

## 2. Non-negotiable principles

| # | Principle | Implication |
|---|-----------|-------------|
| P1 | **Deterministic** | Same bars + same config → same decisions, tickets intent, and journal. No random seeds in the live path. |
| P2 | **Reproducible** | Every decision stores input fingerprint (bar times, hashes, config version). |
| P3 | **Testable** | Each module is a pure domain engine with fakes; orchestration is integration-tested. |
| P4 | **Gold-only** | Symbol forced to XAUUSD via existing `gold_only` policy. No multi-symbol in v1. |
| P5 | **One OMS entry** | Live sends only via Institutional Execution Engine → Gateway → MT5. No parallel send paths. |
| P6 | **Analysis ≠ execution** | ICT engines emit snapshots only. The Trade Decision Engine alone may request execution. |
| P7 | **No AI in v1** | Quant AI / LLM ports are disabled / not wired. Heuristic “AI briefs” are out of the critical path. |
| P8 | **Fail closed** | Any missing data, risk halt, or OMS reject → no trade. Never invent fills or prices. |
| P9 | **Simulation parity** | Sim mode uses the same decision + risk + management code; only the Execution Port is swapped. |

---

## 3. System context

```
┌──────────────────────────────────────────────────────────────────────────┐
│                     Institutional Trading Engine v1                      │
│                                                                          │
│  Market Snapshot (MT5 gateway / bar store)                               │
│       ↓                                                                  │
│  Analysis Pipeline — Phase A (ADR-0007)                                  │
│       Structure → Liquidity → OB → FVG → Trend + Quality/Session/News    │
│       ↓                                                                  │
│  MarketAnalysisSnapshot                                                  │
│       ↓                                                                  │
│  ConfluenceEngine — Phase B (canonical judge)                            │
│       ↓                                                                  │
│  RiskEngine (extended) → ALLOW sized | REJECT (+ all reasons)            │
│       ↓                                                                  │
│  PositionEligibilityEngine — pre-OMS checklist                           │
│       ↓                                                                  │
│  TradeDecisionEngine → NO_TRADE | WATCH | BUY | SELL                     │
│       ↓                                                                  │
│  Execution Bridge — Phase C (re-verify · journal · kill switch · canary) │
│       ↓ only BUY/SELL + all gates pass                                   │
│  Institutional OMS (existing, unmodified) → Gateway → MetaTrader5        │
│       ↓                                                                  │
│  Position Management Engine — Phase D (BE · partial · ATR trail · exits) │
│       ↓                                                                  │
│  Research Platform — Phase E (Sim · WF · MC · Analytics · Promotion)     │
│       ↓ SimulationOmsPort only (no order_send)                           │
└──────────────────────────────────────────────────────────────────────────┘
```

**Phase B rule:** Decision path never calls OMS / `order_send`. Eligibility failure → `NO_TRADE` only.

**Phase C rule:** Only the Execution Bridge may call OMS for entries. WATCH/NO_TRADE ignored.

**Phase D rule:** PME never opens trades. Manages EXISTING positions only.

**Phase E rule:** Simulation uses the same institutional decision/risk/eligibility/bridge/PME contracts via `SimulationOmsPort`. Never MT5 `order_send`. Append-only versioning.

**External systems:** Windows MT5 Gateway (live), bar history APIs, existing frontend Terminal/Broker/Diagnostics (observe only in v1; no new primary nav surface required).

---

## 4. Module catalogue

### MODULE 1 — Market Structure Engine

| | |
|--|--|
| **Purpose** | Detect swings, internal/external structure, BOS, CHOCH |
| **Reuse** | `app/domain/market_structure/` (`SwingDetector`, `StructureAnalyzer`, `MarketStructureEngine`) |
| **v1 work** | Thin adapter into unified snapshot; expose `internal` vs `external` structure labels consistently in snapshot contract |
| **Inputs** | OHLC bars (single TF) |
| **Outputs** | `StructureSnapshot`: swing highs/lows, BOS, CHOCH, trend state, internal/external nodes |
| **Determinism** | Close-based rules; fixed swing lookback from config |

### MODULE 2 — Liquidity Engine

| | |
|--|--|
| **Purpose** | Equal highs/lows, pools, buy-side / sell-side liquidity, sweeps |
| **Reuse** | `app/domain/liquidity/` (`EqualHighDetector`, `EqualLowDetector`, `LiquiditySweepDetector`, `LiquidityEngine`) |
| **v1 work** | Snapshot fields for BSL/SSL tags used by confluence |
| **Inputs** | Bars + structure swings |
| **Outputs** | `LiquiditySnapshot`: EQH, EQL, pools, sweeps, BSL/SSL levels |

### MODULE 3 — Order Blocks (Smart Money Concepts)

| | |
|--|--|
| **Purpose** | Bullish/bearish OBs, mitigation, breaker blocks |
| **Reuse** | `app/domain/order_block/` (`OrderBlockDetector`, `MitigationDetector`, `BreakerDetector`, `OrderBlockEngine`) |
| **v1 work** | Prefer OBs tied to recent BOS/CHOCH; strength score already exists |
| **Inputs** | Bars + structure breaks |
| **Outputs** | `OrderBlockSnapshot`: active OBs, mitigated, breakers |

### MODULE 4 — Fair Value Gaps

| | |
|--|--|
| **Purpose** | Bullish/bearish FVG, partial fill, full mitigation/invalidation |
| **Reuse** | `app/domain/fair_value_gap/` (`FairValueGapDetector`, `GapFillDetector`, `FairValueGapEngine`) |
| **v1 work** | Confluence consumes “fresh / partially filled / mitigated” states |
| **Inputs** | Bars (+ optional OB for quality) |
| **Outputs** | `FairValueGapSnapshot`: gaps, fills, quality |

### MODULE 5 — Trend Engine (MTF)

| | |
|--|--|
| **Purpose** | Multi-timeframe bias + confidence |
| **Timeframes** | **M5, M15, H1, H4, Daily** (aligns with existing `decision_engine/mtf.py` `REQUIRED_TFS`) |
| **Reuse** | Per-TF `MarketStructureEngine` / `TrendClassifier` + `summarize_mtf()` |
| **v1 work** | Dedicated `TrendEngine` façade that scores alignment (e.g. D1/H4 bias must agree for high confidence) |
| **Outputs** | `TrendSnapshot`: per-TF direction, alignment score 0–100, daily bias enum |

**Scoring sketch (deterministic):**

```
alignment = weighted vote(D1:30, H4:25, H1:20, M15:15, M5:10)
confidence = alignment * (1 - conflict_penalty)
```

Conflicts (e.g. D1 bullish vs H1 bearish) reduce confidence; they do not invent a trade.

### MODULE 6 — Confluence Engine ✅ Phase B

| | |
|--|--|
| **Purpose** | Final institutional judge; emit direction + confidence only above threshold |
| **Impl** | `app/domain/institutional_trading/confluence.py` → `ConfluenceEngine` |
| **Inputs** | `MarketAnalysisSnapshot` + optional ATR + current drawdown % |
| **Outputs** | `ConfluenceResult` (see §5.2) |

**Hard gate (config, defaults):**

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `min_confluence_score` | **80** | Below → reject / WATCH band |
| `high_confidence_score` | **90** | 90–100 = high confidence |
| `min_trade_quality_score` | **80** | Independent quality gate |
| `min_aligned_tfs` | **3** of hierarchy | H4/H1/M15 core agreement |
| `require_structure_event` | true | Need BOS or CHOCH context on H1 |
| `require_liquidity_or_ob` | true | Sweep into OB **or** OB + FVG |
| `require_fvg_or_ob` | true | At least one SMC zone |
| `allowed_sessions` | London, New York, London/NY overlap | Avoid low-liquidity |
| `news_protection_enabled` | **false** | Enable only with reliable calendar feed |

**Example long factors (illustrative):**

- H4 + H1 bullish bias  
- CHOCH/BOS bullish on H1  
- Sell-side liquidity swept  
- Price in bullish OB  
- Bullish FVG unmitigated overlapping entry  

### MODULE 7 — Risk Engine ✅ Phase B (extended)

| | |
|--|--|
| **Purpose** | Dynamic sizing + portfolio risk gates; return every rejection reason |
| **Reuse** | `app/application/services/risk_engine.py` |
| **ITE mapping** | `risk_config_from_ite()` — does **not** change global FX defaults |

| Control | v1 / Phase B behavior |
|---------|------------------------|
| Risk % per trade | 1% equity (ITE) |
| Max daily loss | 3% → reject |
| Max weekly drawdown | 8% → reject |
| Max open trades | **1** (ITE) |
| Max consecutive losses | After **3** → reject |
| Cooldown after loss streak | Active flag / remaining minutes → reject |
| Session restriction | `session_allowed=false` → reject |
| Spread restriction | Above `max_spread` → reject |
| ATR volatility filter | ATR% of mid above cap → reject |

**Fail closed:** if free margin, symbol specs, or SL distance invalid → REJECT (no trade).

### MODULE 8 — Trade Decision Engine ✅ Phase B

| | |
|--|--|
| **Purpose** | Convert confluence + risk + eligibility into a decision — **never sends** |
| **Impl** | `trade_decision.py` + `InstitutionalDecisionPipeline` |
| **Outputs** | `TradeDecision`: `NO_TRADE` \| `WATCH` \| `BUY` \| `SELL` (see §5.2b) |
| **Rules** | Never sizes without Risk Engine. Never calls OMS. Never bypasses gold-only. |

### MODULE 8b — Position Eligibility Engine ✅ Phase B

| | |
|--|--|
| **Purpose** | Last checklist before any future OMS call |
| **Impl** | `app/domain/institutional_trading/eligibility.py` |
| **Checks** | Already in trade · max exposure · risk available · market open · spread · session · news · confluence ≥80 · quality ≥80 |
| **Rule** | Any NO → ineligible → `NO_TRADE`. Never call OMS. |

### MODULE 9 — Execution Engine (existing OMS) + Phase C Bridge ✅

| | |
|--|--|
| **Purpose** | Validate → safety → `order_check` → `order_send` |
| **Reuse** | `InstitutionalExecutionEngine`, `ExecutionGateway`, MT5 gateway trade routes — **UNMODIFIED by Phase C** |
| **Phase C bridge** | `ExecutionBridge` + `InstitutionalOmsAdapter` (sole Decision→OMS path) |
| **Live gate** | `EXECUTION_ENABLED=true` + bridge kill switch off + mode ≠ SHADOW |
| **Observability** | ITE `ExecutionAttemptJournal` + existing OMS journal |

#### Execution Bridge diagram

```
TradeDecision (BUY|SELL only)
        │
        ▼
┌─────────────────────── ExecutionBridge ───────────────────────┐
│  ignore WATCH / NO_TRADE                                      │
│  1. input_hash matches expected                               │
│  2. age < decision_ttl (default 30s)                          │
│  3. session still valid                                       │
│  4. market still open                                         │
│  5. spread still acceptable                                   │
│  6. PositionEligibilityEngine re-check                        │
│  7. EXECUTION_ENABLED (live/canary)                           │
│  8. kill switch disarmed                                      │
│  9. decision_hash not previously executed                     │
│  + canary daily cap (CANARY_LIVE)                             │
│  any fail → journal ABORT, never OMS                          │
└───────────────────────────┬───────────────────────────────────┘
                            │ pass
          ┌─────────────────┼─────────────────┐
          ▼                 ▼                 ▼
       SHADOW          CANARY_LIVE          LIVE
    journal only      OMS ≤1/day           OMS via
    no OMS call       then cap abort       OmsSubmitPort
                            │                 │
                            └────────┬────────┘
                                     ▼
                    InstitutionalOmsAdapter
                                     │
                                     ▼
                    InstitutionalExecutionEngine.run_submit
                                     │
                                     ▼
                         ExecutionGateway → MT5
```

**Modes:** `SHADOW` · `CANARY_LIVE` (max 1 trade/day) · `LIVE`  
**Retry:** never — decision hash consumed on first OMS attempt (success or fail).

### MODULE 10 — Position Management Engine ✅ Phase D

| | |
|--|--|
| **Purpose** | Manage open XAU positions after fill — **automated**, deterministic |
| **Impl** | `app/domain/institutional_trading/management/` |
| **Port** | `OmsManagePort` → `InstitutionalOmsManageAdapter` → existing `run_submit` (oms_kind `sltp` / `partial_close` / `close`) |
| **Never** | Opens trades · modifies OMS · edits Phase A/B/C |

| Policy | Behavior |
|--------|----------|
| **Break-even** | At **+1R**, move SL to entry **+0.2R** once; never move backwards |
| **Partial** | At **+2R**, close **50%**; remainder continues |
| **ATR trail** | After **2R** and PARTIAL state; distance = ATR × regime mult (low/normal/high); never fixed-pip |
| **Time stop** | If max favorable R &lt; min within N minutes (30/60/120) → flatten |
| **Emergency** | Structure break · trend reverse · spread spike · market closed · connection unstable · risk exit |
| **Daily shutdown** | Daily loss · kill switch · news exit → flatten |

#### Position state machine

```
OPEN ──(+1R BE)──► BE_MOVED ──(+2R 50%)──► PARTIAL ──(ATR trail)──► TRAILING
  │                    │                      │                        │
  └────────────────────┴──────────────────────┴────────────────────────┴──► EXITED
       (emergency / time stop / daily shutdown / manual close)
```

Illegal: `OPEN→PARTIAL`, `OPEN→TRAILING`, `BE_MOVED→TRAILING` (never skip).  
One progressive action per `evaluate()` tick.

#### Position journal schema

```text
ticket, action, from_state, to_state, reason, timestamp, latency_ms, outcome
old_sl, new_sl, old_tp, new_tp, volume, r_multiple, retcode, comment, fingerprint
```

#### PME metrics schema

```text
evaluations, average_hold_seconds, average_rr
be_success / be_attempts
trailing_success / trailing_attempts
partial_success / partial_attempts
exits, exit_reasons{}, duplicates, oms_failures
```


### MODULE 11 — Analytics

| | |
|--|--|
| **Purpose** | Measure engine performance (strategy quality, not just fill latency) |
| **Reuse** | `backtest_metrics.MetricsEngine`, execution analytics (separate) |
| **Metrics** | Win rate, expectancy, profit factor, average R:R, max drawdown, Sharpe, daily PnL series |
| **Store** | Per-engine-run and live-session aggregates; no mock trades |

### MODULE 12 — Simulation Mode

| | |
|--|--|
| **Purpose** | Replay historical XAU candles; full pipeline; **no** `order_send` |
| **Reuse** | Backtest `ReplayClock` / paper executor patterns |
| **Contract** | `ExecutionPort = SimulationExecutor` fills at next bar open/close per config slippage model (deterministic) |
| **Output** | Same analytics + decision journal as live |

---

## 5. Canonical data contracts

### 5.1 `MarketAnalysisSnapshot` (analysis output)

```text
symbol: XAUUSD
as_of: timestamp
timeframes: { M5, M15, H1, H4, D1 } → bar fingerprints
structure: StructureSnapshot          # primary TF configurable (default H1)
liquidity: LiquiditySnapshot
order_blocks: OrderBlockSnapshot
fvgs: FairValueGapSnapshot
trend: TrendSnapshot                  # MTF
context: optional session/volatility  # reuse market_context if available
config_version: string
input_hash: string                    # reproducibility key
```

### 5.2 `ConfluenceResult` (Phase B)

```text
confidence: 0..100
direction: BUY | SELL | NONE
reasons: [str, ...]
rejected_rules: [str, ...]
input_hash: str
band: reject | tradable | high_confidence
passed: bool                    # confidence >= min_confluence AND direction != NONE
factors: { code → int }
```

### 5.2b `TradeDecision` (Phase B — decision object schema)

```text
id: uuid
schema_version: "1.0.0"
action: NO_TRADE | WATCH | BUY | SELL
direction: BUY | SELL | NONE
confidence: 0..100
quality: 0..100
risk_score: 0..100
reasons: [str, ...]
invalidations: [str, ...]
entry_zone: { low, high, mid? } | null
stop_zone:  { low, high, mid? } | null
target_zone:{ low, high, mid? } | null
estimated_rr: decimal | null
expected_duration: str          # e.g. "intraday_m5_m15"
confluence: ConfluenceResult
eligibility: {
  eligible: bool
  checks: {
    already_in_trade, max_open_trades, risk_available,
    market_open, spread_acceptable, session_valid,
    news_clear, confluence_ok, quality_ok, ...
  }
  rejection_reasons: [str, ...]
}
input_hash: str
config_version: str
symbol: XAUUSD
as_of: iso8601
approved_lots: decimal | null   # from RiskEngine when ALLOW
risk_reasons: [str, ...]
```

**Determinism:** same snapshot + same `AccountRiskState` + same config → identical
`action`, zones, scores, and hashes (UUID `id` is the only non-content identity field).

### 5.3 `SizedIntent` / OMS mapping (Phase C)

Bridge builds `OrderIntent` via existing `parse_order_intent` (OMS helper, not modified):

```text
symbol, side=buy|sell, order_type=market
volume = approved_lots
stop_loss / take_profit from decision zones
magic = ITE magic, comment = ite:v1:{input_hash_prefix}
→ InstitutionalExecutionEngine.run_submit → ExecutionResult tickets/retcode
```

### 5.3b `ExecutionAttemptRecord` (Phase C journal schema)

```text
decision_hash: str          # content hash; execute-once key
input_hash: str
timestamp: iso8601
decision_action: BUY|SELL|…
confidence: int
quality: int
approved_lots: decimal|null
oms_status: str
gateway_status: str
mt5_ticket: int|null
mt5_deal: int|null
retcode: int|null
comment: str
latency_ms: float
execution_result: str       # success|shadow|abort reason|…
abort_reason: BridgeAbortReason
mode: SHADOW|CANARY_LIVE|LIVE
status: aborted|shadow|forwarded|duplicate|oms_rejected|oms_success
```

```text
symbol: XAUUSD
side: buy | sell
order_type: market | limit (v1 default market)
volume: decimal           # from Risk Engine + MT5 volume_step
sl, tp: prices
magic: ITE_MAGIC
comment: ite:v1:{decision_id}
decision_id: uuid
fingerprint: string
```

### 5.4 `ManageCommand`

```text
action: break_even | trail | partial_close | flatten | modify_sltp
ticket: int
volume?: decimal
sl?: price
tp?: price
reason: string
```

---

## 6. Runtime loops

### 6.1 Decision loop (entries) — Phase B complete through step 6

```
every N seconds OR on new closed bar (H1 primary, M5 trigger):
  1. Load XAUUSD bars for M5,M15,H1,H4,D1 (fail closed if incomplete)
  2. Run Analysis Pipeline → MarketAnalysisSnapshot          # Phase A
  3. ConfluenceEngine → ConfluenceResult                     # Phase B
  4. RiskEngine.evaluate → ALLOW sized | REJECT (+reasons)   # Phase B
  5. PositionEligibilityEngine → eligible | NO               # Phase B
  6. TradeDecisionEngine → NO_TRADE | WATCH | BUY | SELL     # Phase B
  7. ExecutionBridge.handle (re-verify + journal)            # Phase C
     - SHADOW: journal only
     - CANARY_LIVE / LIVE: OmsSubmitPort → existing OMS only if gates pass
  8. Record attempt in ITE journal (+ OMS blotter when forwarded)
```

### 6.2 Management loop (open book)

```
every M5 closed bar (and optional tick throttle):
  1. Sync positions from MT5 / sim book
  2. For each ITE-magic position:
       evaluate BE / trail / partial / time / emergency
  3. Emit ManageCommands through ExecutionPort
  4. Update analytics
```

### 6.3 Simulation loop

```
for bar in replay(XAUUSD, range, TFs):
  advance clocks → decision loop → management loop
  never call MetaTrader5.order_send
```

---

## 7. Package layout (proposed)

Keep domain engines where they are. Add a thin **orchestrator** package:

```text
app/domain/institutional_trading/
  models.py / pipeline.py / trend_engine.py / …   # Phase A
  decision_models.py                              # ConfluenceResult, TradeDecision, …
  confluence.py                                   # ConfluenceEngine
  eligibility.py                                  # PositionEligibilityEngine
  trade_decision.py                               # TradeDecisionEngine
  config.py / fingerprint.py

app/application/services/
  institutional_trading_analysis.py               # Phase A orchestrator
  institutional_decision_pipeline.py              # Phase B orchestrator
  institutional_execution_integration.py          # Phase C façade
  institutional_oms_adapter.py                    # OmsSubmitPort → OMS (no OMS edits)
  risk_engine.py                                  # Extended gates (streak/DD/spread/ATR/session)

app/domain/institutional_trading/execution/       # Phase C bridge package
  bridge.py / config.py / models.py / journal.py
  kill_switch.py / metrics.py / hashing.py / oms_port.py

app/domain/institutional_trading/management/      # Phase D PME package
  engine.py / policies.py / state_machine.py / r_math.py
  config.py / models.py / journal.py / metrics.py / oms_port.py

app/application/services/
  institutional_oms_manage_adapter.py             # OmsManagePort → OMS (no OMS edits)
  institutional_position_management.py            # Phase D façade

# OMS — DO NOT MODIFY for Phase D
# InstitutionalExecutionEngine / ExecutionGateway
```

**Do not** rewrite Structure/Liquidity/OB/FVG engines. **Do not** duplicate OMS.

---

## 8. Configuration (v1 defaults)

```yaml
symbol: XAUUSD
# MTF hierarchy (approved)
macro_bias_tf: H4
primary_structure_tf: H1
entry_confirmation_tf: M15
execution_management_tf: M5
min_confluence_score: 80
high_confidence_score: 90
min_trade_quality_score: 80
risk_per_trade_pct: 1.0
max_daily_loss_pct: 3.0
max_weekly_drawdown_pct: 8.0
max_open_trades: 1
max_consecutive_losses: 3
cooldown_after_loss_streak: true
break_even_at_r: 1.0
partial_at_r: 2.0
partial_close_pct: 50
trail_after_r: 2.0
allowed_sessions: [london, new_york, london_ny_overlap]
news_protection_enabled: false
simulation:
  fill_model: next_bar_open
```

All numeric thresholds live in versioned config; changing them changes `config_version` in fingerprints.

---

## 9. Explicit non-goals (v1)

- Multi-symbol trading  
- LLM / Quant AI in the decision path  
- Copy trading / social signals  
- Rewriting MT5 gateway or OMS  
- Guaranteeing profitability  
- Tick-perfect HFT  
- Automatic strategy parameter genetic search in live mode  

---

## 10. Mapping: requested stack → QuantForg

| Requested layer | QuantForg home | Build vs reuse |
|-----------------|----------------|----------------|
| Market Data | MT5 gateway + bar APIs | Reuse |
| Market Structure | `domain/market_structure` | Reuse + snapshot glue |
| Liquidity | `domain/liquidity` | Reuse |
| Smart Money (OB) | `domain/order_block` | Reuse |
| FVG | `domain/fair_value_gap` | Reuse |
| Trend Engine | MTF façade over structure + `decision_engine/mtf` | **New façade** |
| Confluence | Canonical ITE scorer | **New** (absorb duplicated scoring) |
| Risk | `RiskEngine` + consecutive-loss gate | **Extend** |
| Trade Decision | New ITE decision module | **New** |
| Execution | Institutional EE / Gateway | Reuse |
| Trade Management | New policy loop → OMS manage | **New** |
| Analytics | `MetricsEngine` + ITE session store | Reuse + wire |
| Simulation | Replay + SimulationExecutionPort | **New** on existing replay |

---

## 11. Testing strategy

| Level | What |
|-------|------|
| Unit | Each ICT engine (existing); confluence fixtures; trade management state machine; risk gates |
| Property | Fingerprint stability; volume always on `volume_step`; SL never widens on trail |
| Integration | Snapshot pipeline on golden XAU bar sets → expected HOLD/ENTER |
| Simulation | Multi-day replay → analytics within tolerance of locked fixtures |
| Live dry-run | `EXECUTION_ENABLED=false` → decisions journaled, zero sends |
| Live canary | Enabled flag + max 1 trade / day hard cap |

---

## 12. Implementation phases (after architecture sign-off)

| Phase | Deliverable | Exit criteria |
|-------|-------------|-----------------|
| **A** | `MarketAnalysisSnapshot` orchestrator for XAU (Structure→…→Trend) | ✅ `tests/unit/test_institutional_trading_phase_a.py` |
| **B** | Confluence + Risk extensions + Eligibility + Trade Decision | ✅ `tests/unit/test_institutional_trading_phase_b.py` |
| **C** | Execution Bridge → existing OMS; journal; kill/canary/shadow | ✅ `tests/unit/test_institutional_trading_phase_c.py` |
| **D** | Position Management Engine (BE, ATR trail, partial, time, emergency) | ✅ `tests/unit/test_institutional_trading_phase_d.py` |
| **E** | Research Platform (sim, WF, MC, analytics, promote) | ✅ `tests/unit/test_institutional_trading_phase_e.py` |
| **F** | Ops Control Plane (modes, kill, rollback, audit, runbooks) | ✅ `tests/unit/test_institutional_trading_phase_f.py` |
| **G** | Reliability & Observability (24/7 health, traces, chaos) | ✅ `tests/unit/test_institutional_trading_phase_g.py` |
| **H** | Production Validation & Certification (Go/No-Go) | ✅ `tests/unit/test_institutional_trading_phase_h.py` |

**No Phase includes AI.**

### Phase H — Production Validation & Certification (met)

```
Evidence (shadow days · canary metrics · probes · stage OK)
        ↓
EndToEndCertifier (Decision→…→Reliability)
        ↓
CanaryValidator · LiveAcceptanceGate · Stress · FailureInjection
        ↓
Scorecard + GoNoGoEngine
        ↓
Production Certificate + Operator checklist
        ↓
/ops Certification panel · /ite/certification/*
```

**Rule:** Measurement only. Never `order_send`. Never modifies OMS / strategies / AI.

#### Live acceptance thresholds

| Gate | Required |
|------|----------|
| Shadow | ≥14 days |
| Canary trades | ≥100 |
| Gateway uptime | ≥99.9% |
| Execution success | ≥99% |
| Duplicate executions | ==0 |
| Critical incidents | ==0 |

#### Go / No-Go

- `NOT_READY` — pipeline / stress / failure injection incomplete  
- `READY_FOR_CANARY` — E2E + stress + failures OK; live gates may fail (explained)  
- `READY_FOR_LIVE` — all gates + zero duplicates + zero critical incidents  

#### Schemas (Phase H)

Migration `20260720180000_ite_certification.sql`:

- `ite_certification_reports`
- `ite_certification_certificates`
- `ite_certification_canary_snapshots`
- `ite_certification_approvals`

#### API (Phase H)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ite/certification/dashboard` | Scores · Go/No-Go · checklist |
| POST | `/ite/certification/run` | Full certification report |
| GET | `/ite/certification/report` | Last report |
| GET | `/ite/certification/go-nogo` | Verdict + failed requirements |
| GET | `/ite/certification/certificate` | Production certificate |
| POST | `/ite/certification/approve` | Operator sign-off |
| POST/GET | `/ite/certification/canary` | Canary metrics |
| POST | `/ite/certification/stress` · `/failures` | Isolated suites |

#### Operator checklist

1. Confirm Phases A–G unit suites green in CI  
2. Confirm Shadow ≥14 days (or accept canary-only path)  
3. Confirm canary metrics from OMS journal (read-only)  
4. Confirm gateway uptime ≥99.9%  
5. Confirm zero duplicate executions and zero CRITICAL incidents  
6. Run `POST /ite/certification/run`  
7. Review Go/No-Go failed requirements  
8. Operator sign-off on certificate  
9. LIVE mode change only via Phase F control plane  
10. Do not enable AutoTrading until `READY_FOR_LIVE`

### Phase H exit (met)

- E2E certification across Decision→Reliability  
- Canary validator metrics  
- Live acceptance gate  
- Stress 100/500/1000/5000  
- Failure injection (gateway/MT5/tunnel/DB/Supabase slow/Railway slow)  
- Certification dashboard scores  
- Production certificate  
- Go/No-Go engine with explained failures  
- No OMS rewrite · no new strategies · no AI  

---

### Phase G — Production Reliability & Observability (met)

```
Continuous probes / heartbeats
        ↓
ReliabilityPlatform.tick()
        ↓
Health · Incidents · Escalation · Notifications
        ↓
TradeTrace (one trace_id: Decision→…→Journal)
        ↓
Live metrics · Audit timeline · Chaos harness
        ↓
/ops Reliability panel · /ite/reliability/*
```

**Recovery policy:** gateway reconnect · MT5 reconnect · safe-read retry — **never** automatic `order_send` retry.

#### Schemas (Phase G)

Migration `20260720160000_ite_reliability_observability.sql`:

- `ite_reliability_heartbeats`
- `ite_reliability_health_snapshots`
- `ite_reliability_traces`
- `ite_reliability_incidents`
- `ite_reliability_recovery_events` (CHECK blocks `order_send_retry`)
- `ite_reliability_timeline`
- `ite_reliability_metrics_snapshots`

#### Incident model

`Incident{ severity: INFO|WARNING|ERROR|CRITICAL, status: OPEN|ACKNOWLEDGED|MITIGATING|RESOLVED, escalation_level, source, title, detail }`  
Escalation thresholds by severity (minutes open).

#### Recovery model

`RecoveryAction ∈ {gateway_reconnect, mt5_reconnect, safe_read_retry}`  
`RecoveryOrchestrator.retry_order_send()` raises — forbidden.

#### API (Phase G)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ite/reliability/dashboard` | Ops dashboard payload |
| POST | `/ite/reliability/tick` | Health + heartbeat miss → incidents |
| POST | `/ite/reliability/heartbeat` | Publish component heartbeat |
| GET | `/ite/reliability/metrics` | Live metrics |
| GET | `/ite/reliability/incidents` | Incident list |
| GET | `/ite/reliability/timeline` | Search/filter timeline |
| GET | `/ite/reliability/timeline/export` | Export JSON/CSV |
| POST | `/ite/reliability/chaos/inject` \| `/clear` | Chaos harness |
| POST | `/ite/reliability/recovery/gateway` \| `/mt5` | Safe reconnect |

### Phase G exit (met)

- Continuous health across gateway/MT5/tunnel/Railway/Supabase/DB/OMS/execution/decision/PME  
- Heartbeat miss → incident  
- Distributed trade trace (single id)  
- Incident manager + escalation + notifications (email/slack/discord/webhook/telegram adapters)  
- Live metrics + ops dashboard charts  
- Searchable/filterable/exportable timeline  
- Chaos scenarios with graceful degradation  
- No OMS rewrite · no strategy changes · no AI  

### Production readiness report (post-G)

| Area | Status |
|------|--------|
| Trading engine A–F | Ready |
| Ops control plane | Ready |
| 24/7 reliability platform | Ready |
| Chaos verification | Ready (unit) |
| SQL schemas for durability | Ready |
| Wire live Railway/Supabase/CF probes into tick | Operator / deploy |
| Flush in-memory reliability stores → SQL | Follow-up |
| Live canary under AutoTrading | Operator |
| **Phase H certification gate** | ✅ Required before LIVE |

---

### Phase E — Research Platform (met)

```
Historical bars → SimulationEngine (SimulationOmsPort)
                → TradeReplay / AnalyticsReport
                → WalkForward | MonteCarlo | GridSearch
                → StrategyVersionStore (append-only)
                → PromotionGate (Canary)
                → OperatorDashboard + /ite/research/*
```

**Horizons:** 1m · 3m · 6m · 1y · 2y · 5y  
**Replay speeds:** 1x · 2x · 5x · 10x · 100x + pause/resume/step  
**MC iterations:** 100 · 500 · 1000 · 5000 (seeded)  
**Optimization:** grid search → top 20 parameter sets  

#### Database schema (Phase E)

Tables (migration `20260720120000_ite_research_platform.sql`):

- `ite_research_simulations` — append-only runs (strategy/config version, input_hash, git_commit, metrics JSONB)
- `ite_research_trades` — trade payloads per simulation
- `ite_research_walkforward` / `ite_research_monte_carlo` / `ite_research_promotions` / `ite_research_optimizations`

#### Analytics schema

`AnalyticsReport`: win_rate, expectancy, profit_factor, average_rr, max_drawdown_pct, sharpe, sortino, calmar, recovery_factor, average_hold_seconds, best/worst session, win/loss streaks, mae_avg, mfe_avg, monthly_returns, equity_curve, pnl_distribution.

#### Promotion rules (Canary)

| Gate | Requirement |
|------|-------------|
| Min trades | ≥ 300 |
| Profit factor | > 1.50 |
| Max drawdown | < 10% |
| Expectancy | positive |
| Walk-forward | PASS |
| Monte Carlo | PASS |

### Phase E exit (met)

- Simulation determinism (same bars → same hash/metrics)  
- Replay controls  
- Walk-forward rolling/anchored without future leak  
- Seeded Monte Carlo  
- Analytics + trade replay  
- Grid optimization top-N  
- Promotion gate  
- Append-only versioning  
- OMS / Phase A–D unmodified  

### Phase F — Operations Control Plane (met)

```
Operator UI (/ops Control Center)
        ↓
Operations API (/ite/ops/*)
        ↓
OperationsControlPlane (modes · kill · config · health · alerts · audit)
        ↓
GuardedOmsSubmitPort / GuardedOmsManagePort  (no A–E edits)
        ↓
Execution Bridge / PME → OMS → Gateway → MT5
```

**Modes:** SHADOW → CANARY → LIVE → SHADOW (confirmation + audit required)  
**Kill switch:** Decision/Research/Sim continue; OMS orders=0; PME mods blocked  
**Config:** append-only versions with rollback target  
**Security:** OWNER/ADMIN only for LIVE, disarm kill, promote, rollback, risk  

#### Database schema (Phase F)

Migration `20260720140000_ite_operations_control_plane.sql`:

- `ite_ops_audit_log` (never delete)
- `ite_ops_config_versions` + `ite_ops_active_config`
- `ite_ops_alerts` / `ite_ops_mode_transitions` / `ite_ops_health_snapshots`

#### API specification (Phase F)

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/ite/ops/control-center` | Operator Control Center payload |
| GET | `/ite/ops/readiness` | Production readiness single page |
| POST | `/ite/ops/mode` | Mode transition (`confirmed` required) |
| POST | `/ite/ops/kill-switch/arm` \| `/disarm` | Kill switch |
| POST | `/ite/ops/config/promote` | Append config version |
| POST | `/ite/ops/rollback` | One-click rollback |
| POST | `/ite/ops/risk` | Risk parameter change |
| POST | `/ite/ops/health` | Push health inputs |
| GET/POST | `/ite/ops/alerts` · `/alerts/ack` | Alerts + acknowledge |
| GET | `/ite/ops/audit` | Audit log |
| GET | `/ite/ops/configs` | Config history |
| GET/POST | `/ite/ops/runbooks` · `/runbooks/{id}/execute` | Runbooks |

#### UI layout

`/ops` — Institutional Control Center (top): status grid · mode/kill/rollback controls · unacked alerts · runbooks · readiness panel; **Reliability panel** (Phase G); **Certification panel** (Phase H): scores · Go/No-Go · certificate · checklist; existing infra monitoring below. Command palette: “Operations control”.

### Phase F exit (met)

- Mode transitions + confirmation + audit  
- Kill switch blocks OMS + PME guards  
- Config versioning + rollback  
- Health monitoring + alerts with ack  
- Permissions (non-operator denied)  
- Runbooks  
- OMS / Phase A–E unmodified  

### Production readiness report

| Area | Status |
|------|--------|
| Analysis → Decision → Bridge → OMS | Ready |
| PME lifecycle | Ready |
| Research + promotion gate | Ready |
| Ops control plane + UI | Ready |
| Kill / shadow / canary / live | Ready |
| Append-only audit + config SQL | Schema ready |
| Live Windows MT5 canary under AutoTrading | Operator |
| Durable flush of in-memory ops store → SQL | Ops follow-up |
| Cloudflare / gateway probes wired to HealthInputs | Ops follow-up |

---

## 13. Observability & control plane

- **Decision journal:** every HOLD/ENTER with factors + fingerprint  
- **Execution diagnostics:** existing Validation → Risk → Gateway → `order_check` → `order_send`  
- **Management journal:** every BE/trail/partial/flatten with reason  
- **Kill switch:** Phase F ops kill switch + `EXECUTION_ENABLED` + risk halt  
- **Magic filter:** only manage positions tagged with ITE magic/comment prefix  
- **Ops audit:** every mode/kill/promote/rollback/risk change (append-only)  
- **Phase G reliability:** continuous health, heartbeats, trade traces (`trace_id`), incidents, recovery (no auto `order_send`), live metrics, notification adapters, chaos harness, searchable timeline  
- **Phase H certification:** E2E validation, canary metrics, live acceptance gate, stress, failure injection, Go/No-Go, production certificate, operator checklist  

---

## 14. Risks & mitigations

| Risk | Mitigation |
|------|------------|
| Duplicate scorers diverge | One ConfluenceEngine; deprecate parallel thresholds gradually |
| Overfitting ICT rules | Simulation + walk-forward before raising live risk % |
| OMS/MT5 rejects | Fail closed; humanize retcodes; never invent fills |
| Management vs broker stop level | Always re-read MT5 `stops_level` / `freeze_level` before SL modify |
| Analysis latency | Cache per-TF snapshots by bar open time; only recompute dirty TFs |

---

## 15. Acceptance criteria for “v1 complete”

1. XAUUSD-only path end-to-end in sim and live (gated).  
2. All ten capability areas implemented per sections 4–6.  
3. Identical bars + config → identical decisions in CI.  
4. Zero AI dependencies on the hot path.  
5. Every live order attributable in execution diagnostics.  
6. Trade management moves SL/TP/partials without manual UI.  
7. Analytics report WR, expectancy, PF, avg RR, max DD, Sharpe, daily PnL from engine trades only.

---

## 16. Defaults — approved 2026-07-20

Confirmed and locked in `ITEConfig` / architecture header:

1. Primary structure TF = **H1**, management TF = **M5**, macro = **H4**, entry = **M15**  
2. `min_confluence_score` = **80** (not 75)  
3. Max open XAU trades = **1**  
4. Partials: **1R → BE**, **2R → 50%**, **&gt;2R** trail (see header)  
5. Simulation fill model = **next bar open**  

Implementation proceeds Phase C → F without changing this architecture unless a new ADR is filed.

---

## Appendix A — Related documents

- `docs/adr/0007-analysis-pipeline.md`  
- `docs/adr/0008-*.md` (MarketAnalysisSnapshot)  
- `INSTITUTIONAL_EXECUTION_ENGINE.md`  
- `docs/market-structure.md`, `docs/liquidity.md`, `docs/order-block.md`  
- Gold-only: `app/domain/trading/gold_only.py`, `frontend/src/lib/trading/gold-only.ts`

## Appendix B — Why this is an “execution-quality” engine

Signal tools stop at confluence. ITE v1 owns:

- **Entry quality** (structure + liquidity + SMC + MTF gate)  
- **Risk quality** (sizing + daily/DD/streak halts)  
- **Fill quality** (existing OMS validation + MT5 specs)  
- **Lifecycle quality** (automated BE/trail/partials/time/emergency)  
- **Measurement quality** (analytics + simulation parity)

That is the production boundary for v1.
