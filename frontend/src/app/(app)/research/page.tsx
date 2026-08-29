"use client";

import dynamic from "next/dynamic";
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
      <p className="shrink-0 border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-1.5 text-center text-[11px] font-medium uppercase tracking-wide text-[var(--fg-subtle)]">
        RESEARCH · NOT A TRADE AUTHORIZATION
      </p>
      <div className="min-h-0 flex-1">
        <ResearchShell />
      </div>
    </div>
  );
}
