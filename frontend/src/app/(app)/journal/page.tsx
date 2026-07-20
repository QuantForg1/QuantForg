"use client";

import Link from "next/link";
import { BookOpen, History, LineChart, PlayCircle } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Journal desk hub — session memory surfaces.
 * Primary live broker trade ledger lives at /journal/orders.
 * Institutional analytics live at /journal/analytics.
 * Trade replay opens inside order details.
 */
export default function JournalPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 p-3 sm:p-4 md:p-6 md:py-12">
      <div>
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Journal
        </p>
        <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl text-[var(--fg)]">
          Session memory
        </h1>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">
          Live broker history and desk analytics. Orders History and Institutional Analytics
          read MetaTrader deals through the Execution Gateway — never mock fills. Trade replay
          lives inside order details.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Link
          href="/journal/orders"
          className="rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5 transition-colors hover:border-[var(--accent)]"
        >
          <History className="mb-3 h-5 w-5 text-[var(--accent)]" />
          <h2 className="text-sm font-medium text-[var(--fg)]">Orders History</h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Live MT5 deals, filters, exports, equity curve, and execution timeline.
          </p>
          <Button type="button" size="sm" className="mt-4" variant="outline">
            Open ledger
          </Button>
        </Link>
        <Link
          href="/journal/analytics"
          className="rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5 transition-colors hover:border-[var(--accent)]"
        >
          <LineChart className="mb-3 h-5 w-5 text-[var(--accent)]" />
          <h2 className="text-sm font-medium text-[var(--fg)]">Institutional Analytics</h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Expectancy, Sharpe, SQN, drawdown, and distribution charts from live deals.
          </p>
          <Button type="button" size="sm" className="mt-4" variant="outline">
            Open analytics
          </Button>
        </Link>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5 opacity-90 sm:col-span-2">
          <PlayCircle className="mb-3 h-5 w-5 text-[var(--fg-subtle)]" />
          <h2 className="text-sm font-medium text-[var(--fg)]">Trade replay</h2>
          <p className="mt-1 text-xs text-[var(--fg-muted)]">
            Immutable execution audit stages open from Orders History → Details. Chart candle
            replay stays Not available without stored bar paths.
          </p>
        </div>
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5 opacity-90 sm:col-span-2">
          <BookOpen className="mb-3 h-5 w-5 text-[var(--fg-subtle)]" />
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
