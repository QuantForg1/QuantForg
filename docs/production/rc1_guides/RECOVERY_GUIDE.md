# QuantForg RC1 — Recovery Guide

1. Acknowledge incidents on Reliability desk.
2. Use gateway / MT5 recovery endpoints (`/ite/reliability/recovery/*`) — safe-read first.
3. Run position recovery from production hardening (observational sync).
4. Re-run RC1 smoke (never places orders) before re-enabling OMS.
5. Document incident with timeline export.
