import type { Metadata } from "next";
import Link from "next/link";
import { SeoLanding } from "@/components/marketing/seo-landing";

export const metadata: Metadata = {
  title: { absolute: "AI Gold Trading Robot for MT5 (XAUUSD Expert Advisor) · QuantForg" },
  description:
    "QuantForg is an AI gold trading robot for MetaTrader 5. It trades XAUUSD on your own broker account with risk limits on every trade, no martingale or grid, and full transparency. Start free.",
  alternates: { canonical: "/gold-trading-robot" },
  keywords: [
    "gold trading robot",
    "XAUUSD robot",
    "gold EA MT5",
    "XAUUSD expert advisor",
    "AI gold trading bot",
    "automated gold trading",
    "MT5 gold bot",
  ],
  openGraph: {
    title: "AI Gold Trading Robot for MT5",
    description: "Automated XAUUSD trading on your own MT5 account, with risk limits on every trade.",
    url: "/gold-trading-robot",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg gold trading robot" }],
  },
};

const FAQ = [
  {
    q: "What is a gold trading robot?",
    a: "A gold trading robot is software that analyzes the XAUUSD market and opens and manages trades automatically according to fixed rules. QuantForg runs on MetaTrader 5 and trades on the broker account you already own.",
  },
  {
    q: "Is QuantForg an MT5 Expert Advisor (EA)?",
    a: "It does the same job as an EA (automated gold trading on MT5), but the analysis runs on QuantForg's servers, so you do not need to keep a VPS or your computer running. Your broker account and your money stay with your broker.",
  },
  {
    q: "Does QuantForg use martingale or grid?",
    a: "No. Martingale and grid are blocked in the system. Every trade has a stop loss, and a position is never added to in order to average down a loss.",
  },
  {
    q: "Is the gold robot profitable?",
    a: "No trading software can guarantee profits, and anyone who promises them is not being honest. QuantForg focuses on disciplined, rule-based trading with strict risk limits, and it shows you its real results.",
  },
  {
    q: "How much does it cost?",
    a: "Creating an account, connecting your broker and using QuantForg AI are free. A subscription is needed to switch on automated trading. See the pricing page for current plans.",
  },
];

export default function GoldTradingRobotPage() {
  return (
    <SeoLanding
      path="/gold-trading-robot"
      eyebrow="Gold trading robot"
      title="The AI gold trading robot for MetaTrader 5"
      lead="QuantForg trades gold (XAUUSD) automatically on your own MT5 broker account. It analyzes the market around the clock on weekdays, only trades when its conditions are met, and puts a stop loss and risk limit on every position."
      highlights={[
        { title: "Built for gold", text: "Every rule, session filter and volatility model is designed for XAUUSD, not adapted from currency pairs." },
        { title: "Risk limits on every trade", text: "Stop loss on every position, per-trade and daily risk caps, and no martingale or grid." },
        { title: "Your broker, your money", text: "Connect the MT5 account you already own. QuantForg never holds your funds." },
        { title: "No VPS needed", text: "Analysis runs in the cloud, so the robot keeps working when your computer is off." },
        { title: "QuantForg AI included", text: "Ask about the live gold market, levels and news, or upload a chart screenshot for analysis." },
        { title: "Full transparency", text: "See every decision, every trade and the reason behind it in your dashboard." },
      ]}
      sections={[
        {
          title: "How the QuantForg gold robot trades",
          body: (
            <>
              <p>
                The robot reads live XAUUSD prices and candles across several timeframes. It checks trend, momentum,
                market structure, volatility, the trading session and upcoming news before it considers a trade. When
                the conditions line up and the reward is large enough compared to the risk, it sends the order to your
                broker with a stop loss and take profit already attached.
              </p>
              <p>
                When conditions are not right, for example during thin liquidity, just before major US data, or when
                timeframes disagree, it waits. Waiting is a decision too: it is how the robot avoids forcing trades.
              </p>
            </>
          ),
        },
        {
          title: "100+ strategies tested on real gold data",
          body: (
            <p>
              QuantForg maintains a library of more than 100 gold trading strategies, from trend following and
              breakouts to price action and session strategies. Each one is replayed on recent real XAUUSD data with
              spread included, so you can see which approaches are working in the current market.{" "}
              <Link href="/strategies" className="text-[var(--accent)] underline">Browse the strategy library</Link>.
            </p>
          ),
        },
        {
          title: "Risk management comes first",
          body: (
            <>
              <p>
                Gold can move fast, so every trade is sized from the account balance and the distance to the stop.
                Daily loss limits stop trading for the day if they are reached, and the total risk of open positions
                is capped.
              </p>
              <p>You choose your risk settings, and the robot cannot send an order that breaks them.</p>
            </>
          ),
        },
        {
          title: "Getting started takes minutes",
          body: (
            <ol className="list-decimal space-y-2 pl-5">
              <li>Create a free QuantForg account.</li>
              <li>Connect and verify your MT5 broker account.</li>
              <li>Review your risk settings and choose a plan.</li>
              <li>Switch the robot on and follow every trade from your dashboard or phone.</li>
            </ol>
          ),
        },
      ]}
      faq={FAQ}
    />
  );
}
