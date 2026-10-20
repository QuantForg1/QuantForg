# QuantForg — Gold-Only Policy (XAUUSD)

## Purpose

QuantForg autonomous trading is locked to **Gold (`XAUUSD`)** and verified
broker spellings (typically `XAUUSD_i` / `XAUUSD_I`). This document describes
the policy, symbol mapping, analysis gates, risk behavior (including ~$50
accounts), configuration, and test coverage.

**This is not a profitability guarantee.** The system optimizes for decision
quality, risk-adjusted sizing, and capital preservation. Outcomes depend on
markets, broker conditions, and operator configuration.

## Source of truth

| Layer | Module | Role |
| --- | --- | --- |
| Backend policy | `app/domain/trading/gold_only.py` | `gold_only_enabled()`, `is_gold_symbol()`, `require_xauusd()` |
| Specs | `app/domain/trading/xauusd_specs.py` | Contract size, tick, volume min/step, max spread |
| Settings | `core/config/settings.py` | `EXECUTION_UNIVERSE_MODE`, `GOLD_ONLY_MODE`, `MULTI_SYMBOL_ENABLED` |
| Frontend | `frontend/src/lib/trading/gold-only.ts` | Desk selectors / watchlists / search clamp |
| Opportunity gates | `app/domain/trading/gold_opportunity_quality.py` | MTF / range / spread / session skip reasons |
| Intent parse | `parse_order_intent()` in institutional execution engine | Server-side non-Gold reject |

## Production finalize

When `APP_ENV=production`:

- `EXECUTION_UNIVERSE_MODE=GOLD_ONLY` → preserved; `gold_only_mode=true`, `multi_symbol_enabled=false`
- `EXECUTION_UNIVERSE_MODE=BROKER_DISCOVERED` → lifts gold clamp (explicit multi-market mode)
- Any other value → `FAIL_CLOSED` (empty live universe)

Default application setting is `GOLD_ONLY`.

## Symbol mapping

- Logical desk: `XAUUSD`
- Verified broker forms: `XAUUSD_i`, `XAUUSD_I`, and aliases in `gold_only` / frontend (`GOLD`, `XAUUSDM`, …)
- Non-Gold symbols are **rejected** via `DisabledAutonomousSymbolError` / `DISABLED_AUTONOMOUS_SYMBOL` — never silently remapped to Gold
- If the broker catalogue has no Gold symbol, diagnostics report unavailable; **do not trade**

## Analysis improvements (existing stack + quality gates)

Existing ITE / AI Scalping / M15 semantics / session / spread filters remain the
primary engines. `gold_opportunity_quality.assess_gold_opportunity` adds explicit
fail-safe skip reasons for:

- Multi-timeframe conflict
- Range-bound + false-breakout risk
- Spread above Gold ceiling (`xauusd_specs.MAX_SPREAD`)
- Session not allowed / abnormal volatility
- Stale data / missing candles
- Missing stop-loss / RR / duplicate signal
- Min-lot exceeding risk budget

`scan_setup_families` consumes these flags and will not select a setup when
hard skips fire; breakout family is dropped under false-breakout / range risk.

Confidence percentages are **not invented** — `confidence` is `null` unless a
measured outcome store supplies calibration.

## Risk controls (~$50 account)

Position sizing uses equity, stop distance, contract size (100), tick value,
lot step, and broker `volume_min` (0.01). Conservative defaults (e.g. 1% risk
per trade) mean:

- Min-lot dollar risk ≈ `0.01 × 100 × stop_distance`
- At `$50` equity and a typical Gold stop (~$18), min-lot risk (~$18) **exceeds**
  a 1% budget ($0.50) → **skip the trade** (do not force size, martingale, or grid)

Existing Risk Engine, daily loss limits, max exposure, kill switches, stale
price checks, and emergency stop remain intact. Never chase losses by upsizing.

Configurable via existing settings / ITE config (`risk_per_trade_pct`, daily
loss %, spread ceilings). Units: percent of equity unless documented otherwise
in ITE config.

## Execution safety (unchanged)

| Flag | Default | Scope |
| --- | --- | --- |
| Railway / API `EXECUTION_ENABLED` | `false` | Cloud order send |
| Local `MT5_GATEWAY_EXECUTION_ENABLED` | `false` | Windows Gateway mutation |

Both must be true for a live fill. Disabled execution surfaces
`ExecutionOutcome.DISABLED` / retcode `90001` **before** Risk min-lot sizing so
missing SL cannot mask the disabled gate.

## Tests

- `tests/unit/test_gold_only_autonomous_mode.py` — universe clamp, `require_xauusd`
- `tests/unit/test_execution_gateway.py` — disabled 403, idempotency with SL, non-Gold reject
- `tests/unit/test_gold_opportunity_quality.py` — quality gates + $50 min-lot
- `frontend/src/lib/trading/gold-only.test.ts` — Gold-only selectors
- Gateway suite — `MT5_GATEWAY_EXECUTION_ENABLED` fail-closed

## Backtesting

Where Research / Research Validation Platform infrastructure exists, evaluate
Gold with realistic spread, commission, slippage, and broker constraints, using
out-of-sample / walk-forward. This policy change does **not** claim a measured
expectancy improvement unless a reproducible report is attached.

## Production diagnostics (Gateway offline)

Screenshots showing **Gateway Offline**, **Broker NOT CONNECTED**, **Research
DEGRADED**, and empty Gold signals are consistent with an unreachable Windows
MT5 Gateway (tunnel/URL/process), not with a frontend-only Gold-only bug.

- Research APIs do not require a personal MT5 *login*, but live XAUUSD candles
  still require the Gateway → broker catalogue (`LIVE_BROKER`).
- There is currently **no independent OHLCV provider** for Gold in this repo
  (Finnhub/Polygon adapters cover news/calendar/sentiment only).
- Until Gateway health is green and MT5 is attached, research correctly reports
  **DEGRADED** with `degraded_reason=broker_catalogue_unavailable`.

Subsystem labels: `app/domain/trading/subsystem_status.py`.

## Remaining work before production approval

1. Operator confirmation of broker Gold spelling on the live account
2. Explicit product-owner restart of the Windows Gateway after guard deploys
3. Restore Gateway reachability (URL/tunnel/token) — separate from this code change
4. Keep both execution flags `false` until a controlled go-live checklist
5. Walk-forward backtest report for the active Gold strategy set (if required)
