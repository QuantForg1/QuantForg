# Typography Specification

**Status:** Binding  
**Implementation:** `frontend/src/app/layout.tsx` (IBM Plex Sans / Mono) + `globals.css`  
**Parent:** [Design Bible](README.md)

## Families

| Role | Font | CSS variable |
|---|---|---|
| UI / body | IBM Plex Sans | `--font-sans` |
| Display / titles | IBM Plex Sans (medium/semibold) | `--font-display` |
| Numbers / codes / tickets | IBM Plex Mono | `--font-mono` |

**Do not** introduce Inter, Roboto, Arial, or system-ui as the primary product face.

## Scale (only these)

| Token | Size | Typical use |
|---|---|---|
| `--text-display` | 2.5rem | Rare marketing — avoid on OS desks |
| `--text-title` | 1.75rem | Desk rare titles |
| `--text-heading` | 1.25rem | Section headings (`.qf-heading`) |
| `--text-body` | 0.875rem | Default body |
| `--text-label` | 0.75rem | Labels (`.qf-label`) |
| `--text-caption` | 0.6875rem | Captions (`.qf-caption`) |
| `--text-num-lg` | 1.5rem | Hero metrics |
| `--text-num` | 0.8125rem | Inline metrics |

Line heights: `--leading-*` paired tokens in `globals.css`.

## Numbers

- **Tabular figures everywhere** money, volume, price, PnL, latency  
- Prefer `font-mono` or `.tabular` / `tabular-nums`  
- Never let digits jump layout between updates  

## Hierarchy rules

1. One primary heading per panel.  
2. Labels muted; values stronger.  
3. Uppercase micro-labels sparingly — tracking controlled, not shouty.  
4. Do not invent ad-hoc `text-[13px]` scales when a token exists — extend tokens instead.
