# JustMarkets — master trading password provisioning

**Status:** `JustMarkets-Live7` authenticated with `trade_mode=2`, but MT5 reported
`trade_allowed=false` (investor / read-only credentials). Not `VERIFIED_LIVE`.

## Secure procedure (owner only)

1. Open the JustMarkets **Personal Area** in a private browser window (not ChatGPT / Cursor chat).
2. Confirm the LIVE account login and the exact MT5 server (`JustMarkets-Live7` was observed).
3. Reset or copy the **master / trading** password (not the investor / read-only password).
4. On the Windows MT5 worker host only, edit gitignored:

   `deploy/mt5_worker_agent/local.env`

   Set (values never committed / never pasted into chat):

   ```text
   QF_LIVE_JUSTMARKETS_LOGIN=<account login>
   QF_LIVE_JUSTMARKETS_PASSWORD=<master trading password>
   QF_LIVE_JUSTMARKETS_SERVER=JustMarkets-Live7
   ```

5. Verify presence without printing secrets:

   ```powershell
   .\deploy\mt5_worker_agent\check_broker_credentials.ps1
   ```

6. Authenticate (portable `demo-a` only — never the Weltrade Program Files LIVE terminal):

   ```powershell
   .\deploy\mt5_worker_agent\verify_demo_broker.ps1 -Broker justmarkets -Slot demo-a -Env live
   ```

7. Accept only when the JSON shows `ok=true`, `trade_mode=2`, `trade_allowed=true`,
   server matching JustMarkets, and `orders_submitted=false`.

Do not paste passwords into Cursor, ChatGPT, GitHub, Railway logs, or API responses.
