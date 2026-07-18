# Feature Acceptance Checklist

**Status:** Binding  
**Parent:** [Design Bible](README.md) · [Feature Lifecycle](feature-lifecycle.md)

Use this checklist for **every product feature** (especially frontend OS desks).

## Product

- [ ] Stated job: which trading decision improves?  
- [ ] Mapped to one of the eight surfaces (or justified Settings/drawer)  
- [ ] Non-goals listed (no chatbot-as-core, no fake data, no new nav sprawl)  
- [ ] Complies with [UX Principles](ux-principles.md)  

## Architecture preserves

- [ ] Does not break MT5 execution  
- [ ] Does not change backend contracts without ADR + migration  
- [ ] Does not bypass auth  
- [ ] Counsel/Research/Book never place live orders  
- [ ] AI remains advisory (ADR-0015)  

## Quality gate

- [ ] `tsc --noEmit` clean  
- [ ] ESLint clean  
- [ ] Production build clean  
- [ ] Unit / CI tests green  
- [ ] No reduced type safety to “make it pass”  

## UX / a11y / perf

- [ ] Keyboard path documented (`?` or PR notes)  
- [ ] Empty / loading / error states  
- [ ] [Accessibility](accessibility.md) AA obligations met  
- [ ] [Performance Budgets](performance-budgets.md) respected  
- [ ] OS desks remain zero page-scroll where required  

## Components

- [ ] New components passed [Component Acceptance](component-acceptance-checklist.md)  
- [ ] No duplicated SessionBars / tickets / status systems  

## Docs

- [ ] Design Bible / ADR updated if architecture or tokens change  
- [ ] PR template sections completed  

## Sign-off

- [ ] Author  
- [ ] Reviewer  

**Fail any preserve or quality-gate item → do not merge.**
