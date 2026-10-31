"use client";

import { useState } from "react";
import { ChevronDown } from "lucide-react";

const ITEMS = [
  {
    q: "How does QuantForg work?",
    a: "You create an account, connect your own broker, and choose the permissions you grant. QuantForg then reads market data, scores opportunities, and can submit an order only after the existing risk checks pass. A signal is not an order. An order is not a fill until the broker confirms it.",
  },
  {
    q: "Is my account safe?",
    a: "Your capital stays at your broker. QuantForg does not show broker passwords after they are entered. Orders still have to pass the risk engine and the broker’s own permissions. No control on this page changes those limits.",
  },
  {
    q: "What symbols can I trade?",
    a: "The live desk is gold: XAUUSD. Other symbols are not offered as a public trading universe on this page. The signed-in Markets screen shows what the broker session actually returns.",
  },
  {
    q: "How are the results calculated?",
    a: "Completed results come from broker deals after you are connected: entry, exit, commission, swap, and net profit when the history API returns them. This marketing page does not publish sample win rates or profit figures.",
  },
  {
    q: "Which brokers are supported?",
    a: "The production connection is Weltrade through MetaTrader 5. You connect the account you own and grant the permissions that account allows. Other broker brands are not listed here as live integrations.",
  },
  {
    q: "What happens after I connect a broker?",
    a: "The gateway session loads account status, quotes, and positions from that login. Analysis can show a research signal. Execution still waits for risk validation. If a check fails, the order is not sent. Open positions stay under the existing stop and management rules.",
  },
  {
    q: "Can I use copy trading?",
    a: "QuantForg does not offer a separate copy-trading product. Automatic execution, when enabled, runs on your connected account under the settings already saved for that account.",
  },
] as const;

export function FaqList() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="divide-y divide-[var(--border)] overflow-hidden rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)]">
      {ITEMS.map((item, index) => {
        const expanded = open === index;
        return (
          <div key={item.q}>
            <button
              type="button"
              className="flex w-full items-center justify-between gap-4 px-4 py-4 text-left text-sm font-medium text-[var(--fg)] sm:px-5"
              aria-expanded={expanded}
              onClick={() => setOpen(expanded ? null : index)}
            >
              {item.q}
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-[var(--fg-muted)] transition-transform ${expanded ? "rotate-180" : ""}`}
                aria-hidden
              />
            </button>
            {expanded ? (
              <p className="px-4 pb-4 text-sm leading-relaxed text-[var(--fg-muted)] sm:px-5">
                {item.a}
              </p>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}
