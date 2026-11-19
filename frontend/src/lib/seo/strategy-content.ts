import data from "./strategies.json";

export type SeoStrategy = {
  slug: string;
  key: string;
  name: string;
  category: string;
  description: string;
};

export type CategoryGuide = {
  label: string;
  summary: string;
  howItWorksOnGold: string;
  bestConditions: string[];
  avoidWhen: string[];
  commonMistakes: string[];
};

export const STRATEGIES: SeoStrategy[] = data as SeoStrategy[];

export const CATEGORY_ORDER = [
  "trend",
  "momentum",
  "breakout",
  "mean_reversion",
  "reversal",
  "price_action",
  "pattern",
  "structure",
  "levels",
  "session",
  "volume",
] as const;

export const CATEGORY_GUIDES: Record<string, CategoryGuide> = {
  trend: {
    label: "Trend following",
    summary:
      "Trend strategies try to join a move that is already under way and stay with it while it lasts. They accept small losses in choppy markets in exchange for larger wins when gold trends.",
    howItWorksOnGold:
      "Gold often trends for hours after London or New York opens, or after big US data. Trend rules confirm that direction with moving averages, channels or momentum filters before entering. The stop goes beyond recent volatility, so normal pullbacks do not knock the trade out.",
    bestConditions: [
      "Clear higher highs and higher lows (or the reverse) on M15 and H1",
      "London and New York sessions, when liquidity is deepest",
      "Volatility at or above its recent average",
    ],
    avoidWhen: [
      "Gold is ranging tightly before a major news release",
      "The Asian session is quiet and spreads are wider",
      "Higher timeframes point the opposite way",
    ],
    commonMistakes: [
      "Entering late, after the move is already stretched far from its average",
      "Using stops that are too tight for gold's volatility",
      "Taking every crossover in a sideways market",
    ],
  },
  momentum: {
    label: "Momentum",
    summary:
      "Momentum strategies measure how fast price is moving and enter when that speed shifts in one direction. They aim to catch the strongest part of a move.",
    howItWorksOnGold:
      "Gold reacts sharply to US yields, the dollar and economic data. Momentum oscillators show when buying or selling pressure takes over. A trend filter usually keeps the trade on the side of the larger move.",
    bestConditions: [
      "Expanding volatility after a quiet period",
      "Session opens and the first hour after major data",
      "Agreement between the oscillator and the higher-timeframe trend",
    ],
    avoidWhen: [
      "Momentum is already extreme and fading",
      "Thin liquidity around the daily break (21:00 to 22:00 UTC)",
      "Seconds before a scheduled high-impact release",
    ],
    commonMistakes: [
      "Treating every oscillator cross as a trade",
      "Ignoring divergence that warns momentum is weakening",
      "Chasing a candle that has already covered most of the day's range",
    ],
  },
  breakout: {
    label: "Breakout",
    summary:
      "Breakout strategies wait for price to escape a range or channel and enter as the new move starts. Volatility expansion is what they need.",
    howItWorksOnGold:
      "Gold builds ranges during quiet hours and often breaks them when Europe or the US opens. Breakout rules mark the range, then require a close beyond it, so a quick spike that reverses does not count. Stops sit back inside the range.",
    bestConditions: [
      "A clean, well-tested range or squeeze before the break",
      "Session opens or news releases that bring new volume",
      "Volatility rising from a low base",
    ],
    avoidWhen: [
      "The range is very wide relative to the stop you can afford",
      "Price is breaking into a major daily level just above or below",
      "Liquidity is thin and false breaks are common",
    ],
    commonMistakes: [
      "Entering on an intrabar poke instead of a confirmed close",
      "Ignoring false breakouts in slow markets",
      "Placing the stop too close to the breakout level",
    ],
  },
  mean_reversion: {
    label: "Mean reversion",
    summary:
      "Mean reversion strategies fade moves that have stretched too far from their average, expecting price to snap back.",
    howItWorksOnGold:
      "Outside strong trends, gold tends to oscillate around a short-term average. These rules measure how far price is from that average, usually in ATR or standard deviations. They wait for the first sign of a turn before entering.",
    bestConditions: [
      "Sideways or slowly drifting markets",
      "Overextension without a fundamental catalyst",
      "Quieter sessions with stable volatility",
    ],
    avoidWhen: [
      "A strong trend or news-driven repricing is under way",
      "Volatility is expanding quickly",
      "Price is breaking out of a long consolidation",
    ],
    commonMistakes: [
      "Fading a strong trend just because an oscillator is overbought",
      "Entering before price actually turns",
      "Adding to losing positions (QuantForg never does this)",
    ],
  },
  reversal: {
    label: "Reversal",
    summary:
      "Reversal strategies look for evidence that the current move is exhausted and a turn is starting, often from divergence or volatility spikes.",
    howItWorksOnGold:
      "Gold's sharp moves often end with a final spike and then a fade. Reversal rules require confirmation, such as a divergence at a confirmed swing point or a volatility spike that ends with a strong opposite candle, before taking the trade.",
    bestConditions: [
      "Moves into well-known support or resistance",
      "Divergence between price and momentum",
      "Capitulation-style spikes that fail to follow through",
    ],
    avoidWhen: [
      "There is no confirmation candle yet",
      "A higher-timeframe trend is still accelerating",
      "Major news is still being digested",
    ],
    commonMistakes: [
      "Trying to pick the exact top or bottom",
      "Ignoring the higher-timeframe trend",
      "Using no stop because the reversal \"must\" happen",
    ],
  },
  price_action: {
    label: "Price action",
    summary:
      "Price-action strategies read candles and market structure directly: engulfing bars, pin bars, liquidity sweeps, fair value gaps and order blocks.",
    howItWorksOnGold:
      "Gold leaves clear footprints: sweeps of obvious highs and lows, imbalances after fast moves, and zones where large orders entered. These rules turn those footprints into precise entries with stops just beyond the invalidation point.",
    bestConditions: [
      "Liquid sessions with clean swing points",
      "Reactions at higher-timeframe levels",
      "Confluence with the prevailing trend",
    ],
    avoidWhen: [
      "Candles are erratic during news spikes",
      "Spreads are wide in thin hours",
      "There is no clear structure to anchor the stop",
    ],
    commonMistakes: [
      "Trading every pattern regardless of location",
      "Ignoring the session and liquidity context",
      "Moving the stop after entry",
    ],
  },
  pattern: {
    label: "Chart patterns",
    summary:
      "Pattern strategies trade classic, well-documented candle and chart formations once they complete.",
    howItWorksOnGold:
      "Formations such as double tops and bottoms, stars, tweezers and three-candle sequences show a shift in control between buyers and sellers. The rules wait for the pattern to finish, often with a neckline or confirmation close.",
    bestConditions: [
      "Patterns that form at swing extremes or key levels",
      "Normal volatility, so candles are meaningful",
      "Confirmation by the next candle",
    ],
    avoidWhen: [
      "The pattern forms in the middle of a range",
      "The candles are tiny relative to recent volatility",
      "News is due within minutes",
    ],
    commonMistakes: [
      "Seeing patterns that are not really there",
      "Entering before the pattern completes",
      "Ignoring where the pattern formed",
    ],
  },
  structure: {
    label: "Market structure",
    summary:
      "Structure strategies follow the sequence of swing highs and lows and trade the break of structure that confirms a new direction.",
    howItWorksOnGold:
      "A higher low followed by a close above the last swing high (a break of structure) often marks the start of a new leg in gold. The rules use confirmed swing points only, so they never repaint.",
    bestConditions: [
      "Clear swings on M15 and H1",
      "Liquid sessions",
      "Breaks that align with the higher-timeframe trend",
    ],
    avoidWhen: [
      "Overlapping, messy price action",
      "The break happens into a major daily level",
      "Thin holiday or rollover liquidity",
    ],
    commonMistakes: [
      "Labelling every small wiggle as a swing",
      "Entering before the close confirms the break",
      "Ignoring the next liquidity level",
    ],
  },
  levels: {
    label: "Key levels",
    summary:
      "Level strategies trade reactions at objectively calculated prices: daily pivots, Camarilla levels and Fibonacci retracements.",
    howItWorksOnGold:
      "Many gold traders watch the same daily levels, which can make them self-fulfilling. The rules calculate the levels from the previous day or the latest swing, then trade a rejection or a decisive break.",
    bestConditions: [
      "The first touch of a level in a session",
      "Levels that line up with recent structure",
      "Normal volatility",
    ],
    avoidWhen: [
      "Strong news-driven trends that run through levels",
      "Levels already tested several times today",
      "Wide spreads",
    ],
    commonMistakes: [
      "Treating a level as an exact price instead of a zone",
      "Fading every touch in a trending market",
      "Using levels from the wrong day",
    ],
  },
  session: {
    label: "Session",
    summary:
      "Session strategies use the daily rhythm of the gold market: the quiet Asian range, the London open and the New York open.",
    howItWorksOnGold:
      "Gold trades around the clock, but most volume arrives with London (07:00 UTC) and New York (13:30 UTC). These rules mark the range built before those opens and trade its break, or fade a false break.",
    bestConditions: [
      "Normal weekdays with active European and US sessions",
      "A well-defined pre-session range",
      "No high-impact release in the first minutes",
    ],
    avoidWhen: [
      "Bank holidays in London or New York",
      "Weeks with central bank meetings mid-session",
      "Extremely wide overnight ranges",
    ],
    commonMistakes: [
      "Using local time instead of UTC session times",
      "Ignoring daylight-saving shifts",
      "Trading the open during major data releases",
    ],
  },
  volume: {
    label: "Volume",
    summary:
      "Volume strategies weigh price moves by trading activity (tick volume on MT5), confirming whether a move has participation behind it.",
    howItWorksOnGold:
      "On MT5, tick volume rises when gold is actively traded. Volume-weighted indicators confirm whether a move is backed by activity, filtering out quiet drifts that often reverse.",
    bestConditions: [
      "Session opens and active hours",
      "Moves that start with rising tick volume",
      "Agreement with the main trend",
    ],
    avoidWhen: [
      "Holiday trading with abnormal volume",
      "The broker feed has no tick volume",
      "Low-activity Asian hours",
    ],
    commonMistakes: [
      "Comparing tick volume across different brokers",
      "Reading volume without price context",
      "Ignoring the session effect on volume",
    ],
  },
};

