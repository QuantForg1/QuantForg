# Feature Lifecycle

**Status:** Binding  
**Parent:** [Design Bible](README.md)

## Stages

```
Idea → Spec → Design → Build → Gate → Ship → Observe → Iterate | Retire
```

### 1. Idea

- State the trading decision it improves.  
- If it does not improve a decision → reject.  
- Map to one primary surface (Terminal / Book / Research / Counsel / …).

### 2. Spec

- User job + success metric  
- Data sources (real APIs only)  
- Empty / loading / error states  
- Keyboard path  
- Explicit non-goals (especially: no chatbots-as-product, no fake data)

### 3. Design

- Comply with UX Principles, Tokens, Typography, A11y, Performance budgets  
- Prefer existing OS components before inventing new ones  
- New components require [Component Acceptance](component-acceptance-checklist.md)

### 4. Build

- Preserve backend contracts and MT5 execution  
- Do not weaken types  
- No production mocks  

### 5. Gate

Must pass before merge:

| Check | Required |
|---|---|
| TypeScript `tsc --noEmit` | Yes |
| ESLint | Yes |
| Production build | Yes |
| Unit / CI tests | Yes |
| [Feature Acceptance](feature-acceptance-checklist.md) | Yes |
| Design Bible compliance | Yes |

### 6. Ship

- Continuously releasable (ADR-0017)  
- Feature flags only when risk requires; default path stays clean  

### 7. Observe

- Does it change trading decisions?  
- Latency / error rate / empty-state frequency  

### 8. Iterate or Retire

- Duplicate workflows → merge or delete  
- Unused chrome → remove  
- Retirement requires removing nav, redirects, and dead code — not hiding  

## Promotion across desks

| From | To | Rule |
|---|---|---|
| Research Promote | Counsel / Decision Engine | Eligibility only — never auto-execute |
| Counsel TRADE_IDEA | Terminal | Human opens Terminal; Counsel never submits |
| Book insight | Terminal | Link with symbol; no order from Book |

## Anti-patterns (reject)

- New top-level nav item beyond the eight surfaces  
- “Dashboard of dashboards”  
- Chatbot as the primary AI UX  
- Synthetic bars / demo equity in production paths  
- Diagnostic HTTP / gateway internals in trader chrome  
