export type StrategyBrief = {
  concept: string;
  works: string;
  usage: string;
  traits: string[];
};

/** Written from the strategy plugin rules. No performance claims. */
export const STRATEGY_BRIEFS: Record<string, StrategyBrief> = {
  trend_following: {
    concept: "Follow the slope of an exponential moving average of the close.",
    works:
      "A buy intention appears when the EMA is rising and the close is above it. A sell intention appears when the EMA is falling and the close is below it. Any other alignment holds.",
    usage:
      "Set the EMA length. The default is 50. Evaluate reads the candles you supply, or broker candles when the connection can load them.",
    traits: ["Uses closes only", "Needs enough bars to build the EMA", "Holds when price and slope disagree"],
  },
  ma_cross: {
    concept: "A fast simple moving average crossing a slower one.",
    works:
      "A buy intention appears on the bar where the fast SMA crosses above the slow SMA. A sell intention appears on the opposite cross. If the averages do not cross on the latest bar, the result is hold.",
    usage: "Defaults are fast 10 and slow 30. The slow length must stay longer than the fast length.",
    traits: ["Uses closes only", "Signals on the crossing bar", "Staying apart is not a new signal"],
  },
  rsi: {
    concept: "The relative strength index at an oversold or overbought level.",
    works:
      "A buy intention appears when RSI is at or below the oversold level. A sell intention appears when RSI is at or above the overbought level. A reading between the two levels holds.",
    usage: "The default period is 14, with oversold at 30 and overbought at 70. Oversold must stay below overbought, and both must sit between 0 and 100.",
    traits: ["Oscillator fade", "The middle of the range produces no intention", "Uses closes only"],
  },
  macd: {
    concept: "The MACD line crossing its signal line.",
    works:
      "A buy intention appears when MACD crosses above the signal. A sell intention appears when it crosses below the signal. No cross means hold.",
    usage: "Defaults are fast 12, slow 26, and signal 9. The fast length must be shorter than the slow length.",
    traits: ["Uses closes only", "The decision is the cross", "A line that stays above the signal is not a new buy"],
  },
  bollinger: {
    concept: "A close stretched to a Bollinger band.",
    works:
      "A buy intention appears when the close is at or below the lower band. A sell intention appears when the close is at or above the upper band. A close inside the bands holds.",
    usage: "The default is a 20-bar average and 2 standard deviations.",
    traits: ["Mean reversion at the band", "It does not wait for price to return inside", "Uses closes only"],
  },
  breakout: {
    concept: "The close leaving the high or low of the previous bars.",
    works:
      "The current bar is left out of the range. A buy intention appears when the close is above that prior high. A sell intention appears when the close is below that prior low.",
    usage: "The lookback default is 20 bars.",
    traits: ["Breakout of the prior range", "Price inside the range holds", "The current bar does not count in the range"],
  },
  momentum: {
    concept: "The percentage rate of change of the close.",
    works:
      "A buy intention appears when momentum is at least the threshold. A sell intention appears when it is at or below the negative threshold. A move inside that band holds.",
    usage: "The default lookback is 10 bars and the default threshold is 0.5 percent.",
    traits: ["Directional", "Small moves inside the band are ignored", "Uses closes only"],
  },
  mean_reversion: {
    concept: "The close stretched a set percent away from its simple moving average.",
    works:
      "A buy intention appears when the close is at least that percent below the average. A sell intention appears when it is at least that percent above. A close near the average holds.",
    usage: "The default average is 20 bars and the default deviation is 1 percent.",
    traits: ["Fades an extension from the average", "No second indicator is required", "Uses closes only"],
  },
  custom_rules: {
    concept: "An ordered list of conditions on close, RSI, or SMA.",
    works:
      "Rules are checked from top to bottom. The first matching condition returns its action. If none match, the result is hold.",
    usage:
      "Each rule needs a condition and an action of buy, sell, exit, or hold. The default list buys RSI at or below 30 and sells RSI at or above 70.",
    traits: ["Only the indicators named in the rules are read", "Order matters", "An empty rule list is invalid"],
  },
  donchian_breakout: {
    concept: "The close breaking the highest high or lowest low of the previous bars.",
    works:
      "The current bar is excluded from the channel. A buy intention appears above that high. A sell intention appears below that low. A close inside the channel holds.",
    usage: "The channel length default is 20 bars.",
    traits: ["Breakout", "The current bar is not part of the channel", "No volume is required"],
  },
  stochastic: {
    concept: "Stochastic %K crossing %D after an extreme reading.",
    works:
      "A buy intention appears when %K crosses up through %D and the previous %K was at or below the oversold level. A sell intention appears on the down cross from the overbought level. A cross in the middle holds.",
    usage: "Defaults are %K 14, %D 3, oversold 20, and overbought 80.",
    traits: ["The extreme zone is required", "A mid-range cross is ignored", "Needs enough bars to build %D"],
  },
  cci: {
    concept: "The commodity channel index leaving an extreme and moving back toward zero.",
    works:
      "A buy intention appears when CCI crosses back above the negative threshold. A sell intention appears when it crosses back below the positive threshold. Staying beyond the line, or never reaching it, holds.",
    usage: "The default period is 20 and the default threshold is 100.",
    traits: ["Signals the exit from the extreme", "Typical price is high, low, and close", "A reading still beyond the line holds"],
  },
  williams_r: {
    concept: "Williams %R leaving oversold or overbought.",
    works:
      "A buy intention appears when %R crosses up through -80. A sell intention appears when it crosses down through -20. A reading that stays between those levels holds.",
    usage: "The period default is 14. The -80 and -20 levels are part of the rule.",
    traits: ["Fixed extreme levels", "It waits for the leave, not the arrival", "A flat range is treated as neutral"],
  },
  adx_trend: {
    concept: "Trade only when directional strength is high enough, and take the side of the stronger DI.",
    works:
      "If the latest directional reading is below the minimum, the result is hold. Otherwise a buy intention appears when +DI is above -DI, and a sell intention appears when -DI leads.",
    usage: "The default period is 14 and the default minimum is 20.",
    traits: ["A weak reading holds", "Direction comes from +DI and -DI", "Equal DI values hold"],
  },
  supertrend: {
    concept: "An ATR band that flips when the close crosses to the other side.",
    works:
      "The plugin walks the candles and keeps an up or down state. Once enough bars exist, an up state is a buy intention and a down state is a sell intention.",
    usage: "The default ATR period is 10 and the default multiplier is 3.",
    traits: ["Needs the period plus three bars", "Returns the current band direction", "Uses high, low, and close"],
  },
  keltner_channel: {
    concept: "A close outside an exponential-average channel widened by ATR.",
    works:
      "A buy intention appears above the upper band. A sell intention appears below the lower band. A close inside the channel holds.",
    usage: "The default average is 20 bars and the default ATR multiplier is 2.",
    traits: ["Breakout of the channel", "It does not fade the band", "The average must be ready"],
  },
  triple_ema: {
    concept: "Three exponential averages stacked in one direction.",
    works:
      "A buy intention appears when the fast average is above the middle and the middle is above the slow. A sell intention appears on the opposite stack. Any other order holds.",
    usage: "Defaults are 8, 21, and 55. Each faster length must stay shorter than the next.",
    traits: ["The stack is enough", "A cross is not required", "Uses closes only"],
  },
  hull_trend: {
    concept: "The Hull moving average slope agrees with the close.",
    works:
      "A buy intention appears when the Hull average is rising and the close is above it. A sell intention appears when it is falling and the close is below it. Disagreement holds.",
    usage: "The period default is 16.",
    traits: ["Slope and close must agree", "Needs the period plus its square-root length", "Uses closes only"],
  },
  aroon: {
    concept: "Which extreme, the high or the low, printed more recently.",
    works:
      "A buy intention appears when Aroon Up is at least 70 and Aroon Down is at most 30. A sell intention appears on the mirror. A mixed reading holds.",
    usage: "The period default is 25.",
    traits: ["Recency of the high and the low", "Both sides must agree", "No moving-average cross"],
  },
  awesome_oscillator: {
    concept: "The spread between a fast and a slow average of median price crossing zero.",
    works:
      "A buy intention appears when the oscillator crosses from zero or below to above zero. A sell intention appears on the opposite cross. Staying on one side of zero holds.",
    usage: "Defaults are a 5-bar and a 34-bar average of (high + low) / 2. The fast length must be shorter.",
    traits: ["Median price, not the close alone", "Only the zero cross is a signal", "Uses high and low"],
  },
  engulfing: {
    concept: "The latest candle body fully covers the previous candle of the opposite color.",
    works:
      "A bullish engulfing candle is a buy intention. A bearish engulfing candle is a sell intention. A partial overlap holds.",
    usage: "There are no parameters. Two candles are required.",
    traits: ["The previous candle must be the opposite color", "The body must cover the prior body", "One candle pair only"],
  },
  pin_bar: {
    concept: "A rejection wick at least a set multiple of the candle body, with the close in the rejection direction.",
    works:
      "A long lower wick and a close at or above the open is a buy intention. A long upper wick and a close at or below the open is a sell intention.",
    usage: "The wick multiple default is 2.",
    traits: ["A candle with no range holds", "The opposite wick must stay small", "Uses the latest candle only"],
  },
  inside_bar_breakout: {
    concept: "A bar contained by the prior bar, then a close through that mother bar.",
    works:
      "The middle bar must sit inside the mother bar. The latest close above the mother high is a buy intention. The latest close below the mother low is a sell intention.",
    usage: "There are no parameters. Three bars are required.",
    traits: ["The middle bar must be contained", "The break is the close, not only a wick", "A bar that is not inside holds"],
  },
  rsi_pullback: {
    concept: "RSI turning back in the direction of the simple moving average.",
    works:
      "A buy intention appears when the close is above the average and RSI crosses up through 40. A sell intention appears when the close is below the average and RSI crosses down through 60.",
    usage: "The average default is 50 and the RSI period default is 14. The 40 and 60 levels are part of the rule.",
    traits: ["Trend and oscillator together", "A dip below the average is not bought", "Uses closes only"],
  },
  bollinger_squeeze: {
    concept: "A compressed Bollinger bandwidth, then a close outside the band.",
    works:
      "The previous bar's bandwidth must be at or below the squeeze ratio. A close above the current upper band is then a buy intention. A close below the lower band is a sell intention.",
    usage: "Defaults are period 20, 2 standard deviations, and a squeeze ratio of 0.05.",
    traits: ["Compression is required first", "An ordinary band touch without a squeeze holds", "Uses closes only"],
  },
  ichimoku: {
    concept: "Price versus an unshifted cloud, with Tenkan compared with Kijun.",
    works:
      "A buy intention appears when the close is above the cloud and Tenkan is above Kijun. A sell intention appears when the close is below the cloud and Tenkan is below Kijun. Price inside the cloud holds.",
    usage: "Defaults are Tenkan 9, Kijun 26, and span 52.",
    traits: ["The cloud is not shifted forward", "Both price and Tenkan/Kijun must agree", "Uses high, low, and close"],
  },
  heikin_ashi_trend: {
    concept: "Several reconstructed Heikin Ashi candles of the same color.",
    works:
      "A buy intention appears when each of the last requested candles closes above its Heikin Ashi open. A sell intention appears when each closes below. One disagreement holds.",
    usage: "The default count is 3 candles.",
    traits: ["Reconstructed candles, not the raw print", "Every candle in the window must agree", "Uses open, high, low, and close"],
  },
  linear_regression: {
    concept: "The least-squares slope of recent closes, confirmed by the close versus their mean.",
    works:
      "A buy intention appears when the slope is positive and the close is above the window mean. A sell intention appears when the slope is negative and the close is below the mean. Disagreement holds.",
    usage: "The window default is 20 closes.",
    traits: ["Slope alone is not enough", "The close must sit on the same side of the mean", "Uses closes only"],
  },
  zscore_reversion: {
    concept: "How many standard deviations the close sits from its window mean.",
    works:
      "A buy intention appears at or below the negative threshold. A sell intention appears at or above the positive threshold. A score inside the band holds. A zero standard deviation holds.",
    usage: "The default window is 20 and the default threshold is 2.",
    traits: ["A fade of a stretch", "A flat window cannot be scored", "Uses closes only"],
  },
  nr7_breakout: {
    concept: "The previous bar was the narrowest of seven, and the new close breaks that bar.",
    works:
      "If the previous range is not the smallest of those seven, the result is hold. Otherwise a close above its high is a buy intention and a close below its low is a sell intention.",
    usage: "There are no parameters. Eight bars are required.",
    traits: ["The narrow bar is the range", "A wide previous bar is ignored", "The break is the latest close"],
  },
  three_bar_reversal: {
    concept: "Two closes in one direction, then a close through the middle bar the other way.",
    works:
      "A buy intention appears when the second close is below the first and the third close is above the second high. A sell intention appears on the mirror.",
    usage: "There are no parameters. Three bars are required.",
    traits: ["A reversal pattern", "The third close must clear the middle bar", "Two pushes without the break hold"],
  },
  gap_fill: {
    concept: "The open gaps away from the previous close, and the same candle moves back toward it.",
    works:
      "A gap up of at least the minimum percent, with a close below the open, is a sell intention. A gap down of that size, with a close above the open, is a buy intention.",
    usage: "The minimum gap default is 0.15 percent.",
    traits: ["The fade must happen on the gap candle", "A gap that continues holds", "Needs the previous close"],
  },
  alligator: {
    concept: "Three shifted averages — lips, teeth, and jaw — stacked in one direction.",
    works:
      "A buy intention appears when lips are above teeth and teeth are above the jaw. A sell intention appears on the opposite stack. Tangled lines hold.",
    usage: "Defaults are jaw 13 shifted 8, teeth 8 shifted 5, and lips 5 shifted 3.",
    traits: ["The published shifts are applied", "A partial stack is not a signal", "Uses closes only"],
  },
  vwap_reversion: {
    concept: "The close stretched away from the volume-weighted typical price.",
    works:
      "A buy intention appears when the close is at least the threshold percent below VWAP. A sell intention appears when it is that far above. Missing volume, or volume that is not positive, holds.",
    usage: "The default window is 20 bars and the default distance is 0.3 percent.",
    traits: ["Volume is required", "Typical price is high, low, and close", "A close near VWAP holds"],
  },
  obv_trend: {
    concept: "On-balance volume and the close sloping the same way.",
    works:
      "A buy intention appears when both rose over the lookback. A sell intention appears when both fell. Disagreement holds. Missing volume holds.",
    usage: "The lookback default is 20 bars.",
    traits: ["Volume is required", "Price and OBV must agree", "A flat disagreement holds"],
  },
  liquidity_sweep: {
    concept: "A wick takes the prior swing, and the close returns inside it.",
    works:
      "A sell intention appears when the high exceeds the prior swing high and the close finishes back below it. A buy intention appears when the low takes the prior swing low and the close finishes back above it.",
    usage: "The swing lookback default is 20. The current bar is not part of the swing.",
    traits: ["The close must return inside", "A close that stays beyond the swing is not a sweep", "Uses high, low, and close"],
  },
  fvg: {
    concept: "A gap between the first and the third of the last three candles.",
    works:
      "A buy intention appears when the first high is still below the latest low. A sell intention appears when the first low is still above the latest high. Overlap holds.",
    usage: "There are no parameters. Three candles are required.",
    traits: ["The middle candle is not the gap test", "The gap must still be open", "Three candles only"],
  },
  order_block: {
    concept: "Price retests the last opposite candle before a directional impulse.",
    works:
      "On a bullish impulse, the last down candle is the block. A buy intention appears when the latest low tags that candle and the close finishes above it. The bearish case is the mirror.",
    usage: "The impulse length default is 3 bars.",
    traits: ["An opposite candle is required", "The latest bar must tag that candle", "A close that does not clear the block holds"],
  },
  session_breakout: {
    concept: "The close breaking the high or low of earlier bars inside a UTC hour window.",
    works:
      "If any bar has no readable time, the result is hold. The range uses earlier bars inside the window, not the latest bar. A close above that high is a buy intention. A close below that low is a sell intention.",
    usage: "The default window is 07:00 to 16:00 UTC. The two hours must differ and each must be from 0 to 23.",
    traits: ["Bar time is required", "An empty window holds", "The latest bar is not part of the range"],
  },
};
