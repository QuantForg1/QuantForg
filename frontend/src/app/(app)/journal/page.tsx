"use client";

import Link from "next/link";
import { BookOpen, History, LineChart, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { PageHeader } from "@/components/layout/page-header";
import { DESK_PANEL_SURFACE } from "@/components/desk/panel";
import { cn } from "@/lib/utils";

/**
 * Journal desk hub — session memory surfaces.
 * Primary live broker trade ledger lives at /journal/orders.
 * Institutional analytics live at /journal/analytics.
 * Trade replay lives at /trade-replay; desk analytics at /analytics.
 */
export default function JournalPage() {
  const tiles = [
    {
      href: "/journal/orders",
      icon: History,
      title: "Orders History",
      description:
        "Live MT5 deals, filters, exports, equity curve, and execution timeline.",
      cta: "Open ledger",
    },
    {
      href: "/journal/analytics",
      icon: LineChart,
      title: "Institutional Analytics",
      description:
        "Expectancy, Sharpe, SQN, drawdown, and distribution charts from live deals.",
      cta: "Open analytics",
    },
    {
      href: "/trade-replay",
      icon: PlayCircle,
      title: "Trade Replay",
      description:
        "Immutable execution audit stages from the Execution Audit Engine.",
      cta: "Open replay",
    },
    {
      href: "/analytics",
      icon: LineChart,
      title: "Performance Analytics",
      description:
        "Win rate, expectancy, profit factor, and return distribution across live and paper fills.",
      cta: "Open desk analytics",
    },
  ] as const;

  return (
    <div className="mx-auto w-full max-w-4xl">
      <PageHeader
        title="Journal"
        description="Session memory — live broker history and desk analytics. Never mock fills."
      />
      <div className="grid gap-[var(--space-3)] sm:grid-cols-2">
        {tiles.map((tile) => {
          const Icon = tile.icon;
          return (
            <Link
              key={tile.href}
              href={tile.href}
              className={cn(
                DESK_PANEL_SURFACE,
                "qf-card-interactive block p-[var(--space-4)] hover:border-[var(--border-strong)]",
              )}
            >
              <Icon className="mb-3 h-5 w-5 text-[var(--accent)]" aria-hidden />
              <h2 className="text-sm font-medium text-[var(--fg)]">{tile.title}</h2>
              <p className="mt-1 text-xs text-[var(--fg-muted)]">{tile.description}</p>
              <Button type="button" size="sm" className="mt-4" variant="secondary">
                {tile.cta}
              </Button>
            </Link>
          );
        })}
        <div
          className={cn(
            DESK_PANEL_SURFACE,
            "p-[var(--space-4)] opacity-90 sm:col-span-2",
          )}
        >
          <BookOpen className="mb-3 h-5 w-5 text-[var(--fg-subtle)]" aria-hidden />
          <h2 className="text-sm font-medium text-[var(--fg)]">Narrative journal</h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Session notes and playbooks remain available from Counsel and Ecosystem when
            enabled for your role.
          </p>
        </div>
      </div>
    </div>
  );
}
