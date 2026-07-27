# Institutional AI Scalping Engine v6.3 — Adaptive Scalping Mode

Keeps **v6.2** as the production directional baseline.

Does **not** redesign UI, replace AI, lower quality floors, raise risk, or force trades.

## Adaptive execution logic

1. **Market regime** (continuous): `strong_trend` · `weak_trend` · `range` ·
   `breakout` · `expansion` · `compression`
2. **Regime execution profile** adjusts hold / time-stop / trail / partial /
   cooldown **scale** only — never below `min_expected_rr` or past absolute max hold.
3. **Multi-setup scanner** scores families independently:
   - pullback continuation
   - BOS continuation
   - CHOCH reversal
   - liquidity sweep reversal
   - FVG continuation
   - breakout continuation  
   Failed families do **not** reject others. Highest-quality passer is selected.
4. **Adaptive cooldown** shortens in clean strong-trend / breakout tape; lengthens
   on weak spread, thin liquidity, compression, reject bursts, degraded execution.
5. **Hold window** target **2–15 minutes** (absolute max still configurable).
6. **Volatility collapse exit** flattens when live vol score collapses and edge is gone.

## Trade opportunity improvements

- More entries **only** when quality + confidence + structure + liquidity +
  spread + regime naturally agree.
- Shorter cooldowns under good conditions increase opportunity density
  without threshold dilution.
- Setup ranking surfaces the best local pattern without discarding the book.

## Market regime behaviour

| Regime | Hold / trail bias | Cooldown |
|---|---|---|
| strong_trend / breakout | Hold toward 2–15m; structure trail | Shorter when clean |
| weak_trend | Earlier partial; moderate hold | Slightly longer |
| expansion | Wider trail; capped hold; higher RR floor | Longer |
| range / compression | Fast scale-out; tight hold | Longer |

## Risk controls preserved

- Risk per trade, daily loss, drawdown, max open, exposure unchanged
- No martingale / grid / revenge trading
- Confidence / quality / RR / PA / spread floors unchanged or tighter via regime RR

## Learning

Records setup family, regime, entry/exit reason, R, MAE, MFE, hold, spread,
slippage, latency, rejection — with rolling `by_regime` / `by_setup_family` stats.

## Tests

`tests/unit/test_ai_scalping_v6_3_adaptive.py`
