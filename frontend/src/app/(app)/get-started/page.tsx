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

const BROKER_STEPS = [
  {
    title: "Pick a priority broker",
    detail:
      "Weltrade, XM, Exness, IC Markets, or Pepperstone — all via MetaTrader 5.",
  },
  {
    title: "Read the onboarding guide",
    detail:
      "Open Broker Compatibility for the exact portal server hints (never invent a server name).",
    href: "/broker-compatibility",
  },
  {
    title: "Connect in QuantForg",
    detail: "Enter login, password, and server on MT5 Accounts.",
    href: "/mt5",
  },
  {
    title: "Validate",
    detail: "Run compatibility / certification only against a live session.",
    href: "/broker-certification",
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
        title="Get started"
        description="Closed beta onboarding — tour, broker wizard, and paper trading path."
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
            <CardTitle>First-run checklist</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            {CHECKLIST_ITEMS.map((item) => (
              <div
                key={item.id}
                className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--border)] px-3 py-2"
              >
                <div>
                  <div className="text-sm font-medium">{item.title}</div>
                  <div className="text-xs text-[var(--fg-muted)]">
                    {item.description}
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge tone={checklist?.[item.id] ? "success" : "neutral"}>
                    {checklist?.[item.id] ? "done" : "todo"}
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

        <Card id="broker">
          <CardHeader>
            <CardTitle>Broker connection wizard</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            <p className="text-sm text-[var(--fg-muted)]">
              Additive guide over existing Compatibility and MT5 pages — no
              simulated connectivity.
            </p>
            <ol className="list-decimal space-y-2 pl-5 text-sm">
              {BROKER_STEPS.map((s) => (
                <li key={s.title}>
                  <div className="font-medium">{s.title}</div>
                  <div className="text-[var(--fg-muted)]">{s.detail}</div>
                  {s.href ? (
                    <Button size="sm" variant="secondary" className="mt-1" asChild>
                      <Link
                        href={s.href}
                        onClick={() =>
                          setChecklist(setChecklistItem("broker", true))
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

        <Card>
          <CardHeader>
            <CardTitle>Paper trading tutorial</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <p className="text-[var(--fg-muted)]">
              Open Paper Trading for the interactive tutorial card, or follow:
            </p>
            <ol className="list-decimal space-y-1 pl-5">
              <li>Set symbol (e.g. EURUSD) and volume (e.g. 0.10)</li>
              <li>Submit a Buy or Sell paper order</li>
              <li>Confirm positions and history update</li>
              <li>Reset when finished practicing</li>
            </ol>
            <Button size="sm" asChild>
              <Link
                href="/paper"
                onClick={() => setChecklist(setChecklistItem("paper", true))}
              >
                Go to Paper Trading
              </Link>
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
