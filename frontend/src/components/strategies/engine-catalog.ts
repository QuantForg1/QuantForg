/** Local mirror of the strategy engine plugins. The connected server wins when it returns the same key. */
export type EngineCatalogItem = {
  key: string;
  name: string;
  category: string;
  description: string;
  default_params: Record<string, unknown>;
};

export const ENGINE_CATALOG: EngineCatalogItem[] = [
  { key: "trend_following", name: "Trend Following", category: "trend", description: "Follow EMA slope direction using close prices only.", default_params: { ema_period: 50 } },
  { key: "ma_cross", name: "Moving Average Cross", category: "trend", description: "SMA fast/slow crossover.", default_params: { fast: 10, slow: 30 } },
  { key: "rsi", name: "RSI", category: "momentum", description: "RSI overbought/oversold thresholds.", default_params: { period: 14, oversold: 30, overbought: 70 } },
  { key: "macd", name: "MACD", category: "momentum", description: "MACD line cross of signal line.", default_params: { fast: 12, slow: 26, signal: 9 } },
  { key: "bollinger", name: "Bollinger", category: "mean_reversion", description: "Mean reversion at Bollinger band extremes.", default_params: { period: 20, num_std: 2 } },
  { key: "breakout", name: "Breakout", category: "breakout", description: "Close breaks N-bar high/low.", default_params: { lookback: 20 } },
  { key: "momentum", name: "Momentum", category: "momentum", description: "Rate-of-change momentum threshold.", default_params: { lookback: 10, threshold_pct: 0.5 } },
  { key: "mean_reversion", name: "Mean Reversion", category: "mean_reversion", description: "Revert toward SMA when deviation exceeds threshold.", default_params: { period: 20, deviation_pct: 1 } },
  { key: "custom_rules", name: "Custom Rules", category: "custom", description: "Rule tree over closes/SMA/RSI with explicit conditions.", default_params: { rsi_period: 14, sma_period: 20 } },
  { key: "donchian_breakout", name: "Donchian Breakout", category: "breakout", description: "Close breaks the prior N-bar high or low. The current bar is excluded from the channel.", default_params: { period: 20 } },
  { key: "stochastic", name: "Stochastic", category: "momentum", description: "Stochastic %K crosses %D from the oversold or overbought zone.", default_params: { k_period: 14, d_period: 3, oversold: 20, overbought: 80 } },
  { key: "cci", name: "CCI", category: "momentum", description: "Commodity Channel Index leaves the +/-100 zone back toward zero.", default_params: { period: 20, threshold: 100 } },
  { key: "williams_r", name: "Williams %R", category: "momentum", description: "Williams %R leaves oversold (-80) or overbought (-20).", default_params: { period: 14 } },
  { key: "adx_trend", name: "ADX Trend", category: "trend", description: "Buy when +DI is above -DI and ADX is at least the threshold. Sell on the opposite.", default_params: { period: 14, adx_min: 20 } },
  { key: "supertrend", name: "Supertrend", category: "trend", description: "ATR supertrend flips when close crosses the opposite band.", default_params: { period: 10, multiplier: 3 } },
  { key: "keltner_channel", name: "Keltner Channel", category: "breakout", description: "Close outside an EMA channel widened by ATR.", default_params: { period: 20, multiplier: 2 } },
  { key: "triple_ema", name: "Triple EMA", category: "trend", description: "Fast, mid, and slow EMAs are stacked in one direction.", default_params: { fast: 8, mid: 21, slow: 55 } },
  { key: "hull_trend", name: "Hull Trend", category: "trend", description: "Hull moving average slope and close on the same side.", default_params: { period: 16 } },
  { key: "aroon", name: "Aroon", category: "trend", description: "Aroon Up and Aroon Down show which extreme happened more recently.", default_params: { period: 25 } },
  { key: "awesome_oscillator", name: "Awesome Oscillator", category: "momentum", description: "5-period median-price average crosses the 34-period average.", default_params: { fast: 5, slow: 34 } },
  { key: "engulfing", name: "Engulfing", category: "price_action", description: "The latest candle body fully engulfs the previous opposite candle.", default_params: {} },
  { key: "pin_bar", name: "Pin Bar", category: "price_action", description: "A rejection wick at least twice the candle body, with the close in the rejection direction.", default_params: { wick_ratio: 2 } },
  { key: "inside_bar_breakout", name: "Inside Bar Breakout", category: "breakout", description: "After an inside bar, close breaks the mother bar high or low.", default_params: {} },
  { key: "rsi_pullback", name: "RSI Pullback", category: "trend", description: "RSI leaves 40 in the direction of the 50-period SMA.", default_params: { sma_period: 50, rsi_period: 14 } },
  { key: "bollinger_squeeze", name: "Bollinger Squeeze", category: "breakout", description: "Bandwidth was compressed, then close left the band.", default_params: { period: 20, num_std: 2, squeeze: 0.05 } },
  { key: "ichimoku", name: "Ichimoku", category: "trend", description: "Close is above the unshifted cloud and Tenkan is above Kijun, or the bearish mirror.", default_params: { tenkan: 9, kijun: 26, span: 52 } },
  { key: "heikin_ashi_trend", name: "Heikin Ashi Trend", category: "trend", description: "The last three Heikin Ashi candles agree on direction.", default_params: { bars: 3 } },
  { key: "linear_regression", name: "Linear Regression", category: "trend", description: "Ordinary least-squares slope of closes, with close on the same side of the mean.", default_params: { period: 20 } },
  { key: "zscore_reversion", name: "Z-Score Reversion", category: "mean_reversion", description: "Close z-score versus its SMA is beyond the threshold.", default_params: { period: 20, threshold: 2 } },
  { key: "nr7_breakout", name: "NR7 Breakout", category: "breakout", description: "The previous bar was the narrowest of seven, and the latest close breaks it.", default_params: {} },
  { key: "three_bar_reversal", name: "Three Bar Reversal", category: "price_action", description: "Two pushes one way, then a close through the prior bar in the other direction.", default_params: {} },
  { key: "gap_fill", name: "Gap Fill", category: "mean_reversion", description: "The open gaps away from the previous close and the latest close moves back toward it.", default_params: { min_gap_pct: 0.15 } },
  { key: "alligator", name: "Alligator", category: "trend", description: "Williams Alligator lips, teeth, and jaw are stacked.", default_params: { jaw: 13, teeth: 8, lips: 5, jaw_shift: 8, teeth_shift: 5, lips_shift: 3 } },
  { key: "vwap_reversion", name: "VWAP Reversion", category: "mean_reversion", description: "Close is stretched from volume-weighted average price. Holds when volume is missing.", default_params: { period: 20, threshold_pct: 0.3 } },
  { key: "obv_trend", name: "OBV Trend", category: "volume", description: "On-balance volume and close slope agree. Holds when volume is missing.", default_params: { period: 20 } },
  { key: "liquidity_sweep", name: "Liquidity Sweep", category: "price_action", description: "The latest wick takes the prior swing high or low and the close returns inside it.", default_params: { period: 20 } },
  { key: "fvg", name: "Fair Value Gap", category: "price_action", description: "A three-candle price gap, with the latest close still on the gap side.", default_params: {} },
  { key: "order_block", name: "Order Block", category: "price_action", description: "Price retests the last opposite candle before a directional close impulse.", default_params: { impulse_bars: 3 } },
  { key: "session_breakout", name: "Session Breakout", category: "breakout", description: "Close breaks the high or low of bars in the configured UTC hour window.", default_params: { start_hour: 7, end_hour: 16 } },
];
