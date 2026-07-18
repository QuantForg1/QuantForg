# ADR-0021: Counsel OS Decision Operating System

## Status

Accepted

## Context

AI, Quant AI, Decision Engine, and Intelligence were fragmented desks. Traders
need one Decision Operating System — not a chatbot, not a prompt box.
Terminal, Book, and Research (ADR-0018–0020) must not be modified.
Execution remains Terminal-only.

## Decision

**`/counsel` renders `CounselShell` — a zero-scroll Decision OS.**

### Merged into Counsel

AI · Quant AI · Decision Engine · Intelligence · Advisor concepts.

Legacy URLs redirect to `/counsel` (existing `next.config.ts` map).

### Original surfaces

| Component | Role |
|---|---|
| Decision Pulse | Stance / confidence / approval |
| Context Lens | DE analysis + MTF + market context |
| Recommendation Card | Action · Reason · Evidence · Confidence · Impact · Approval |
| Portfolio Impact | Live session + Quant AI modules |
| Decision Timeline | Paper recent + reports |
| Learning Memory | Paper performance + session analysis |
| Silence Protocol | First-class WAIT / hold / unavailable |

### Hard rules

1. Real Decision Engine / Quant AI / Intelligence / session data only.
2. Never fabricate recommendations or evidence.
3. Never submit orders — Evaluate is paper/advisory.
4. Default and error stance is WAIT (Silence Protocol).
5. Full-bleed via AppShell includes `/counsel`.

### Keyboard

1–7 focus · E evaluate · S silence · R refresh · ?

## Consequences

**Positive** — One decision surface; Silence is productized; Terminal remains execution.

**Negative** — Legacy Quant AI / DE page modules remain until cleanup.

## References

- ADR-0015 AI Is Advisor
- ADR-0016–0020
- `frontend/src/components/counsel/shell.tsx`
