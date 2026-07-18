# ADR-0020: Research OS Workflow Shell

## Status

Accepted

## Context

Quant Studio, Research Lab, Strategy, Backtesting, and Walk Forward were
separate desks that fragmented the research day. Traders need one operating
system that follows Idea → Observe → Validate → Backtest → Walk Forward →
Risk → AI Review → Promote — without imitating TradingView, MT5 Strategy
Tester, QuantConnect, or Bloomberg.

Terminal (ADR-0018) and Book (ADR-0019) must not be modified.

## Decision

**`/research` renders `ResearchShell` — a zero-scroll Research OS.**

### Merged into Research

Quant Studio · Strategy · Research Lab · Backtesting · Walk Forward ·
Optimization (as evidence/metrics) · Strategy Builder concepts (catalog DNA).

Legacy URLs redirect to `/research` (unchanged in `next.config.ts`).

### Original surfaces

| Component | Role |
|---|---|
| Promotion Pipeline | Stage chrome (1–8) |
| Strategy DNA | Catalog/library identity |
| Confidence Timeline | Stage confidence from real artifacts |
| Evidence Stack | Stored BT / WF / compare / library |
| Research Memory | Leaders, regime, paper preview |
| AI Review | Validation AI payload only |
| Promote Gate | `promotion/evaluate` eligibility → human to Terminal/Counsel |

### Hard rules

1. Advisory only — never submits orders.
2. No synthetic `sampleBars` runs from this shell; display stored API results.
3. Missing metrics → empty / `—`, never fabricated.
4. Promote is eligibility for Decision Engine, not live MT5 deploy.
5. Full-bleed via AppShell `OS_FULLBLEED_PATHS` includes `/research`.

### Keyboard

1–8 stages · V validate · P promote evaluate · A AI strip · R refresh · ?

## Consequences

**Positive** — One research workflow; clear handoff to Terminal/Counsel.

**Negative** — Legacy page modules remain in repo until cleanup; not primary UX.

## References

- ADR-0016–0019
- `frontend/src/components/research/shell.tsx`