export function categoryGuide(category: string): CategoryGuide {
  return CATEGORY_GUIDES[category] ?? CATEGORY_GUIDES.trend;
}

export function strategyBySlug(slug: string): SeoStrategy | undefined {
  return STRATEGIES.find((s) => s.slug === slug);
}

export function relatedStrategies(s: SeoStrategy, n = 6): SeoStrategy[] {
  return STRATEGIES.filter((x) => x.category === s.category && x.slug !== s.slug).slice(0, n);
}

export function strategiesByCategory(): Array<[string, SeoStrategy[]]> {
  const groups = new Map<string, SeoStrategy[]>();
  for (const s of STRATEGIES) {
    groups.set(s.category, [...(groups.get(s.category) ?? []), s]);
  }
  const order = [...CATEGORY_ORDER] as string[];
  return [...groups.entries()].sort((a, b) => {
    const ia = order.indexOf(a[0]);
    const ib = order.indexOf(b[0]);
    return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
  });
}

/** Plain-language FAQ unique to each strategy page. */
export function strategyFaq(s: SeoStrategy): Array<{ q: string; a: string }> {
  const g = categoryGuide(s.category);
  return [
    {
      q: `What is the ${s.name} strategy?`,
      a: `${s.name} is a ${g.label.toLowerCase()} strategy. ${s.description} ${g.summary}`,
    },
    {
      q: `Does ${s.name} work on gold (XAUUSD)?`,
      a: `It can, in the right conditions: ${g.bestConditions[0].toLowerCase()}. No strategy works all the time. QuantForg tests ${s.name} and 100+ other strategies on recent real XAUUSD data and shows how each one actually performed, so you can see when it is working.`,
    },
    {
      q: `When should I avoid trading ${s.name}?`,
      a: `Be careful when ${g.avoidWhen.map((x) => x.charAt(0).toLowerCase() + x.slice(1)).join("; ")}.`,
    },
    {
      q: `Can ${s.name} be automated on MetaTrader 5?`,
      a: `Yes. Its rules are fully objective, so software can evaluate them on every candle. QuantForg runs on MT5 with your own broker account, and every trade passes risk limits before it is sent.`,
    },
  ];
}

export const SITE_URL = (process.env.NEXT_PUBLIC_APP_URL || "https://www.quantforg.com").replace(/\/$/, "");
