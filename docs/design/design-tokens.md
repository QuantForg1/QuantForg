# Design Tokens Specification

**Status:** Binding  
**Source of truth:** `frontend/src/app/globals.css`  
**Parent:** [Design Bible](README.md)

## Rules

1. **Use CSS variables** — do not hard-code one-off hex in product UI.  
2. **Extend tokens in globals.css** — then document here.  
3. **No neon / atmosphere gradients** on product surfaces.  
4. Light and dark (`.light`) must both remain readable.

## Color (steel)

| Token | Role |
|---|---|
| `--bg` | App background |
| `--bg-elevated` | Chrome / rails |
| `--surface` / `--surface-2` / `--surface-3` | Panels |
| `--border` / `--border-strong` | Dividers |
| `--fg` / `--fg-muted` / `--fg-subtle` | Text hierarchy |
| `--accent` / `--accent-fg` / `--accent-soft` | Focus / primary action |
| `--success` / `--warning` / `--danger` (+ soft) | Status |
| `--buy` / `--sell` | Side semantics |
| `--ring` | Focus ring |

Forbidden in product UI: purple-on-white fintech gradients, glow stacks, cream+terracotta cliché themes as default brand.

## Spacing

Use `--space-1` … `--space-8` only for OS layout rhythm.

| Token | Value |
|---|---|
| `--space-1` | 0.25rem |
| `--space-2` | 0.5rem |
| `--space-3` | 0.75rem |
| `--space-4` | 1rem |
| `--space-5` | 1.5rem |
| `--space-6` | 2rem |
| `--space-7` | 3rem |
| `--space-8` | 4rem |

## Motion

| Token | Value | Use |
|---|---|---|
| `--duration-os` | 200ms | Default transitions (range 180–220ms) |
| `--ease-os` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Standard ease |

No decorative looping animations on trading desks.

## Elevation

`--shadow-card` / `--shadow-card-hover` default to **none**. Prefer border separation.

## Changing tokens

1. Propose in PR with before/after screenshots of Terminal + Book  
2. Update `globals.css` and this document together  
3. Verify light mode  
4. No regressions to contrast (see Accessibility)
