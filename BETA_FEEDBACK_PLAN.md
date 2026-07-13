# Beta Feedback Plan

## Goals

Capture bugs, UX friction, and feature asks from Closed Beta users without changing core APIs.

## Channels

| Channel | How |
|---------|-----|
| In-app widget | Floating feedback control (category + message) |
| Support page | `/support#feedback` guidance + mailto |
| Email | `beta@quantforg.com` |

## Capture fields

- Category: bug / feature / general  
- Message  
- Optional email  
- Browser, build version, route, user id  
- Timestamp  

Stored locally (`qf.ops.feedback.v1`) and optionally POSTed to `NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL`.

## Triage cadence

| Cadence | Action |
|---------|--------|
| Daily | Scan new items; label P0 connectivity/auth bugs |
| Weekly | Theme synthesis; update What’s New if fixes ship |
| Biweekly | Share summary with product + infra |

## Severity guide

| Severity | Examples |
|----------|----------|
| P0 | Cannot login, data loss, unintended live trading |
| P1 | MT5 connect failures, paper order errors |
| P2 | Confusing copy, missing empty states |
| P3 | Polish / nice-to-have |

## Response SLA (target)

- P0: same day acknowledgment  
- P1: 2 business days  
- P2/P3: weekly batch  

## Do not

- Ask users for broker passwords in feedback forms  
- Treat mock MT5 as production certification evidence
