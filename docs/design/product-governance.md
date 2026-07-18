# Product Governance

**Status:** Binding  
**Parent:** [Design Bible](README.md)

## Purpose

Keep QuantForg coherent as teams and surfaces scale. Product governance defines **what may change**, **who decides**, and **what is sacred**.

## Sacred surfaces (locked unless ADR + explicit ask)

| Surface | Path / tree | Rule |
|---|---|---|
| Terminal OS | `frontend/src/components/terminal/` | Do not modify casually; execution flagship |
| Book OS | `frontend/src/components/book/` | Do not modify casually |
| Research OS | `frontend/src/components/research/` | Do not modify casually |
| Counsel OS | `frontend/src/components/counsel/` | Do not modify casually |
| Backend contracts | APIs, DB schema, auth, gateway protocol | Never break silently |
| MT5 execution | Gateway + execution submit path | Preserve always |

Changes to locked surfaces require:

1. Clear product intent in the PR  
2. Reference to Design Bible + relevant ADR  
3. Full quality gate green  
4. Feature / component acceptance checklists completed  

## Decision rights

| Decision | Owner |
|---|---|
| New primary nav surface | Product + architecture ADR |
| New component in OS desks | Design Bible + Component Acceptance |
| Visual token change | Design Bible + tokens ADR/doc update |
| Backend contract change | Backend ADR + compatibility plan |
| AI autonomy / execution | **Forbidden** without superseding ADR-0015 |

## Product principles (governance)

1. **Workflows over pages** — design jobs, not screens.  
2. **Terminal executes; Counsel decides; Book understands; Research proves.**  
3. **Eight surfaces maximum** in primary nav (ADR-0016).  
4. **Delete aggressively** — duplication is a defect.  
5. **Real data or empty** — fabrication is a ship blocker.  
6. **Continuously releasable** — no long red branches (ADR-0017).

## Change control

```
Propose → Design Bible compliance → ADR if architectural
→ Implement behind releasable gate → Review checklists → Merge
```

Emergency hotfixes may skip Design Bible *expansions* but must not introduce:

- Mock trading data in production  
- New neon/gradient visual debt  
- Execution outside Terminal  
- Weakened TypeScript safety  

Follow up with a governance PR within one release cycle.
