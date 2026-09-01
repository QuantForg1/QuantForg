"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  ProductTour,
  ProductTourTrigger,
} from "@/components/platform/product-tour";
import {
  CHECKLIST_ITEMS,
  getChecklist,
  setChecklistItem,
  type ChecklistState,
} from "@/lib/platform/onboarding";

const STEPS = [
  {
    title: "Welcome to QuantForg",
    detail:
      "This is your workspace for market research and, when you choose, live trading. Research never requires a broker connection.",
  },
  {
    title: "Explore markets",
    detail:
      "Open Markets to see the instruments QuantForg can research. Coverage comes from the live catalogue — never invented.",
    href: "/markets",
    checklist: "markets" as const,
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
    detail: "Set appearance, notifications, and workspace defaults in Settings.",
    href: "/settings",
    checklist: "preferences" as const,
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

      <div className="space-y-4">
        <Card>
          <CardHeader>
            <CardTitle>Your first steps</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {CHECKLIST_ITEMS.map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2"
              >
                <div>
                  <div className="text-sm font-medium">{item.title}</div>
                  <div className="text-xs text-[var(--fg-muted)]">
                    {item.description}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={checklist?.[item.id] ? "success" : "neutral"}>
                    {checklist?.[item.id] ? "done" : "next"}
                  </Badge>
                  <Button size="sm" variant="secondary" asChild>
                    <Link
                      href={item.href}
                      onClick={() =>
                        setChecklist(setChecklistItem(item.id, true))
                      }
                    >
                      Open
                    </Link>
                  </Button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>How QuantForg is organized</CardTitle>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-3 pl-5 text-sm">
              {STEPS.map((s) => (
                <li key={s.title}>
                  <div className="font-medium">{s.title}</div>
                  <div className="text-[var(--fg-muted)]">{s.detail}</div>
                  {s.href ? (
                    <Button size="sm" variant="secondary" className="mt-2" asChild>
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
                </li>
              ))}
            </ol>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
