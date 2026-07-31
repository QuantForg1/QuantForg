# Design Tokens Specification

**Status:** Binding  
**Source of truth:** `frontend/src/app/globals.css`  
**Parent:** [Design Bible](README.md)

## Rules

1. **Use CSS variables** — do not hard-code one-off hex in product UI.  
2. **Extend tokens in globals.css** — then document here.  
3. **No neon / atmosphere noise** on product surfaces — RC4 allows subtle cyan ambient gradients only.  
4. Light and dark (`.light`) must both remain readable.

## Color (RC4 — logo-derived charcoal + cyan)

| Token | Example | Role |
|---|---|---|
| `--bg` | `#111827` | App background (never pure black) |
| `--bg-elevated` | `#151B23` | Chrome / rails |
| `--surface` / `--surface-2` / `--surface-3` | `#1A2330` … `#283344` | Panels |
| `--border` / `--border-strong` | `#2F3B4D` … | Dividers |
| `--fg` / `--fg-muted` / `--fg-subtle` | white → muted | Text hierarchy |
| `--accent` | `#00D4E0` | Logo turquoise / primary |
| `--accent-gradient` | cyan → teal | Primary buttons (`.qf-btn-primary`) |
| `--accent-fg` / `--accent-soft` / `--accent-glow` | — | On-accent / soft / glow |
| `--success` / `--warning` / `--danger` (+ soft) | — | Status |
| `--buy` / `--sell` | — | Side semantics |
| `--ring` | cyan | Focus ring |
| `--bg-ambient` | soft radials | Page atmosphere (no grid) |

Brand assets: `frontend/public/brand/quantforg-mark.png` (official mark).

Forbidden in product UI: purple-on-white fintech gradients, heavy glow stacks, cream+terracotta cliché themes, hacker/gaming/crypto chrome.

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
| `--duration-fast` | 160ms | Hover / selection / cmd items |
| `--duration-os` | 200ms | Default transitions (range 180–220ms) |
| `--duration-slow` | 220ms | Status flashes / emphasis |
| `--ease-os` | `cubic-bezier(0.2, 0.8, 0.2, 1)` | Standard ease |
| `--ease-os-out` | `cubic-bezier(0.16, 1, 0.3, 1)` | Enter (dialog, palette, panels) |
| `--ease-os-in` | `cubic-bezier(0.4, 0, 1, 1)` | Exit |

### Utility classes

| Class | Role |
|---|---|
| `.qf-fade-in` / `.qf-motion-overlay` | Overlay / scrim |
| `.qf-motion-pop` | Centered dialog |
| `.qf-motion-slide-up` | Command palette / sheets |
| `.qf-motion-slide-down` | Tooltips / dropdowns |
| `.qf-motion-desk` | Workspace content enter |
| `.qf-panel-live` | Focused desk panel emphasis |

No decorative looping animations on trading desks. Always respect `prefers-reduced-motion`.

## Elevation

`--shadow-card` / `--shadow-card-hover` / `--shadow-elevated` provide soft institutional depth on charcoal. Prefer borders first; shadows second.

## Changing tokens

1. Propose in PR with before/after screenshots of Terminal + Book  
2. Update `globals.css` and this document together  
3. Verify light mode  
4. No regressions to contrast (see Accessibility)
