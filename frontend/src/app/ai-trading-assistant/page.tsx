import type { Metadata } from "next";
import { SeoLanding } from "@/components/marketing/seo-landing";

export const metadata: Metadata = {
  title: { absolute: "QuantForg AI: AI Trading Assistant & Chart Screenshot Analysis for Gold" },
  description:
    "QuantForg AI is an AI trading assistant for gold (XAUUSD). Ask about the live market, key levels, sessions and news, or upload a chart screenshot for an instant analysis. Free with every account.",
  alternates: { canonical: "/ai-trading-assistant" },
  keywords: [
    "AI trading assistant",
    "AI chart analysis",
    "chart screenshot analysis",
    "gold market analysis",
    "XAUUSD analysis",
    "AI forex assistant",
  ],
  openGraph: {
    title: "QuantForg AI: AI Trading Assistant for Gold",
    description: "Live gold market answers and chart screenshot analysis, grounded in real data.",
    url: "/ai-trading-assistant",
    images: [{ url: "/og-image.png", width: 1200, height: 630, alt: "QuantForg AI trading assistant" }],
  },
};

const FAQ = [
  {
    q: "What can QuantForg AI do?",
    a: "It answers trading questions about gold using live market data: price, trend on several timeframes, support and resistance, volatility, the current session and upcoming economic events. It can also read a chart screenshot you upload and explain what it shows.",
  },
  {
    q: "How does chart screenshot analysis work?",
    a: "Upload a screenshot from MT5, TradingView or any platform. QuantForg AI reads the timeframe, structure, levels and indicators that are visible, and explains the setup. If a value is not legible, it says so instead of guessing.",
  },
  {
    q: "Does QuantForg AI make up prices?",
    a: "No. Prices, levels and indicators come only from the live market feed. Recent news comes from cited sources. If data is unavailable, it tells you.",
  },
  {
    q: "Which languages does it support?",
    a: "You can ask in any major language, including English, French, Spanish, Swahili and Kinyarwanda, and it answers in the same language.",
  },
  {
    q: "Is QuantForg AI free?",
    a: "Yes, QuantForg AI is included with every account, including the free one.",
  },
];

export default function AiTradingAssistantPage() {
  return (
    <SeoLanding
      path="/ai-trading-assistant"
      eyebrow="QuantForg AI"
      title="An AI trading assistant that knows the live gold market"
      lead="QuantForg AI answers your trading questions with real, live XAUUSD data and analyzes the chart screenshots you upload. It shows its reasoning step by step and tells you when something is uncertain."
      highlights={[
        { title: "Live market answers", text: "Trend, levels, volatility, session and news, from the live gold feed, not from memory." },
        { title: "Chart screenshot analysis", text: "Upload any chart and get a clear read of structure, levels and the setup." },
        { title: "Trade conditions check", text: "Is now a good moment to trade gold? A clear checklist with the reason for each point." },
        { title: "News and calendar aware", text: "Knows the next high-impact events and cites sources for recent news." },
        { title: "Strategy knowledge", text: "Explains 100+ strategies and how they have been performing on recent gold data." },
        { title: "Any language", text: "Ask in your own language and get the answer in the same language." },
      ]}
      sections={[
        {
          title: "Grounded in real data",
          body: (
            <p>
              Most AI chatbots answer from what they learned during training, which can be months old. QuantForg AI
              receives a fresh snapshot of the gold market with every question, including price, multi-timeframe
              trend, key levels, volatility and the economic calendar. Its answers describe the market as it is now.
            </p>
          ),
        },
        {
          title: "See how it thinks",
          body: (
            <p>
              While it works, QuantForg AI shows each step: reading the market, checking the news and analyzing your
              chart. Then it writes a structured answer covering bias, levels, conditions and risks, so you can check
              the logic yourself.
            </p>
          ),
        },
        {
          title: "Built for traders who want honesty",
          body: (
            <p>
              QuantForg AI never promises profits and never tells you a trade is certain. It explains probabilities,
              risks and what would invalidate an idea. The final decision is always yours.
            </p>
          ),
        },
      ]}
      faq={FAQ}
    />
  );
}
