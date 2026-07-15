# Closed Beta Kit

Operator + invitee package for QuantForg Closed Beta.  
Core platform is **complete** — this kit does not add product modules.

**Baseline:** `9074a00` · Audit: `CLOSED_BETA_PRODUCTION_AUDIT.md` · Monitoring: `CLOSED_BETA_MONITORING.md`

---

## 1. Beta onboarding

See `BETA_ONBOARDING.md` for persistence keys and entrypoints.

**Invitee path (order):**

1. Open invite URL → enter invite code (`NEXT_PUBLIC_BETA_MODE`).  
2. Register / verify email → sign in.  
3. Open **Get Started** (`/get-started`) — complete checklist.  
4. Take the product tour.  
5. Place a **paper** trade (`/paper`).  
6. Connect MT5 only with the **exact** portal server via `/broker` (password stays on Windows gateway — attach/reconnect; never paste into support tickets).  
7. Explore advisory desks: Quant AI → Quant Studio → Decision Engine → Research Lab.  
8. Send feedback (`/support#feedback` or floating widget).  
9. Read **What’s New** (`/whats-new`).

**Safety copy for all invitees**

- Live `order_send` is **off** unless operators explicitly change policy (`EXECUTION_ENABLED`).  
- Paper results ≠ live broker fills.  
- Decision Engine default is **WAIT**.  
- Research Lab / Quant Studio / Quant AI never submit trades.

---

## 2. Quick start guide

| Goal | Where | Tip |
|------|-------|-----|
| See account health | `/dashboard` | Wait for SessionStrip before judging connectivity |
| Paper trade | `/paper` | Use tutorial card first run |
| Connect broker | `/broker` | Prefer session attach; avoid password in browser |
| Terminal | `/workspace` | Same session as Broker Workspace |
| OMS / journal | `/execution` | Lifecycle is observable; still gated by execution flag |
| Ask “should we trade?” | `/decision-engine` | Expect WAIT often — by design |
| Backtest ideas | `/quant-studio` | MT5 OHLC only when connected |
| Compare strategies | `/research-lab` | Validate → Compare → Promotion eligibility only |
| Ops / gateways | `/ops` `/cloud-ops` | Owner/admin |

**5-minute smoke (operator):** login → Get Started → paper → Decision Engine WAIT badge → Research Lab modules → Support feedback → logout.

---

## 3. FAQ

**Q: Can I place live trades in Closed Beta?**  
A: No by default. Production forces `EXECUTION_ENABLED=false`. Treat the beta as paper + research.

**Q: Why is Decision Engine stuck on WAIT?**  
A: Capital preservation. WAIT is the default unless score and risk gates open a paper TRADE_IDEA.

**Q: Why does Research Lab say a strategy is an “archetype”?**  
A: Some library entries (liquidity sweep, FVG, etc.) are research metadata until an OHLC plugin exists — metrics are not invented.

**Q: Where do my broker passwords go?**  
A: Windows MT5 gateway memory only for reconnect. Never Railway, never `localStorage`, never feedback forms.

**Q: Chart / quotes unavailable?**  
A: Confirm gateway heartbeat on `/cloud-ops`, broker session on `/broker`, then refresh the desk. Empty/unavailable is honest — we do not mock ticks.

**Q: How do I report a bug?**  
A: See §7 Issue reporting. Include route, UTC time, and build from Support/version — never passwords.

**Q: Is invite code encryption-grade security?**  
A: No — it is an operator cohort gate. Auth remains JWT on the API.

---

## 4. Known limitations

1. Live execution disabled for beta cohort.  
2. Auth tokens stored in browser `localStorage` (XSS residual).  
3. Auth rate limiting is per-process (multi-replica best-effort).  
4. Some desks lack `DeskEmpty` polish (wallet, settings, broker custom errors).  
5. Playwright does not yet cover every route (ops, wallet, full OMS).  
6. Cross-region DB latency can add ~180–220ms to probes.  
7. No dedicated `/admin` UI — use `/ops`.  
8. Research archetypes without engine plugins cannot run OHLC validation.  
9. External pager/Slack for ops alerts is optional, not mandatory.  
10. Chaos/failover drills are operator runbook-driven, not automated in CI.  
11. **Trading Ecosystem (`/ecosystem`) data is process-memory** — journal, playbooks, watchlists, workspaces, alerts, learning progress, preferences, and sync bundles live in API process RAM and **may reset after an API restart** (no durable DB schema in Closed Beta). Export a sync bundle before planned restarts when possible.

---

## 5. Release notes (Closed Beta cut)

**Included in baseline `9074a00` (highlights since core beta packaging):**

- Institutional Execution Engine + observability.  
- Quant AI V2 (advisory).  
- Quant Studio V3 (research workspace).  
- Decision Engine V4 (WAIT-biased gate).  
- Quant Research Lab V5 (library, validation, promotion eligibility).  
- Trading Ecosystem (`/ecosystem`) — journal, playbooks, coach, watchlists, workspaces, alerts, learning, reports, prefs, cloud sync (**process-memory; may reset on API restart**).  
- Closed Beta onboarding / invite / maintenance / read-only gates.  
- Weltrade + MT5 Gateway attach/reconnect path.

**Explicitly unchanged for this kit:** locked desks listed in the production audit — no schema or API freeze breaks.

Update `/whats-new` curated UI when tagging the beta build.

---

## 6. Feedback form

Use existing channels (no new API):

| Channel | Mechanism |
|---------|-----------|
| In-app | Floating feedback widget (bug / feature / general) |
| Support | `/support#feedback` |
| Email | `beta@quantforg.com` |
| Optional | `NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL` |

Captured: category, message, optional email, browser, build, route, user id, timestamp.  
Local ring: `qf.ops.feedback.v1`. Full process: `BETA_FEEDBACK_PLAN.md`.

**Never** request broker passwords or gateway tokens in feedback.

---

## 7. Issue reporting guide

1. **Reproduce** once; note UTC timestamp and route.  
2. Capture **build/version** from Support or `/api/v1` version endpoint.  
3. Severity:  
   - **P0** — cannot login, data loss, any unintended live send  
   - **P1** — MT5 connect / paper / gateway failures  
   - **P2** — confusing UX / missing empty states  
   - **P3** — polish  
4. Attach screenshots **without** account numbers if possible; redact tickets.  
5. File via feedback widget or email with subject `[Beta][P0|P1] short title`.  
6. Operators triage daily (`BETA_OPERATIONS.md`).

---

## Related documents

- `BETA_ONBOARDING.md` · `BETA_CHECKLIST.md` · `BETA_OPERATIONS.md` · `BETA_FEEDBACK_PLAN.md`  
- `OPERATIONS_RUNBOOK.md` · `SECURITY.md` · `GATEWAY_DEPLOYMENT.md`  
- `CLOSED_BETA_PRODUCTION_AUDIT.md` · `CLOSED_BETA_MONITORING.md`
