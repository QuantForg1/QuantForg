"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

const ITEMS = [
  {
    q: "How does QuantForg work?",
    a: "Create a QuantForg account and connect the MetaTrader 5 account you already own. The QuantForg Robot analyzes the gold market (XAUUSD) and trades only when its conditions and your risk limits allow. QuantForg AI is your assistant: ask it about the market or send it a chart screenshot for analysis.",
  },
  {
    q: "What is QuantForg AI?",
    a: "QuantForg AI is the assistant built into QuantForg. It answers trading questions in your language, explains the live gold market (trend, momentum, key support and resistance), summarizes news and upcoming economic events, and reviews your risk settings. It explains and analyzes; it never places trades for you.",
  },
  {
    q: "Can QuantForg AI analyze my chart screenshots?",
    a: "Yes. Upload, paste or drag a chart screenshot into the assistant. QuantForg AI reads the market structure, levels and indicators that are visible on the chart, compares them with the live gold price, and gives you the bullish and bearish scenarios with what would invalidate each. If something on the chart is not readable, it says so instead of guessing.",
  },
  {
    q: "Does QuantForg hold customer funds?",
    a: "No. Your capital stays at your broker. QuantForg does not open a brokerage account for you and never holds customer funds.",
  },
  {
    q: "How do I connect my MT5 account?",
    a: "Open Broker Accounts, choose your broker and server, and enter your MT5 login and password. QuantForg checks the account within seconds and shows Connected or Rejected. Your password is stored encrypted and never shown again.",
  },
  {
    q: "Which brokers are supported?",
    a: "MetaTrader 5 accounts at Weltrade, XM, Exness, HFM, JustMarkets, IC Markets, Pepperstone and FP Markets. MetaTrader 5 is the trading platform; the broker is the company that holds your account.",
  },
  {
    q: "How are risk controls applied?",
    a: "Every trade has a stop loss. Your settings (risk per trade, maximum lot, daily loss limit and number of open positions) are checked before any order is sent. Your limits can be stricter than the platform limits but never looser, and a subscription never bypasses them.",
  },
  {
    q: "How is performance calculated?",
    a: "Results come from your broker's own trade history: entry, exit, commission, swap and net profit. QuantForg does not publish sample or simulated statistics.",
  },
  {
    q: "What happens if the connection fails?",
    a: "QuantForg never opens a trade without a working connection to your account. Positions already open stay at your broker with their stop loss and take profit in place.",
  },
  {
    q: "Can I disconnect my broker?",
    a: "Yes, at any time from Broker Accounts. Disconnecting stops QuantForg from using that account; it does not close the account at your broker.",
  },
  {
    q: "Are profits guaranteed?",
    a: "No. QuantForg sells software access. Trading can lose capital. A subscription, an AI analysis, a signal or a connected account is not a promise of profit.",
  },
] as const;

export function FaqList() {
  const baseId = useId();
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="home-faq">
      {ITEMS.map((item, index) => {
        const expanded = open === index;
        const buttonId = `${baseId}-btn-${index}`;
        const panelId = `${baseId}-panel-${index}`;
        return (
          <div key={item.q} className="home-faq-item">
            <h3>
              <button
                id={buttonId}
                type="button"
                aria-expanded={expanded}
                aria-controls={panelId}
                onClick={() => setOpen(expanded ? null : index)}
              >
                <span>{item.q}</span>
                <ChevronDown aria-hidden data-open={expanded ? "true" : "false"} />
              </button>
            </h3>
            <div id={panelId} role="region" aria-labelledby={buttonId} hidden={!expanded}>
              <p>{item.a}</p>
            </div>
          </div>
        );
      })}
    </div>
  );
}
