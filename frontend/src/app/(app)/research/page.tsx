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
    <div className="flex h-full min-h-0 w-full flex-col">
      <div className="flex shrink-0 flex-wrap items-center justify-center gap-3 border-b border-[var(--border)] bg-[var(--surface)] px-4 py-1.5">
        <p className="text-center text-[11px] font-medium uppercase tracking-wide text-[var(--fg-subtle)]">
          RESEARCH · NOT A TRADE AUTHORIZATION
        </p>
        <Link
          href="/signals"
          className="text-[11px] font-medium text-[var(--fg-muted)] hover:text-[var(--accent)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
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
