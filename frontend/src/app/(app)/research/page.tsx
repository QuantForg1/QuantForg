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

/** Flagship Research OS — Idea → Promote workflow. */
export default function ResearchPage() {
  return (
    <div className="h-full min-h-0 w-full">
      <ResearchShell />
    </div>
  );
}
