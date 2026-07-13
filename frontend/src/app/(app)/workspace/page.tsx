"use client";

import dynamic from "next/dynamic";
import { DeskSkeleton } from "@/components/desk/primitives";

const WorkspaceShell = dynamic(
  () =>
    import("@/components/workspace/shell").then((m) => m.WorkspaceShell),
  {
    ssr: false,
    loading: () => (
      <div className="p-4">
        <DeskSkeleton variant="page" />
      </div>
    ),
  },
);

export default function WorkspacePage() {
  return <WorkspaceShell />;
}
