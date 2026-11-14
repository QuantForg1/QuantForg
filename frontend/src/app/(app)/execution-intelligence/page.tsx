"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5ExecutionDesk } from "@/components/ops/phase5/execution-desk";

export default function ExecutionIntelligencePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Execution Intelligence"
        description="Persisted OMS lifecycle metrics — never inferred from signal generation alone."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5ExecutionDesk />
      </PageMotion>
    </div>
  );
}
