"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

const ITEMS = [
  {
    q: "How does QuantForg work?",
    a: "You create a QuantForg account and connect an MT5 broker account you already own. QuantForg reads that session, evaluates market structure and strategy profiles, and can submit an order only after risk validation and only when execution is authorized. A research result is not an order. An order is not a trade until the broker confirms the fill.",
  },
  {
    q: "Does QuantForg hold customer funds?",
    a: "No. Your capital stays at your broker. QuantForg does not open a brokerage account for you and does not custody customer funds.",
  },
  {
    q: "How do I connect my MT5 account?",
    a: "Create your QuantForg account, then open Broker Accounts and enter the MT5 login you own. Weltrade is the production connection. QuantForg uses the permissions that broker login already grants. Email verification stays on the existing account path. This is not a separate identity check.",
  },
  {
    q: "Which brokers are supported?",
    a: "Supported MT5 brands (in order): Weltrade, XM, Exness, HFM, JustMarkets, IC Markets, Pepperstone, and FP Markets. Weltrade is the production-verified connection today. Listing a brand is not the same as a verified LIVE path — authentication evidence is recorded separately. MetaTrader 5 is the trading platform, not a broker.",
  },
  {
    q: "How are risk controls applied?",
    a: "Risk checks run before an order is submitted. Customer preferences — risk per trade, maximum lot, daily loss, and open positions — can be stricter than the platform ceiling and cannot loosen it. A failed check blocks the order. A subscription plan does not bypass those checks. The autonomous desk trades XAUUSD (gold).",
  },
  {
    q: "How is performance calculated?",
    a: "Completed results come from broker deal history after a session is connected: entry, exit, commission, swap, and net profit when that history is returned. This page does not publish a sample win rate, profit, profit factor, drawdown, or average trade.",
  },
  {
    q: "What happens if the connection fails?",
    a: "The gateway reports the session as unavailable. QuantForg does not submit an order without that connection. Positions that are already open remain at the broker under the stops and permissions on that account.",
  },
  {
    q: "Can I disconnect my broker?",
    a: "Yes. Broker Accounts includes disconnect for the connected Weltrade session. Disconnecting stops QuantForg from using that login. It does not close the account at the broker.",
  },
  {
    q: "Are profits guaranteed?",
    a: "No. QuantForg sells software access. Trading can lose capital. A subscription, a signal, or a connected account is not a promise of profit.",
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
