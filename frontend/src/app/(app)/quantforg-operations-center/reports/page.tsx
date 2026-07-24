"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AocReportsWorkspace } from "@/components/ops/aoc-workspaces";

export default function AocReportsPage() {
  return (
    <div>
      <PageHeader
        title="Operations Reports"
        description="Daily ops, weekly executive, platform readiness and recommendation reports."
      />
      <PageMotion>
        <AocReportsWorkspace />
      </PageMotion>
    </div>
  );
}
