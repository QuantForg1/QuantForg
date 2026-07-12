# Risk Management Engine Report

**Status:** Complete  
**Scope:** Centralized **pre-execution** risk gate (before Execution Gateway)  
**Date:** 2026-07-12  

## Explicit non-goals (not started)

- Enabling `EXECUTION_ENABLED` (remains **false**)  
- Calling `order_send()`  
- AI  
- Strategy runtime  

Broker Foundation, MT5 Sprints 1–4, Execution Safety, Portfolio Engine, Auth, User Platform, Supabase, and CI are preserved.

---

## Summary

| Feature | Delivered |
|---------|-----------|
| Position sizing (fixed lot, fixed $, %, ATR, max lot cap) | Yes |
| Exposure engine (symbol / asset class / total / long-short) | Yes |
| Drawdown protection (daily / weekly / monthly / max DD / equity) | Yes |
| Correlation risk | Yes |
| Risk score 0–100 → LOW / MEDIUM / HIGH / BLOCKED | Yes |
| Decision: **ALLOW** / **REDUCE_SIZE** / **REJECT** only | Yes |
| Events: RiskApproved / RiskRejected / RiskReduced | Yes |
| `POST /api/v1/risk/check` | Yes |
| Persist assessments + RLS | Yes |
| Tests + CI green | Yes |

---

## Architecture

```
POST /api/v1/risk/check
        ↓
CheckRiskUseCase
        ↓
RiskEngine.evaluate
  sizing → exposure → drawdown → correlation → score → decision
        ↓
risk_assessments (history only)
```

Pipeline position relative to trading stack:

```
Risk Engine  →  Execution Safety  →  Execution Gateway (flag-gated)
```

**Never executes. Never enables `EXECUTION_ENABLED`.**

`RiskProfile` remains declared policy; the engine is an independent evaluator (ADR-0013).

---

## Modules

### 1. Position sizing

`RiskEngine.size_position()` — `fixed_lot` | `fixed_dollar_risk` | `percentage_risk` | `atr_based` + `max_lot` / `min_lot` caps.

### 2. Exposure

Margin-based exposure (notional / leverage) by symbol, asset class, total, long/short.

### 3. Drawdown protection

Daily / weekly / monthly loss % vs balance; max drawdown vs peak equity; equity protection flag.

### 4. Correlation

Grouped majors/JPY/metals/crypto; blocks excessive correlated exposure.

### 5–6. Score & decision

Score 0–100 → band; decision only `allow` | `reduce_size` | `reject`.

---

## API

| Method | Path | Returns |
|--------|------|---------|
| `POST` | `/api/v1/risk/check` | risk score, band, approved lots, decision, warnings, reasons, exposure, drawdown, checks |

---

## Database

| Migration | Purpose |
|-----------|---------|
| `20260712149000_risk_engine.sql` | `risk_assessments` |
| `20260712149100_risk_engine_rls.sql` | Owner RLS |
| Matching `down/*.down.sql` | Reversible |

**No credentials. No execution records.**

---

## Testing

`tests/unit/test_risk_engine.py` — fully mocked:

- Sizing / allow / reject (daily loss) / reduce (cap) / correlation  
- Use case persistence  
- Asserts `execution_enabled` stays false and adapter `order_send` remains disabled  

### Quality gates

```text
ruff check app core tests     → passed
black --check app core tests  → passed
mypy app core                 → passed
pytest                        → 261 passed, 2 skipped (~79% coverage)
```

---

## Stop line

This phase ends at the **Risk Management Engine**.

Do **not**:

- Enable live execution  
- Call `order_send()`  
- Implement AI  
- Implement strategies  
