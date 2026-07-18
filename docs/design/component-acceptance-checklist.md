# Component Acceptance Checklist

**Status:** Binding  
**Parent:** [Design Bible](README.md)

Use this checklist for **every new or substantially redesigned component**.

Copy into the PR when introducing UI under `frontend/src/components/`.

## Intent

- [ ] Improves a trading decision (or is pure infrastructure chrome)  
- [ ] Belongs to one clear desk or shared system (`ui/`, `broker/`, desk OS)  
- [ ] Does not duplicate an existing component (search first)  
- [ ] Not a competitor clone  

## Design system

- [ ] Uses Design Tokens (no rogue hex / random spacing)  
- [ ] Typography tokens / IBM Plex only  
- [ ] No neon, glow stacks, or atmosphere gradients  
- [ ] Motion ≤ 220ms and purposeful  

## Data honesty

- [ ] Real API / session data only (or empty)  
- [ ] Empty / loading / error states implemented  
- [ ] Never fabricates prices, balances, trades, or AI text  

## Interaction

- [ ] Keyboard operable  
- [ ] Focus visible  
- [ ] `aria-*` / labels correct  
- [ ] Works in light and dark if both themes apply  

## Engineering

- [ ] TypeScript-safe (no `any` escapes to ship)  
- [ ] Memoized if hot-path / list-heavy  
- [ ] No layout shift when data arrives  
- [ ] Does not submit orders unless inside Terminal execution path  

## Review sign-off

- [ ] Author self-checked  
- [ ] Reviewer confirmed Design Bible compliance  

**Fail any critical item → do not merge.**
