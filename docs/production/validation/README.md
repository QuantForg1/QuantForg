# Production Validation Mode — Evidence Export

Observe-only execution evidence for natural eligible trades.

## Purpose

Capture a complete Validation ID package whenever the production strategy cycle runs:

- Signal / context fields (session, quality, confluence, MTF, risk, RR, spread, ATR, liquidity, OB, FVG, BOS, CHOCH)
- Full stage timeline (Scheduler → … → Position Close) with PASS/FAIL, timestamp, latency, reason
- Every NO_TRADE reason individually (never summarized)
- OMS payload / latency / response / retry count
- Gateway request / response / HTTP / latencies
- MT5 ticket / retcode / comment / fill / slippage

## Acceptance

A validation is **ACCEPTED** only when:

- Scheduler PASS
- Market PASS
- AI BUY or SELL
- Risk PASS
- OMS PASS
- Gateway PASS
- MT5 PASS
- Broker PASS
- Ticket created

Otherwise the report classifies the **first blocker only**.

## Hard rules

- Never weakens trading logic, quality thresholds, risk, safety, OMS, gateway, or MT5
- Never forces BUY/SELL
- Never fabricates evidence or paper trades
- Live dashboard: `/production-validation` and `GET /api/v1/ite/ops/production-validation-mode`

## Files

Auto-written per attempt:

- `*.json` — full evidence package
- `*.md` — human-readable report
- `*.csv` — stage rows
- `LATEST.json` / `LATEST.md` — most recent closed attempt
