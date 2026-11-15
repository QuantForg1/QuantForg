"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase6ExecutionDesk } from "@/components/ops/phase6/execution-desk";

export default function ExecutionOptimizationPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="Execution Optimization"
        description="Persisted OMS and broker execution quality — signals are not fills."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase6ExecutionDesk />
      </PageMotion>
    </div>
  );
}
