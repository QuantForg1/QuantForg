# Certification Result — QuantForg Broker Verification

**Date:** 2026-07-13  
**Tester:** certification-engineer  
**Environment:** darwin (macOS) · `MT5_ENABLED=true` · `MT5_USE_MOCK=true` · `EXECUTION_ENABLED=false`  
**Live MT5 terminal:** **unavailable**  
**MetaTrader5 Python package:** **not installed**  
**Matched broker session:** **none**

## Gate rule

A broker is marked **Certified / PASS** only when every verification below succeeds against a **real** MT5 session for that brand.

**This run does not certify any broker.** Mock MT5 and simulated data were not used to produce PASS results.

## Platform probe

| Check | Result | Detail |
|-------|--------|--------|
| Real MT5 terminal present | FAIL | No live MetaTrader 5 process / `MetaTrader5` module |
| Live session connected | FAIL | Connectivity health → unavailable |
| `MT5_USE_MOCK` | FAIL (for certification) | `true` — mock path must not be treated as production certification |

---

## Weltrade (`weltrade`)

| Field | Value |
|-------|--------|
| **Overall** | **FAIL** |
| **Certified** | No |
| **Reason** | No live MT5 session — connect via `/mt5` with Weltrade credentials and exact portal server |
| **Latency** | n/a (not measured) |
| **Heartbeat** | n/a (not measured) |
| **Supported capabilities** | Documented MT5: connect, health, balances, positions, orders, history, symbols, quotes, candles, trading gate (via platform adapter) |

| Verification | Result | Reason |
|--------------|--------|--------|
| Connect (real credentials) | FAIL | No live session |
| Account sync | FAIL | No live session |
| Balances | FAIL | No live session |
| Equity | FAIL | No live session |
| Positions | FAIL | No live session |
| Pending orders | FAIL | No live session |
| History | FAIL | No live session |
| Symbols | FAIL | No live session |
| Quotes | FAIL | No live session |
| Candles | FAIL | No live session |
| Execution check | FAIL | No live session |
| Paper trading | FAIL | Paper engine not verified in a live certification context for this broker |

---

## XM (`xm`)

| Field | Value |
|-------|--------|
| **Overall** | **FAIL** |
| **Certified** | No |
| **Reason** | No live MT5 session — connect via `/mt5` with XM credentials and exact portal server |
| **Latency** | n/a (not measured) |
| **Heartbeat** | n/a (not measured) |
| **Supported capabilities** | Documented MT5 retail profile (same live path as platform MT5 adapter) |

| Verification | Result | Reason |
|--------------|--------|--------|
| Connect (real credentials) | FAIL | No live session |
| Account sync | FAIL | No live session |
| Balances | FAIL | No live session |
| Equity | FAIL | No live session |
| Positions | FAIL | No live session |
| Pending orders | FAIL | No live session |
| History | FAIL | No live session |
| Symbols | FAIL | No live session |
| Quotes | FAIL | No live session |
| Candles | FAIL | No live session |
| Execution check | FAIL | No live session |
| Paper trading | FAIL | No live certification context |

---

## Exness (`exness`)

| Field | Value |
|-------|--------|
| **Overall** | **FAIL** |
| **Certified** | No |
| **Reason** | No live MT5 session — connect via `/mt5` with Exness credentials and exact portal server |
| **Latency** | n/a (not measured) |
| **Heartbeat** | n/a (not measured) |
| **Supported capabilities** | Documented MT5 retail profile (same live path as platform MT5 adapter) |

| Verification | Result | Reason |
|--------------|--------|--------|
| Connect (real credentials) | FAIL | No live session |
| Account sync | FAIL | No live session |
| Balances | FAIL | No live session |
| Equity | FAIL | No live session |
| Positions | FAIL | No live session |
| Pending orders | FAIL | No live session |
| History | FAIL | No live session |
| Symbols | FAIL | No live session |
| Quotes | FAIL | No live session |
| Candles | FAIL | No live session |
| Execution check | FAIL | No live session |
| Paper trading | FAIL | No live certification context |

---

## IC Markets (`ic-markets`)

| Field | Value |
|-------|--------|
| **Overall** | **FAIL** |
| **Certified** | No |
| **Reason** | No live MT5 session — connect via `/mt5` with IC Markets credentials and exact portal server |
| **Latency** | n/a (not measured) |
| **Heartbeat** | n/a (not measured) |
| **Supported capabilities** | Documented MT5 retail profile (same live path as platform MT5 adapter) |

| Verification | Result | Reason |
|--------------|--------|--------|
| Connect (real credentials) | FAIL | No live session |
| Account sync | FAIL | No live session |
| Balances | FAIL | No live session |
| Equity | FAIL | No live session |
| Positions | FAIL | No live session |
| Pending orders | FAIL | No live session |
| History | FAIL | No live session |
| Symbols | FAIL | No live session |
| Quotes | FAIL | No live session |
| Candles | FAIL | No live session |
| Execution check | FAIL | No live session |
| Paper trading | FAIL | No live certification context |

---

## Pepperstone (`pepperstone`)

| Field | Value |
|-------|--------|
| **Overall** | **FAIL** |
| **Certified** | No |
| **Reason** | No live MT5 session — connect via `/mt5` with Pepperstone credentials and exact portal server |
| **Latency** | n/a (not measured) |
| **Heartbeat** | n/a (not measured) |
| **Supported capabilities** | Documented MT5 retail profile (same live path as platform MT5 adapter) |

| Verification | Result | Reason |
|--------------|--------|--------|
| Connect (real credentials) | FAIL | No live session |
| Account sync | FAIL | No live session |
| Balances | FAIL | No live session |
| Equity | FAIL | No live session |
| Positions | FAIL | No live session |
| Pending orders | FAIL | No live session |
| History | FAIL | No live session |
| Symbols | FAIL | No live session |
| Quotes | FAIL | No live session |
| Candles | FAIL | No live session |
| Execution check | FAIL | No live session |
| Paper trading | FAIL | No live certification context |

---

## Summary matrix

| Broker | PASS | FAIL | Certified |
|--------|------|------|-----------|
| Weltrade | — | **FAIL** | No |
| XM | — | **FAIL** | No |
| Exness | — | **FAIL** | No |
| IC Markets | — | **FAIL** | No |
| Pepperstone | — | **FAIL** | No |

**Certified brokers:** none  
**Pending / failed verification:** all five priority brokers  

## Operator actions to reach Certified

1. Provide a **Windows** host (or environment) with a real MetaTrader 5 terminal and `MetaTrader5` Python package.  
2. Set `MT5_USE_MOCK=false` and point `MT5_TERMINAL_PATH` at the live terminal.  
3. For each broker, connect via `/mt5` with **real** portal credentials and the **exact** server string.  
4. Run `POST /broker-connectivity/certification/run` (or `/broker-certification` → Run certification).  
5. Re-generate this report only from that live run — never from MockMT5.

## Integrity statement

No broker data was simulated for this certification attempt.  
No broker was marked Certified.  
Results reflect environment capability at the time of the run, not product defects in the certification workflow itself.
