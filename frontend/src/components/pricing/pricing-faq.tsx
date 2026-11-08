"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    q: "What am I paying for?",
    a: "A QuantForg subscription is software access to the trading technology platform and the support level for that plan. It is not a managed trading account, broker partnership, or profit share.",
  },
  {
    q: "Do these prices guarantee trading performance?",
    a: "No. QuantForg never promises profits, guaranteed returns, or risk-free trading. Market outcomes depend on markets, brokers, and your own decisions.",
  },
  {
    q: "Is annual billing available?",
    a: "Not yet. Only monthly plan pricing is published. An annual option will appear only after a recurring billing provider is configured to support it.",
  },
  {
    q: "Can I checkout online today?",
    a: "Yes — signed-in customers can start a NOWPayments LIVE crypto invoice from Billing checkout. Paid access activates only after QuantForg receives and verifies a finished payment notification. A browser return page never grants access by itself.",
  },
  {
    q: "Is crypto billing automatic every month?",
    a: "Not yet. Automatic recurring crypto billing is not enabled for this merchant account. After your paid period, renew with a new invoice from Settings → Subscription.",
  },
  {
    q: "Can I use my own MT5 broker?",
    a: "Yes, where your plan and secure infrastructure support it. You connect the MetaTrader 5 account you authorize. QuantForg does not assume every customer shares one MT5 account.",
  },
  {
    q: "How do upgrades, downgrades, and cancellation work?",
    a: "Upgrade or change plans by creating a new LIVE invoice for the target plan. Cancel from Settings → Subscription to stop renewal intent; access remains until the paid period ends unless an operator suspends the license. Entitlements never change from a client-side button alone.",
  },
  {
    q: "Where can I see my subscription status?",
    a: "Signed-in customers can open Settings → Subscription for plan status. If no verified license exists, the page shows that clearly instead of inventing paid access.",
  },
];

export function PricingFaq() {
  const baseId = useId();
  const [open, setOpen] = useState<number | null>(0);

  return (
    <div className="mx-auto w-full max-w-3xl space-y-3">
      {faqs.map((item, i) => {
        const isOpen = open === i;
        const panelId = `${baseId}-panel-${i}`;
        const btnId = `${baseId}-btn-${i}`;
        return (
          <div key={item.q} className="qf-glass-card overflow-hidden">
            <h3>
              <button
                id={btnId}
                type="button"
                className="flex w-full items-center justify-between gap-4 px-5 py-4 text-left font-[family-name:var(--font-display)] text-[1.02rem] font-semibold tracking-tight text-[var(--fg)] transition-colors hover:bg-[var(--surface-2)]/40 sm:px-6 sm:py-5"
                aria-expanded={isOpen}
                aria-controls={panelId}
                onClick={() => setOpen(isOpen ? null : i)}
              >
                <span>{item.q}</span>
                <ChevronDown
                  className={`h-4 w-4 shrink-0 text-[var(--accent)] transition-transform duration-[var(--duration-os)] ease-[var(--ease-os)] ${
                    isOpen ? "rotate-180" : ""
                  }`}
                  aria-hidden
                />
              </button>
            </h3>
            <div
              id={panelId}
              role="region"
              aria-labelledby={btnId}
              className={`qf-faq-panel grid transition-[grid-template-rows] duration-[var(--duration-os)] ease-[var(--ease-os)] ${
                isOpen ? "grid-rows-[1fr]" : "grid-rows-[0fr]"
              }`}
            >
              <div className="overflow-hidden">
                <p className="border-t border-[var(--border)] px-5 pb-5 pt-4 text-sm leading-relaxed text-[var(--fg-muted)] sm:px-6 sm:pb-6 sm:text-[0.9375rem]">
                  {item.a}
                </p>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
