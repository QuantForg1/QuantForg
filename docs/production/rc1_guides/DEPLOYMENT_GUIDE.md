# QuantForg RC1 — Deployment Guide

1. Confirm Railway environment and secrets (names present; rotate via platform).
2. Confirm database / Supabase URL.
3. Deploy backend; verify `/health/live` and `/health/ready`.
4. Verify MT5 Gateway and broker session (read-only first).
5. Open RC1 desk → run checklist + smoke (no trades).
6. Enable limited live only after Go Live Score ≥ threshold **and** human approval.
