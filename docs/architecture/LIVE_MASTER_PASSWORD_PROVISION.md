# LIVE master trading password provisioning

Several LIVE accounts authenticate to the correct broker server with
`trade_mode=2`, but fail `trade_allowed` because an **investor / read-only**
password was provisioned.

| Broker | Observed LIVE server | Blocker |
|---|---|---|
| JustMarkets | `JustMarkets-Live7` | investor/read-only password |
| Exness | `Exness-MT5Real10` | investor/read-only password |

## Secure procedure (owner only)

Do **not** paste passwords into Cursor, ChatGPT, GitHub, Railway, or API responses.

1. Open the broker Personal Area in a private browser.
2. Confirm login + exact MT5 server name.
3. Copy the **master / trading** password (not investor).
4. On the Windows MT5 worker host only, edit gitignored
   `deploy/mt5_worker_agent/local.env`:

   ```text
   QF_LIVE_<BROKER>_LOGIN=...
   QF_LIVE_<BROKER>_PASSWORD=<master trading password>
   QF_LIVE_<BROKER>_SERVER=<exact observed server>
   ```

   Broker mid-names: `JUSTMARKETS`, `EXNESS`, `HFM`, `IC_MARKETS`, `FP_MARKETS`.

5. Presence check (no secret values printed):

   ```powershell
   .\deploy\mt5_worker_agent\check_broker_credentials.ps1
   ```

6. Portable verify (never Program Files Weltrade LIVE):

   ```powershell
   .\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker <slug> -Slot demo-a -Env live
   ```

7. Accept `VERIFIED_LIVE` only when `ok=true`, `trade_mode=2`, `trade_allowed=true`,
   broker identity matches, and `orders_submitted=false`.
