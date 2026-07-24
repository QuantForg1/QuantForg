"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocQueueWorkspace } from "@/components/ops/aoc-workspaces";

export default function AocQueuePage() {
  return (
    <div>
      <PageHeader
        title="Operational Queue"
        description="Prioritized work items with owners, dependencies and next actions."
      />
      <PageMotion>
        <AocQueueWorkspace />
      </PageMotion>
    </div>
  );
}
