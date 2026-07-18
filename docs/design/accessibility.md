# Accessibility Standards

**Status:** Binding  
**Parent:** [Design Bible](README.md)  
**Target:** WCAG 2.2 **AA** for product UI

## Must-have

| Requirement | Standard |
|---|---|
| Keyboard | All actions reachable without a mouse |
| Focus | Visible `:focus-visible` using `--ring` |
| Labels | Icon-only buttons have `aria-label` |
| Live regions | Session / decision status use `role="status"` / `aria-live` appropriately |
| Structure | Landmarks (`main`, `nav`, `application` on OS shells) |
| Contrast | Text/icon vs background meets AA |
| Motion | Respect `prefers-reduced-motion` for non-essential animation |
| Forms | Associated `<label>` or `aria-label` |
| Dialogs | Focus trap + Escape closes |
| Tables | Header cells; sortable controls announced |

## Trading-specific

- Confirm destructive closes / submits — never one-key silent live send without confirm path already established in Terminal.  
- Color is not the only signal for buy/sell/PnL — pair with text/sign.  
- Empty and error states must be readable by screen readers (`role="status"` / `role="alert"`).

## Forbidden

- Removing focus outlines without a visible replacement  
- Click-only critical flows with no keyboard equivalent  
- Low-contrast muted text for primary values  

## Review

Include a11y items from [Component Acceptance](component-acceptance-checklist.md) on every UI PR.
