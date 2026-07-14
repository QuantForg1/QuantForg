"use client";

import dynamic from "next/dynamic";
import { DeskSkeleton } from "@/components/desk/primitives";

const WorkspaceShell = dynamic(
  () => import("@/components/workspace/shell").then((m) => m.WorkspaceShell),
  {
    ssr: false,
    loading: () => (
      <div className="p-4">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

/** Institutional Trading Terminal — same multipanel shell as /workspace. */
export default function ExecutionPage() {
  return (
    <div className="-mx-4 -mb-6 flex h-[calc(100dvh-3.5rem)] min-h-[36rem] flex-col md:-mx-6">
      <WorkspaceShell />
    </div>
  );
}
