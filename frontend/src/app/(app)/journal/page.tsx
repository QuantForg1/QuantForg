"use client";

import Link from "next/link";
import { BookOpen, History } from "lucide-react";
import { Button } from "@/components/ui/button";

/**
 * Journal desk hub — session memory surfaces.
 * Primary live broker trade ledger lives at /journal/orders.
 */
export default function JournalPage() {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-8 px-6 py-12">
      <div>
        <p className="text-[10px] font-medium uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          Journal
        </p>
        <h1 className="mt-1 font-[family-name:var(--font-display)] text-2xl text-[var(--fg)]">
          Session memory
        </h1>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">
          Live broker history and desk notes. Orders History reads MetaTrader deals through
          the Execution Gateway — never mock fills.
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
        <div className="rounded-xl border border-[var(--border)] bg-[var(--bg-panel)] p-5 opacity-90">
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
