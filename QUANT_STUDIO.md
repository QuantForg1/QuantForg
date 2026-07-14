# Quant Studio V3.0 — Architecture & Production Readiness

## What it is

**Quant Studio** is QuantForg’s AI-assisted **research workspace**.

It is **not** MetaTrader, TradingView, or Bloomberg — and it is **not** a live trading bot.

- Visual strategy composition
- Backtest / walk-forward / Monte Carlo on **live MT5 OHLC**
- Advisory AI review + optimizer suggestions (never auto-applied)
- In-memory strategy marketplace (no schema migration)
- Portfolio lab + live monitor (read-only)

## Security

- Never `order_send`
- Never flips `EXECUTION_ENABLED`
- Never modifies broker / OMS / terminal state
- Never mutates locked Quant AI / execution / portfolio intelligence modules

## Architecture

```
/quant-studio
  → /api/v1/quant-studio/*
  → QuantStudioService
      ├─ MT5 candles (live)
      ├─ BacktestEngine (compose, not modify)
      ├─ WalkForwardEngine (compose, not modify)
      ├─ domain/quant_studio (builder, MC, review, optimizer, analytics, marketplace)
      └─ portfolio sync (read-only)
```

## Modules

1. Visual Strategy Builder  
2. Backtest Studio  
3. Walk Forward  
4. Monte Carlo  
5. AI Strategy Review  
6. AI Optimizer  
7. Strategy Marketplace  
8. Professional Analytics  
9. Portfolio Lab  
10. Live Strategy Monitor  

## Data policy

No mock / fake / demo / placeholder candles. Unavailable when MT5 disconnected.

Marketplace is **process-memory** (save / version / publish / clone / favorite) — no DB schema change.

## Performance

- Workspace TTL cache 20s
- React Query staleTime / background refresh per module
- Lazy equity charts
- Module-gated polling (portfolio / monitor only when active)
