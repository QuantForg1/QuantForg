# Micro Account Analyzer — Feasibility Report

- Generated: `2026-07-23T16:38:21.564212+00:00`
- Institutional Mode modified: **False**
- Strategy / OMS / Safety unchanged: **True**

## Broker specs

- Source: `live_broker` · min_lot=0.01 · step=0.01 · contract=100.0 · tick_size=0.001 · tick_value=0.10
- Standard min lot — not nano; current broker settings unchanged

## Selected analysis

- Balance: **$50**
- Risk %: **2%**
- ATR=9.7414 · Stop=14.6121 · Lots=0.00
- Eligible: **NO** (NOT ELIGIBLE)
- Reason: NOT ELIGIBLE: calculated lots 0.00 < broker min_lot 0.01. Min-lot stop-loss is $14.61 (29.22% of $50); selected risk 2% budget cannot fund a real lot without faking size or bypassing broker rules.

**$50 is NOT tradable on this broker for XAUUSD at ATR=9.7414 (stop=14.6121): NOT ELIGIBLE: calculated lots 0.00 < broker min_lot 0.01. Min-lot stop-loss is $14.61 (29.22% of $50); selected risk 2% budget cannot fund a real lot without faking size or bypassing broker rules.**

## Minimum safe balance (this broker)

| Risk % | Min safe balance | $ risk @ min_lot |
|---:|---:|---:|
| 0.25% | $5844.00 | $14.61 |
| 0.50% | $2922.00 | $14.61 |
| 0.75% | $1948.00 | $14.61 |
| 1.00% | $1461.00 | $14.61 |
| 1.50% | $974.00 | $14.61 |
| 2.00% | $730.50 | $14.61 |

## Supported balance matrix

| Balance | Status | Lots | Max loss | Reason |
|---:|---|---:|---:|---|
| $50 | NOT ELIGIBLE | 0.00 | $14.61 | NOT ELIGIBLE: calculated lots 0.00 < broker min_lot 0.01. Min-lot stop-loss is $14.61 (29.22% of $50); selected risk 2% budget cannot fund a real lot without faking size or bypassing broker rules. |
| $100 | NOT ELIGIBLE | 0.00 | $14.61 | NOT ELIGIBLE: calculated lots 0.00 < broker min_lot 0.01. Min-lot stop-loss is $14.61 (14.61% of $100); selected risk 2% budget cannot fund a real lot without faking size or bypassing broker rules. |
| $250 | NOT ELIGIBLE | 0.00 | $14.61 | NOT ELIGIBLE: calculated lots 0.00 < broker min_lot 0.01. Min-lot stop-loss is $14.61 (5.84% of $250); selected risk 2% budget cannot fund a real lot without faking size or bypassing broker rules. |
| $500 | NOT ELIGIBLE | 0.00 | $14.61 | NOT ELIGIBLE: calculated lots 0.00 < broker min_lot 0.01. Min-lot stop-loss is $14.61 (2.92% of $500); selected risk 2% budget cannot fund a real lot without faking size or bypassing broker rules. |
