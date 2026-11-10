# Twelve Data — public Live Market fallback

## Why

Public `/public/market/*` prefers the platform MT5 gateway. When the gateway is offline, QuantForg falls back to licensed **Twelve Data** OHLCV/quotes for `XAU/USD`.

## Railway variable (server-side only)

| Name | Required | Notes |
|---|---|---|
| `TWELVEDATA_API_KEY` | For fallback | Never put in frontend / Vercel `NEXT_PUBLIC_*` |

```bash
# From a machine that already holds the key in a secret store (do not paste into chat):
railway variables set TWELVEDATA_API_KEY=<paste-key-here> --service QuantForg
```

Redeploy the Railway API after setting the variable.

## Verify (no secret printing)

```bash
curl -sS "https://quantforg-production.up.railway.app/api/v1/public/market/status"
# expect: "twelvedata_configured": true

curl -sS "https://quantforg-production.up.railway.app/api/v1/public/market/candles/XAUUSD?timeframe=H1&count=5"
# when gateway down: status delayed, source twelvedata, non-empty candles
```

## Instrument / intervals

- Provider symbol: `XAU/USD` (from `XAUUSD` / `XAUUSD_i`)
- Intervals: M1, M5, M15, M30, H1, H4, D1, W1

## Security

- Key stays in Railway env only.
- API responses never echo the key.
- Frontend calls `/public/market/*` without the key.
