"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ProductTour,
  ProductTourTrigger,
} from "@/components/platform/product-tour";
import { BILLING_PLANS, formatUsd, FREE_TRIAL_AVAILABLE } from "@/lib/billing/plans";
import {
  getChecklist,
  setChecklistItem,
  type ChecklistState,
} from "@/lib/platform/onboarding";

const STEPS = [
  {
    title: "Welcome to QuantForg",
    detail:
      "QuantForg is MT5 software for XAUUSD. Your funds stay at your broker. Research does not require a broker connection, and this guide never asks for a broker password.",
  },
  {
    title: "Read what the product will and will not do",
    detail:
      "Analysis is not an order. A failed risk check means no order is submitted. A stop is not a guaranteed fill price. A simulation is not broker profit and loss. The decision record shows stored fields only.",
    href: "/learn",
    checklist: "guides" as const,
  },
  {
    title: "Explore markets",
    detail:
      "Open Markets to see the instruments QuantForg can research. Coverage comes from the live catalogue — never invented.",
    href: "/markets",
    checklist: "markets" as const,
  },
  {
    title: "Read what a decision means",
    detail:
      "A BUY or SELL on the decision report is a recorded intention. ORDER_SENT is not a fill. NOT_REACHED is not a passed risk check. Fields the history row did not store stay unavailable.",
    href: "/learn/decision-lifecycle",
  },
  {
    title: "View research signals",
    detail:
      "Signals are research intelligence. They stay available without MT5. They are not trade authorization.",
    href: "/signals",
    checklist: "signals" as const,
  },
  {
    title: "Connect a broker when ready",
    detail:
      "Broker connection is optional until you want account data or live execution. Research continues without it.",
    href: "/broker",
    checklist: "broker" as const,
  },
  {
    title: "Configure trading preferences",
    detail: "Set appearance, notifications, and workspace defaults in Settings. This checklist is stored in this browser. It is not a server activation count.",
    href: "/settings",
    checklist: "preferences" as const,
  },
  {
    title: "Review plans before you subscribe",
    detail: FREE_TRIAL_AVAILABLE
      ? "See the pricing page for the current offer."
      : `Current software prices: ${BILLING_PLANS.map((plan) => `${plan.name} ${formatUsd(plan.monthlyPriceUsd)}`).join(", ")}. A free trial is not offered. A plan does not bypass a risk check, and opening the pricing page is not a subscription.`,
    href: "/pricing",
    checklist: "plans" as const,
  },
  {
    title: "Enable live trading only when explicitly ready",
    detail:
      "Live trading stays disabled until you connect a broker and pass existing risk, ownership, and authorization checks. QuantForg never auto-enables live trading.",
    href: "/broker",
    checklist: "live_ready" as const,
  },
];

export default function GetStartedPage() {
  const [checklist, setChecklist] = useState<ChecklistState | null>(null);
  const [tourOpen, setTourOpen] = useState(false);

  useEffect(() => {
    setChecklist(getChecklist());
  }, []);

  return (
    <div>
      <PageHeader
        eyebrow="Onboarding"
        title="Welcome to QuantForg"
        description="Start with markets and research. Connect a broker later. Live trading stays off until you enable it."
        actions={
          <div className="flex gap-2">
            <ProductTourTrigger />
            <Button size="sm" onClick={() => setTourOpen(true)}>
              Start tour
            </Button>
          </div>
        }
      />

      {tourOpen ? (
        <ProductTour forceOpen onClose={() => setTourOpen(false)} />
      ) : null}

      <ol className="space-y-3">
        {STEPS.map((s, index) => (
          <li
            key={s.title}
            className="flex flex-col gap-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
          >
            <div className="min-w-0">
              <p className="text-[11px] font-medium uppercase tracking-[0.12em] text-[var(--fg-subtle)]">
                Step {index + 1}
              </p>
              <p className="mt-1 text-sm font-medium text-[var(--fg)]">{s.title}</p>
              <p className="mt-1 text-sm leading-relaxed text-[var(--fg-muted)]">{s.detail}</p>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {s.checklist ? (
                <Badge tone={checklist?.[s.checklist] ? "success" : "neutral"}>
                  {checklist?.[s.checklist] ? "done" : "next"}
                </Badge>
              ) : null}
              {s.href ? (
                <Button size="sm" variant="secondary" asChild>
                  <Link
                    href={s.href}
                    onClick={() =>
                      s.checklist
                        ? setChecklist(setChecklistItem(s.checklist, true))
                        : undefined
                    }
                  >
                    Continue
                  </Link>
                </Button>
              ) : null}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}
