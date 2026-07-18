# Performance Budgets

**Status:** Binding  
**Parent:** [Design Bible](README.md)

## Feel

Everything must feel **instant**. Prefer lazy load, streaming where available, and zero layout shift.

## Budgets (frontend product)

| Metric | Budget | Notes |
|---|---|---|
| OS desk interaction | < 100ms perceived | Keyboard / panel focus |
| Motion duration | 180–220ms | `--duration-os` |
| Layout shift (CLS) | ≈ 0 on OS desks | Fixed chrome heights |
| Terminal chart load | Lazy; skeleton OK | `dynamic(..., { ssr: false })` |
| Large lists | Virtualize ≥ ~50 rows | See Terminal blotter pattern |
| Rerenders | Memo heavy panels; avoid prop thrash | No unnecessary Context blasts |
| Production bundle | No new large deps without justification | Prefer existing stack |

## Data

- Prefer React Query `staleTime` over aggressive polling when websockets exist.  
- Do not refetch entire desks on every keystroke.  
- Empty states cheaper than fabricating charts.

## Anti-patterns

- Loading entire legacy dashboards into OS shells  
- Unvirtualized 1k-row DOM tables  
- Animated chart replay on every tick  
- Blocking the main thread with sync JSON transforms on hot paths  

## Verification

- Production `next build` must succeed  
- Manual: Terminal / Book / Research / Counsel open with cold cache feel acceptable  
- Optional: Lighthouse on marketing pages only — OS desks judged by interaction feel
