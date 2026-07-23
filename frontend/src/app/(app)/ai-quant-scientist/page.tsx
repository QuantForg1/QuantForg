"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqsDashboardWorkspace } from "@/components/ops/aqs-workspaces";

export default function AiQuantScientistPage() {
  return (
    <div>
      <PageHeader
        title="AI Quant Scientist"
        description="Institutional AI research scientist — patterns, weaknesses, comparisons, and explainable recommendations. Never modifies production."
      />
      <PageMotion>
        <AqsDashboardWorkspace />
      </PageMotion>
    </div>
  );
}
