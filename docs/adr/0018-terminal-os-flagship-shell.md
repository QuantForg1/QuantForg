# ADR-0018: Terminal OS Flagship Shell

## Status

Accepted

## Context

Phase P1 requires one institutional Terminal: zero page scrolling, one
SessionBar, one chart surface, one order ticket, one Counsel strip, one
bottom blotter. Legacy WorkspaceShell stacked ConnectionBar, duplicate
account metrics, diagnostic blotter tabs (gateway/broker/system logs), and
limited keyboard coverage.

## Decision

**`/terminal` renders `TerminalShell` as the sole flagship trading surface.**

### Composition

| Surface | Component | Role |
|---|---|---|
| SessionBar | `terminal/session-bar.tsx` | Live / equity / free / float / sync |
| Counsel | `terminal/counsel-strip.tsx` | Always-on decision layer (not chatbot) |
| Watchlist | `workspace/left-rail.tsx` | Symbol selection (existing) |
| Chart | `workspace/chart-panel.tsx` | TradingView Lightweight Charts + MT5 candles |
| Ticket | `terminal/right-rail.tsx` → `ExecutionOrderTicket` | Unchanged submit path |
| Blotter | `terminal/blotter.tsx` | Positions, orders, history, journal only |

### Removed from trader Terminal chrome

- Gateway / broker / system / notification diagnostic tabs
- Duplicate account summary under the ticket (moved to SessionBar)
- Stacked ConnectionBar + per-panel status noise

### Preserved

- MT5 validate → risk → checklist → execution check → submit
- Real positions / orders / history via portfolio + session
- Realtime execution / notifications / activity streams
- Layout persistence (`qf.terminal.layout.v1`)

### Keyboard

B/S buy-sell · 1–4 blotter · [ ] rails · \\ blotter · C counsel · F fullscreen · Esc · ?

### Performance

- History and journal use windowed `VirtualList`
- Heavy panels remain dynamically imported on the route
- Counsel intelligence context is optional, stale 60s, never fabricated

## Consequences

**Positive** — One mental model; diagnostics out of the trading day; keyboard-first.

**Negative** — Position/order managers still use desk table pagination until densified further.

## References

- ADR-0016, ADR-0017
- `frontend/src/components/terminal/shell.tsx`
