"use client";

import dynamic from "next/dynamic";
import Link from "next/link";
import { DeskSkeleton } from "@/components/desk/primitives";

const ResearchShell = dynamic(
  () => import("@/components/research/shell").then((m) => m.ResearchShell),
  {
    ssr: false,
    loading: () => (
      <div className="flex h-full items-center justify-center p-6">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

/** Flagship Research OS — Idea → Promote workflow. Advisory only. */
export default function ResearchPage() {
  return (
    <div className="qf-desk flex h-full min-h-0 w-full flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-2">
        <p className="min-w-0 text-xs leading-relaxed text-[var(--fg-muted)]">
          Institutional research workspace. Results come from the research service. Nothing here authorizes a trade.
        </p>
        <Link
          href="/signals"
          className="inline-flex h-9 shrink-0 items-center rounded-[var(--radius-sm)] px-3 text-xs font-medium text-[var(--accent)] hover:bg-[var(--accent-soft)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
        >
          Signals
        </Link>
      </div>
      <div className="min-h-0 flex-1">
        <ResearchShell />
      </div>
    </div>
  );
}
