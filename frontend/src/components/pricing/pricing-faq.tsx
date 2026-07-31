"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

const faqs = [
  {
    q: "Why no subscription?",
    a: "QuantForg is sold as a single institutional license. You pay once for lifetime access — no monthly fees, no renewals, no recurring charges.",
  },
  {
    q: "Do I own the software forever?",
    a: "Yes. The Institutional License is a one-time purchase for lifetime software access for the entitled operator.",
  },
  {
    q: "Can I use my MT5 broker?",
    a: "Yes. QuantForg connects to your own MetaTrader 5 terminal and broker session. You keep control of accounts, credentials, and live execution gates.",
  },
  {
    q: "Are future updates included?",
    a: "Yes. Your license includes future updates to the QuantForg platform for as long as the product is supported — no upgrade fees for the licensed software.",
  },
  {
    q: "Can I install on multiple devices?",
    a: "Access is intended for a single professional operator. You may sign in from the devices you use for desk work; concurrent multi-seat sharing is not included.",
  },
  {
    q: "What happens after payment?",
    a: "You land on a confirmation screen where you create your QuantForg account. After registration, you sign in and enter the institutional workspace.",
  },
  {
    q: "Can I access all features immediately?",
    a: "Yes. One license unlocks the complete QuantForg ecosystem — no tiers, no feature gates, no upsells after purchase.",
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
