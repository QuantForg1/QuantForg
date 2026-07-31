# Manual License Purchase — UI Report

**Date:** 2026-07-31  
**Scope:** Frontend UI/UX only (RC4 dark theme preserved)  
**Objective:** QuantForg is not self-service. Customers contact sales; the team provisions licenses after payment verification.

---

## Summary

Public online checkout, self-serve registration, and self-serve password recovery were removed from the product UI. Purchase CTAs now route to a frontend-only **Contact Support** form. Accounts are not created through public registration flows.

---

## Removed registration paths

| Path / CTA | Change |
|---|---|
| `/register` | Redirects to `/contact` (no public registration form) |
| Landing / header “Create Account”, “Get Lifetime Access”, “Start Free”, etc. | Replaced with **Contact Sales** / **Contact Support to Purchase** |
| Login “Need access? Purchase…” | Replaced with support contact messaging |
| Marketing footer Register / Create Account / Reset password | Replaced with Contact Sales, Support, Documentation, Privacy, Terms |
| `go-live-landing.html` register-style CTAs | Updated to Contact Sales / Sign In |

---

## Removed payment methods / checkout

| Item | Change |
|---|---|
| `/purchase` mock checkout (card / Stripe / PayPal / crypto / bank placeholders) | Redirects to `/contact` |
| `/purchase/success` fake payment success | Redirects to `/contact/success` |
| Payment method selectors / demo checkout / success simulation | Removed from UI |
| Pricing “Pay Now” / “Get Lifetime Access” | Replaced with **Contact Support to Purchase** → `/contact` |
| Sticky purchase bar | Same CTA → `/contact` |

Price messaging retained on Pricing: **$2,499 · Lifetime License · One-Time Payment**.

---

## Contact form implementation

- **Route:** `/contact`
- **Success:** `/contact/success` (“Request Submitted”)
- **Style:** RC4 glass card (`.qf-glass-card`), dark theme, cyan accent
- **Backend:** None — client-side navigation only after submit
- **Fields:** Full Name, Company (optional), Country, Email, Phone / WhatsApp, Trading Experience, Broker (optional), Preferred Contact Method, Message
- **Checkbox:** Manual activation after payment verification
- **Primary button:** Request Purchase

Success page CTAs: **Contact Support**, **Back to Home** (no Create Account).

---

## Login simplification

- Sign In form only (email / password / remember me)
- **Removed:** Forgot password link
- **Replaced with:** “Need help accessing your account? Contact QuantForg Support” → `/contact`
- `/forgot-password` and `/reset-password` show support messaging (no self-serve reset UI; no API calls from those pages)

---

## Header & footer

**Header (landing + pricing chrome):**

- Primary: Contact Sales → `/contact`
- Secondary: Sign In → `/login`
- No Register

**Footer:**

- Contact Sales, Support, Documentation, Privacy, Terms
- Sign In retained under Sales
- No Register / Create Account / Reset password

---

## Responsive verification

- Contact form: single column on mobile; two-column field grids from `sm` breakpoint
- Sticky CTA uses safe-area padding and truncated price copy on narrow viewports
- Marketing header CTAs compress padding on small screens
- Success actions stack on mobile (`flex-col` → `sm:flex-row`)

---

## Systems not modified

Confirmed **unchanged** by this work:

- Backend services and APIs (including `authApi.register` / `forgotPassword` client wrappers left in place but unused by public UI)
- Authentication server logic / database / licensing business logic
- Trading Engine, AI Engine, OMS, MT5 Gateway
- Order execution, websockets, Supabase protocol
- Security and architecture beyond public marketing/auth **page UI** redirects

Only frontend marketing, auth page surfaces, pricing CTAs, contact flow, related CSS, and E2E expectations for those surfaces were updated.

---

## QA checklist

- [x] No online payment UI remains on marketing surfaces
- [x] No payment methods remain
- [x] No public registration CTAs remain
- [x] No Create Account button on purchase/success flows
- [x] No Forgot Password self-serve link on login
- [x] Login is Sign In only (+ support help link)
- [x] Pricing CTAs → Contact Support form
- [x] Contact form is responsive + RC4 branded
- [x] No backend / trading / OMS / MT5 / auth-logic / DB changes
