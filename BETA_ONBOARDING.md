# Beta Onboarding

Closed Beta first-run path for QuantForg. Additive UX over existing desks — no architecture or UI redesign.

## Entrypoints

| Surface | Route / control |
|---------|-----------------|
| Invite gate | `NEXT_PUBLIC_BETA_MODE` + invite code |
| First-run checklist banner | Shell (dismissible) |
| Product tour | Dialog on first visit / Get Started |
| Get Started hub | `/get-started` |
| Broker wizard | `/get-started#broker` → Compatibility → `/mt5` |
| Paper tutorial | Card on `/paper` |
| Feedback | Floating widget + `/support#feedback` |
| Release notes | `/whats-new` |

## Recommended user path

1. Unlock closed beta (invite).  
2. Complete the first-run checklist.  
3. Take the product tour.  
4. Place a **paper** trade.  
5. Connect MT5 with the **exact** portal server (no simulated data).  
6. Send feedback.  
7. Read What’s New.

## Local persistence

Keys (browser only):

- `qf.onboarding.checklist.v1`
- `qf.onboarding.tour.dismissed.v1`
- `qf.onboarding.paper.tutorial.v1`
- `qf.onboarding.first_run.dismissed.v1`
- `qf.onboarding.release.seen.v1`

No `/settings` API changes.

## Safety reminders for beta users

- `EXECUTION_ENABLED` stays off unless operators explicitly enable it.  
- Paper ≠ live broker fills.  
- Certification / compatibility require real MT5 sessions.
