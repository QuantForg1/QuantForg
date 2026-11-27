import type { Metadata } from "next";
import Link from "next/link";
import { SeoLanding } from "@/components/marketing/seo-landing";

export const metadata: Metadata = {
  title: { absolute: "QuantForg Gold Breakout EA for MT5 (XAUUSD) · Setup Guide" },
  description:
    "QuantForg Gold Breakout EA is a rule-based XAUUSD Expert Advisor for MetaTrader 5: trend-filtered breakout, stop loss on every trade, no martingale or grid. Setup guide and inputs explained.",
  alternates: { canonical: "/mt5-expert-advisor" },
  openGraph: {
    title: "QuantForg Gold Breakout EA for MT5",
    description: "Rule-based XAUUSD Expert Advisor with a stop loss on every trade. Setup guide and inputs.",
    url: "/mt5-expert-advisor",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg Gold Breakout EA" }],
  },
};

const FAQ = [
  {
    q: "Which symbol, timeframe and account type?",
    a: "XAUUSD on an M15 chart, on a hedging or netting MT5 account. Make sure Algo Trading is switched on.",
  },
  {
    q: "What does the EA do?",
    a: "Once per new M15 bar, inside its session (07:00 to 12:00 UTC, Monday to Friday), it looks for a confirmed breakout of the last 40 bars in the direction of the H1 EMA50/EMA200 trend. It opens one trade with a stop loss of 2.0 x ATR and a take profit of 2.5 x the risk.",
  },
  {
    q: "Does it use martingale, grid or averaging down?",
    a: "No. One position at a time, a stop loss on every trade, a spread filter, a daily stop, and the lot size is reduced so a stop-out never exceeds the risk cap.",
  },
  {
    q: "Will it make money?",
    a: "Nobody can promise that. The EA wins roughly four to five trades in ten in our tests and relies on winners being larger than losers, so losing streaks of several trades are normal. Backtests do not guarantee future results, and results depend on your broker, spread and execution. Test on a demo account first.",
  },
  {
    q: "Is this the same as the QuantForg cloud robot?",
    a: "No. The EA is a standalone product that runs inside your own MT5 terminal. The QuantForg cloud robot runs on our servers with a subscription and does not need your computer on.",
  },
];

export default function Mt5ExpertAdvisorPage() {
  return (
    <SeoLanding
      path="/mt5-expert-advisor"
      eyebrow="MT5 Expert Advisor"
      title="QuantForg Gold Breakout EA for MetaTrader 5"
      lead="A simple, transparent XAUUSD Expert Advisor: trend-filtered breakout entries, a stop loss and take profit on every trade, and strict risk limits. Listing on the MQL5 Market is in progress; this page explains how it works and how to set it up."
      highlights={[
        { title: "Rules you can read", text: "H1 EMA50/200 trend plus a confirmed M15 breakout of the last 40 bars. No black box." },
        { title: "Stop loss on every trade", text: "2.0 x ATR stop and 2.5 x risk target, with the reward checked after spread." },
        { title: "Risk cap built in", text: "Lot is reduced, never raised, so a stop-out stays under your maximum risk percent." },
        { title: "No martingale, no grid", text: "One position at a time and a daily stop that pauses trading for the day." },
        { title: "Session and spread filters", text: "Trades only 07:00 to 12:00 UTC on weekdays and skips wide spreads." },
        { title: "Honest by design", text: "We publish the settings and the risks. No profit promises." },
      ]}
      sections={[
        {
          title: "Set up in five steps",
          body: (
            <ol className="list-decimal space-y-2 pl-5">
              <li>Open MT5 and add an XAUUSD chart on the M15 timeframe.</li>
              <li>Attach QuantForgEA from the Navigator (Expert Advisors) and tick Allow Algo Trading.</li>
              <li>Keep the default lot of 0.01 while you test, and run it on a demo account first.</li>
              <li>Check the Experts tab: you should see the EA start without errors.</li>
              <li>Keep the terminal running (a VPS helps) during the 07:00 to 12:00 UTC session.</li>
            </ol>
          ),
        },
        {
          title: "Inputs explained",
          body: (
            <ul className="list-disc space-y-2 pl-5">
              <li><strong>InpLot</strong>: trade size. Default 0.01.</li>
              <li><strong>InpMaxRiskPct</strong>: maximum loss at the stop, as a percent of equity. The lot is reduced to fit it.</li>
              <li><strong>InpDailyStopPct</strong>: stops new trades for the day after this loss.</li>
              <li><strong>InpMaxSpread</strong>: skips trades when the spread is wider than this.</li>
              <li><strong>InpStartHourUTC / InpEndHourUTC</strong>: trading window.</li>
              <li><strong>InpSwingBars, InpAtrSlMult, InpRR</strong>: breakout lookback, stop distance and reward ratio.</li>
            </ul>
          ),
        },
        {
          title: "Know the risks",
          body: (
            <p>
              Trading gold is high risk and you can lose your capital. Read our{" "}
              <Link href="/risk-disclosure" className="text-[var(--accent)] underline">risk disclosure</Link> before you
              trade, and prefer the cloud robot on the{" "}
              <Link href="/pricing" className="text-[var(--accent)] underline">pricing page</Link> if you do not want to
              keep a terminal running.
            </p>
          ),
        },
      ]}
      faq={FAQ}
    />
  );
}
